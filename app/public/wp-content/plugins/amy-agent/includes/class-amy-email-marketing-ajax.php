<?php
/**
 * Admin-AJAX: Email Marketing send via wp_mail (FluentSMTP) + history/opt-out.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Explicit admin-triggered marketing sends (never silent).
 *
 * Delivery uses WordPress wp_mail so FluentSMTP (active on ogcnewfinity.com)
 * handles SMTP. From address defaults to hello@ogcnewfinity.com.
 * Personal Gmail and AgentMail are rejected as From.
 *
 * History lives in the Python service (same conversations.db). FluentSMTP has
 * no inbound — replies are manual notes or the optional inbound webhook.
 */
class Amy_Email_Marketing_Ajax {

	const NONCE_ACTION = 'amy_agent_email_marketing';

	/**
	 * Default From for marketing when Settings field is empty.
	 */
	const DEFAULT_FROM_EMAIL = 'hello@ogcnewfinity.com';

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @var Amy_Api_Client|null
	 */
	private $api_client;

	/**
	 * Last wp_mail_failed message (request-scoped).
	 *
	 * @var string
	 */
	private $last_mail_error = '';

	/**
	 * @param Amy_Settings        $settings   Settings instance.
	 * @param Amy_Api_Client|null $api_client Optional service client for history.
	 */
	public function __construct( Amy_Settings $settings, $api_client = null ) {
		$this->settings   = $settings;
		$this->api_client = $api_client;
	}

	/**
	 * Register AJAX + public opt-out REST + inbound webhook REST.
	 */
	public function register() {
		add_action( 'wp_ajax_amy_email_marketing_send', array( $this, 'ajax_send' ) );
		add_action( 'wp_ajax_amy_email_marketing_history', array( $this, 'ajax_history' ) );
		add_action( 'wp_ajax_amy_email_marketing_thread', array( $this, 'ajax_thread' ) );
		add_action( 'wp_ajax_amy_email_marketing_note', array( $this, 'ajax_note' ) );
		add_action( 'wp_ajax_amy_email_marketing_optout', array( $this, 'ajax_optout' ) );
		add_action( 'wp_ajax_amy_email_marketing_suppressions', array( $this, 'ajax_suppressions' ) );
		add_action( 'wp_mail_failed', array( $this, 'capture_mail_failure' ) );
		add_action( 'rest_api_init', array( $this, 'register_rest_routes' ) );
	}

	/**
	 * Public opt-out + optional inbound webhook (shared secret).
	 */
	public function register_rest_routes() {
		register_rest_route(
			'amy-agent/v1',
			'/email-opt-out',
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'handle_public_opt_out' ),
				'permission_callback' => '__return_true',
				'args'                => array(
					'email' => array(
						'required'          => true,
						'type'              => 'string',
						'sanitize_callback' => 'sanitize_email',
					),
					'token' => array(
						'required'          => true,
						'type'              => 'string',
						'sanitize_callback' => 'sanitize_text_field',
					),
				),
			)
		);

		register_rest_route(
			'amy-agent/v1',
			'/email-inbound',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'handle_inbound_webhook' ),
				'permission_callback' => array( $this, 'verify_amy_secret' ),
			)
		);

		register_rest_route(
			'amy-agent/v1',
			'/email-marketing/propose',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'handle_amy_propose' ),
				'permission_callback' => array( $this, 'verify_amy_secret' ),
			)
		);
	}

	/**
	 * Shared-secret gate for service → WP relays.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return true|WP_Error
	 */
	public function verify_amy_secret( $request ) {
		$expected = (string) $this->settings->get_shared_secret();
		if ( '' === $expected ) {
			return new WP_Error( 'amy_forbidden', '', array( 'status' => 403 ) );
		}
		$header = $request->get_header( 'x-amy-secret' );
		if ( ! is_string( $header ) || '' === $header || ! hash_equals( $expected, $header ) ) {
			return new WP_Error( 'amy_forbidden', '', array( 'status' => 403 ) );
		}
		return true;
	}

	/**
	 * HMAC token for public unsubscribe links.
	 *
	 * @param string $email Recipient.
	 * @return string
	 */
	public function opt_out_token( $email ) {
		$email = strtolower( sanitize_email( $email ) );
		$key   = (string) $this->settings->get_shared_secret();
		if ( '' === $key ) {
			$key = wp_salt( 'auth' );
		}
		return hash_hmac( 'sha256', 'amy-email-opt-out|' . $email, $key );
	}

	/**
	 * @param string $email Recipient.
	 * @return string Absolute opt-out URL.
	 */
	public function opt_out_url( $email ) {
		$email = strtolower( sanitize_email( $email ) );
		return add_query_arg(
			array(
				'email' => $email,
				'token' => $this->opt_out_token( $email ),
			),
			rest_url( 'amy-agent/v1/email-opt-out' )
		);
	}

	/**
	 * Public one-click opt-out.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_public_opt_out( $request ) {
		$email = strtolower( sanitize_email( (string) $request->get_param( 'email' ) ) );
		$token = (string) $request->get_param( 'token' );
		if ( ! $email || ! is_email( $email ) || ! hash_equals( $this->opt_out_token( $email ), $token ) ) {
			return new WP_REST_Response(
				array(
					'ok'      => false,
					'message' => __( 'Invalid opt-out link.', 'amy-agent' ),
				),
				400
			);
		}

		$ok = $this->persist_suppression( $email, 'one-click unsubscribe', 'opt_out' );
		$status = $ok ? 200 : 502;
		return new WP_REST_Response(
			array(
				'ok'      => $ok,
				'email'   => $email,
				'message' => $ok
					? __( 'You have been unsubscribed from Amy marketing email.', 'amy-agent' )
					: __( 'Could not record opt-out. Contact hello@ogcnewfinity.com.', 'amy-agent' ),
			),
			$status
		);
	}

	/**
	 * Optional inbound forwarder → Python history. Not AgentMail.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_inbound_webhook( $request ) {
		if ( ! $this->api_client ) {
			return new WP_REST_Response( array( 'ok' => false, 'message' => 'API client missing.' ), 500 );
		}
		$params = $request->get_json_params();
		if ( ! is_array( $params ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'message' => 'Invalid JSON.' ), 400 );
		}
		/**
		 * Filter inbound webhook payload before storage.
		 *
		 * @param array $params Raw JSON body.
		 */
		$params = apply_filters( 'amy_email_marketing_inbound_payload', $params );
		$result = $this->api_client->record_email_inbound( $params );
		$code   = $result['ok'] ? 200 : ( $result['status_code'] ? (int) $result['status_code'] : 502 );
		return new WP_REST_Response(
			array(
				'ok'      => (bool) $result['ok'],
				'message' => $result['ok']
					? __( 'Inbound message stored.', 'amy-agent' )
					: ( $result['error'] ? $result['error'] : __( 'Failed to store inbound.', 'amy-agent' ) ),
				'body'    => $result['body'],
				'note'    => __( 'FluentSMTP is outbound-only. This webhook is an optional forwarder — not AgentMail.', 'amy-agent' ),
			),
			$code
		);
	}

	/**
	 * Amy-triggered propose hook (service → WP → service history). Never sends.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_amy_propose( $request ) {
		if ( ! $this->api_client ) {
			return new WP_REST_Response( array( 'ok' => false, 'message' => 'API client missing.' ), 500 );
		}
		$params = $request->get_json_params();
		if ( ! is_array( $params ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'message' => 'Invalid JSON.' ), 400 );
		}

		/**
		 * Fires when Amy proposes a marketing send (still requires human Approve → Send).
		 *
		 * @param array $params Propose payload.
		 */
		do_action( 'amy_email_marketing_propose', $params );

		$result = $this->api_client->propose_email_send( $params );
		$code   = $result['ok'] ? 200 : ( $result['status_code'] ? (int) $result['status_code'] : 502 );
		return new WP_REST_Response(
			array(
				'ok'                     => (bool) $result['ok'],
				'requires_human_approve' => true,
				'message'                => $result['ok']
					? __( 'Draft proposed. A human must Approve then Send in Email Marketing — nothing was sent.', 'amy-agent' )
					: ( $result['error'] ? $result['error'] : __( 'Propose failed.', 'amy-agent' ) ),
				'body'                   => $result['body'],
			),
			$code
		);
	}

	/**
	 * @param WP_Error $error Mail error.
	 */
	public function capture_mail_failure( $error ) {
		if ( is_wp_error( $error ) ) {
			$this->last_mail_error = $error->get_error_message();
			// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
			error_log( '[amy-agent] email marketing wp_mail_failed: ' . $this->last_mail_error );
		}
	}

	/**
	 * Capability + nonce gate.
	 */
	private function guard() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to send marketing email.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( self::NONCE_ACTION, 'nonce' );
	}

	/**
	 * Explicit send after human approve. Never runs without admin click.
	 */
	public function ajax_send() {
		$this->guard();

		$confirmed = isset( $_POST['confirmed'] ) && '1' === (string) wp_unslash( $_POST['confirmed'] ); // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$approved  = isset( $_POST['approved'] ) && '1' === (string) wp_unslash( $_POST['approved'] ); // phpcs:ignore WordPress.Security.NonceVerification.Missing

		if ( ! $confirmed || ! $approved ) {
			wp_send_json_error(
				array(
					'message' => __( 'Approve the draft, then click Send and confirm. Marketing email is never sent silently.', 'amy-agent' ),
				),
				400
			);
		}

		$subject = isset( $_POST['subject'] ) ? sanitize_text_field( wp_unslash( $_POST['subject'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$body    = isset( $_POST['body'] ) ? sanitize_textarea_field( wp_unslash( $_POST['body'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing

		if ( '' === $subject ) {
			wp_send_json_error( array( 'message' => __( 'Subject is required.', 'amy-agent' ) ), 400 );
		}
		if ( '' === trim( $body ) ) {
			wp_send_json_error( array( 'message' => __( 'Message body is required.', 'amy-agent' ) ), 400 );
		}

		$recipients = $this->parse_recipients();
		if ( empty( $recipients ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Select at least one valid recipient from the approved audience.', 'amy-agent' ) ),
				400
			);
		}

		// Soft cap: personalized follow-ups, not bulk newsletter blasts.
		$max = (int) apply_filters( 'amy_email_marketing_max_recipients', 50 );
		if ( $max > 0 && count( $recipients ) > $max ) {
			wp_send_json_error(
				array(
					'message' => sprintf(
						/* translators: %d: max recipients */
						__( 'Too many recipients for one send (max %d). Narrow the selection.', 'amy-agent' ),
						$max
					),
				),
				400
			);
		}

		$from_email = $this->settings->get_marketing_from_email();
		$from_name  = $this->settings->get_marketing_from_name();

		if ( ! $this->is_allowed_from( $from_email ) ) {
			wp_send_json_error(
				array(
					'message' => __( 'From address must be a domain mailbox configured in Amy → Settings and authorized in FluentSMTP (site default hello@ogcnewfinity.com when empty). Personal Gmail and AgentMail are never used.', 'amy-agent' ),
				),
				400
			);
		}

		$suppressed = array();
		$sendable   = array();
		foreach ( $recipients as $to ) {
			if ( $this->is_recipient_suppressed( $to ) ) {
				$suppressed[] = $to;
			} else {
				$sendable[] = $to;
			}
		}

		if ( empty( $sendable ) && ! empty( $suppressed ) ) {
			$this->record_outbound_history(
				$subject,
				$body,
				$from_email,
				array_map(
					static function ( $email ) {
						return array(
							'email' => $email,
							'ok'    => false,
							'error' => 'opted_out',
						);
					},
					$suppressed
				)
			);
			wp_send_json_error(
				array(
					'message'    => __( 'All selected recipients are opted out. Nothing was sent.', 'amy-agent' ),
					'suppressed' => $suppressed,
				),
				400
			);
		}

		/**
		 * Fires immediately before FluentSMTP / wp_mail marketing send.
		 *
		 * @param string   $subject   Subject.
		 * @param string   $body      Plain body.
		 * @param string[] $sendable  Recipients that will be mailed.
		 * @param string   $from_email From address.
		 */
		do_action( 'amy_email_marketing_before_send', $subject, $body, $sendable, $from_email );

		$results = array();
		$sent    = 0;
		$failed  = 0;

		foreach ( $suppressed as $to ) {
			$results[] = array(
				'email' => $to,
				'ok'    => false,
				'error' => 'opted_out',
			);
		}

		$from_email_cb = function () use ( $from_email ) {
			return $from_email;
		};
		$from_name_cb  = function () use ( $from_name ) {
			return $from_name;
		};

		add_filter( 'wp_mail_from', $from_email_cb, 99 );
		add_filter( 'wp_mail_from_name', $from_name_cb, 99 );
		add_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );

		foreach ( $sendable as $to ) {
			$this->last_mail_error = '';
			$headers               = array(
				sprintf( 'From: %s <%s>', $this->encode_from_name( $from_name ), $from_email ),
				sprintf( 'Reply-To: %s', $from_email ),
			);

			$html_body = $this->build_message_html( $body, $from_email, $to );
			$ok        = wp_mail( $to, $subject, $html_body, $headers );

			if ( $ok ) {
				++$sent;
				$results[] = array(
					'email' => $to,
					'ok'    => true,
					'error' => '',
				);
			} else {
				++$failed;
				$err = $this->last_mail_error
					? $this->last_mail_error
					: sprintf(
						/* translators: %s: Marketing From email */
						__( 'wp_mail returned false for From %s. Open FluentSMTP → Connections / logs, confirm mailbox + SPF/DKIM, then retry.', 'amy-agent' ),
						$from_email
					);
				$results[] = array(
					'email' => $to,
					'ok'    => false,
					'error' => $err,
				);
				// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
				error_log( '[amy-agent] email marketing send failed to=' . $to . ' err=' . $err );
			}

			/**
			 * Per-recipient send result (FluentSMTP / wp_mail).
			 *
			 * @param string $to         Recipient.
			 * @param bool   $ok         Whether wp_mail succeeded.
			 * @param string $subject    Subject.
			 * @param string $from_email From.
			 */
			do_action( 'amy_email_marketing_send_result', $to, $ok, $subject, $from_email );
		}

		remove_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );
		remove_filter( 'wp_mail_from', $from_email_cb, 99 );
		remove_filter( 'wp_mail_from_name', $from_name_cb, 99 );

		$history = $this->record_outbound_history( $subject, $body, $from_email, $results );

		/**
		 * Fires after the marketing send batch finishes (history may be partial if service down).
		 *
		 * @param array $results Per-recipient results.
		 * @param array $history Service history response meta.
		 */
		do_action( 'amy_email_marketing_after_send', $results, $history );

		if ( 0 === $sent ) {
			wp_send_json_error(
				array(
					'message'    => sprintf(
						/* translators: %s: Marketing From email */
						__( 'No messages were sent. Verify FluentSMTP can send as %s (Amy → Settings → General). Check FluentSMTP → Connections and SPF/DKIM.', 'amy-agent' ),
						$from_email
					),
					'from_email' => $from_email,
					'sent'       => 0,
					'failed'     => $failed,
					'suppressed' => $suppressed,
					'results'    => $results,
					'history'    => $history,
				),
				500
			);
		}

		wp_send_json_success(
			array(
				'message'    => sprintf(
					/* translators: 1: sent count, 2: from email, 3: failed count */
					__( 'Sent %1$d message(s) From %2$s via wp_mail/FluentSMTP.%3$s', 'amy-agent' ),
					$sent,
					$from_email,
					$failed > 0 || ! empty( $suppressed )
						? ' ' . sprintf(
							/* translators: 1: failed count, 2: suppressed count */
							__( '%1$d failed, %2$d opted out — see history / FluentSMTP logs.', 'amy-agent' ),
							$failed,
							count( $suppressed )
						)
						: ''
				),
				'from_email' => $from_email,
				'sent'       => $sent,
				'failed'     => $failed,
				'suppressed' => $suppressed,
				'results'    => $results,
				'history'    => $history,
			)
		);
	}

	/**
	 * List conversation threads.
	 */
	public function ajax_history() {
		$this->guard();
		if ( ! $this->api_client ) {
			wp_send_json_error( array( 'message' => __( 'Service client unavailable.', 'amy-agent' ) ), 500 );
		}
		$q      = isset( $_POST['q'] ) ? sanitize_text_field( wp_unslash( $_POST['q'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$limit  = isset( $_POST['limit'] ) ? (int) $_POST['limit'] : 40; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$offset = isset( $_POST['offset'] ) ? (int) $_POST['offset'] : 0; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$result = $this->api_client->list_email_threads( $limit, $offset, $q );
		if ( ! $result['ok'] ) {
			wp_send_json_error(
				array(
					'message' => $result['error']
						? $result['error']
						: __( 'Could not load email history. Check the Amy Agent service.', 'amy-agent' ),
				),
				$result['status_code'] ? (int) $result['status_code'] : 502
			);
		}
		$body = is_array( $result['body'] ) ? $result['body'] : array();
		$body['inbound_limitation'] = __(
			'FluentSMTP is outbound-only. Automatic hello@ inbound is not wired (no AgentMail). Use Add reply note, or POST /wp-json/amy-agent/v1/email-inbound with X-Amy-Secret if you forward mail yourself.',
			'amy-agent'
		);
		wp_send_json_success( $body );
	}

	/**
	 * Thread detail.
	 */
	public function ajax_thread() {
		$this->guard();
		if ( ! $this->api_client ) {
			wp_send_json_error( array( 'message' => __( 'Service client unavailable.', 'amy-agent' ) ), 500 );
		}
		$thread_id = isset( $_POST['thread_id'] ) ? sanitize_text_field( wp_unslash( $_POST['thread_id'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		if ( '' === $thread_id ) {
			wp_send_json_error( array( 'message' => __( 'thread_id is required.', 'amy-agent' ) ), 400 );
		}
		$result = $this->api_client->get_email_thread( $thread_id );
		if ( ! $result['ok'] ) {
			wp_send_json_error(
				array(
					'message' => $result['error']
						? $result['error']
						: __( 'Could not load thread.', 'amy-agent' ),
				),
				$result['status_code'] ? (int) $result['status_code'] : 502
			);
		}
		wp_send_json_success( $result['body'] );
	}

	/**
	 * Add manual note / inbound reply note.
	 */
	public function ajax_note() {
		$this->guard();
		if ( ! $this->api_client ) {
			wp_send_json_error( array( 'message' => __( 'Service client unavailable.', 'amy-agent' ) ), 500 );
		}
		$thread_id  = isset( $_POST['thread_id'] ) ? sanitize_text_field( wp_unslash( $_POST['thread_id'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$body       = isset( $_POST['body'] ) ? sanitize_textarea_field( wp_unslash( $_POST['body'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$as_inbound = isset( $_POST['as_inbound'] ) && '1' === (string) wp_unslash( $_POST['as_inbound'] ); // phpcs:ignore WordPress.Security.NonceVerification.Missing
		if ( '' === $thread_id || '' === trim( $body ) ) {
			wp_send_json_error( array( 'message' => __( 'thread_id and body are required.', 'amy-agent' ) ), 400 );
		}
		$result = $this->api_client->add_email_thread_note(
			$thread_id,
			array(
				'body'       => $body,
				'wp_user_id' => get_current_user_id(),
				'as_inbound' => $as_inbound,
			)
		);
		if ( ! $result['ok'] ) {
			wp_send_json_error(
				array(
					'message' => $result['error']
						? $result['error']
						: __( 'Could not save note.', 'amy-agent' ),
				),
				$result['status_code'] ? (int) $result['status_code'] : 502
			);
		}
		wp_send_json_success( $result['body'] );
	}

	/**
	 * Admin-triggered opt-out.
	 */
	public function ajax_optout() {
		$this->guard();
		$email  = isset( $_POST['email'] ) ? sanitize_email( wp_unslash( $_POST['email'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$reason = isset( $_POST['reason'] ) ? sanitize_text_field( wp_unslash( $_POST['reason'] ) ) : 'admin'; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		if ( ! $email || ! is_email( $email ) ) {
			wp_send_json_error( array( 'message' => __( 'Valid email required.', 'amy-agent' ) ), 400 );
		}
		if ( ! $this->persist_suppression( $email, $reason, 'admin' ) ) {
			wp_send_json_error( array( 'message' => __( 'Could not record opt-out on the Amy service.', 'amy-agent' ) ), 502 );
		}
		wp_send_json_success(
			array(
				'email'   => strtolower( $email ),
				'message' => __( 'Recipient opted out. Future marketing sends are blocked.', 'amy-agent' ),
			)
		);
	}

	/**
	 * List suppressions.
	 */
	public function ajax_suppressions() {
		$this->guard();
		if ( ! $this->api_client ) {
			wp_send_json_error( array( 'message' => __( 'Service client unavailable.', 'amy-agent' ) ), 500 );
		}
		$result = $this->api_client->list_email_suppressions( 500 );
		if ( ! $result['ok'] ) {
			wp_send_json_error(
				array(
					'message' => $result['error']
						? $result['error']
						: __( 'Could not load opt-outs.', 'amy-agent' ),
				),
				$result['status_code'] ? (int) $result['status_code'] : 502
			);
		}
		wp_send_json_success( $result['body'] );
	}

	/**
	 * @return string
	 */
	public function html_content_type() {
		return 'text/html';
	}

	/**
	 * Parse and sanitize recipient list from POST.
	 *
	 * @return string[]
	 */
	private function parse_recipients() {
		$raw = array();
		if ( isset( $_POST['recipients'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing
			$posted = wp_unslash( $_POST['recipients'] ); // phpcs:ignore WordPress.Security.NonceVerification.Missing,WordPress.Security.ValidatedSanitizedInput.InputNotSanitized
			if ( is_array( $posted ) ) {
				$raw = $posted;
			} elseif ( is_string( $posted ) ) {
				$decoded = json_decode( $posted, true );
				if ( is_array( $decoded ) ) {
					$raw = $decoded;
				} else {
					$raw = preg_split( '/[\n,;]+/', $posted ) ?: array();
				}
			}
		}

		$out = array();
		foreach ( $raw as $item ) {
			$email = sanitize_email( trim( (string) $item ) );
			if ( $email && is_email( $email ) ) {
				$out[ strtolower( $email ) ] = $email;
			}
		}
		return array_values( $out );
	}

	/**
	 * Only allow domain mailboxes — never Gmail / AgentMail / free webmail.
	 *
	 * @param string $email From address.
	 * @return bool
	 */
	private function is_allowed_from( $email ) {
		$allowed = Amy_Settings::is_allowed_marketing_from_email( $email );
		/**
		 * Filter whether a marketing From address is allowed.
		 *
		 * @param bool   $allowed Default: domain mailbox not on free-webmail blocklist.
		 * @param string $email   Candidate From address.
		 */
		return (bool) apply_filters( 'amy_email_marketing_allow_from', $allowed, $email );
	}

	/**
	 * @param string $name Display name.
	 * @return string
	 */
	private function encode_from_name( $name ) {
		$name = trim( (string) $name );
		if ( '' === $name ) {
			$name = 'OGC NewFinity';
		}
		// Strip control chars / angle brackets that break From headers.
		$name = str_replace( array( "\r", "\n", '<', '>' ), '', $name );
		return $name;
	}

	/**
	 * Build a simple HTML body from plain draft text, with opt-out footer.
	 *
	 * @param string $body       Plain message.
	 * @param string $from_email From address shown in footer.
	 * @param string $to_email   Recipient (for personalized unsubscribe link).
	 * @return string
	 */
	private function build_message_html( $body, $from_email, $to_email = '' ) {
		$paragraphs = preg_split( "/\n{2,}/", trim( (string) $body ) ) ?: array();
		$html       = '';
		foreach ( $paragraphs as $para ) {
			$html .= '<p style="margin:0 0 1em;line-height:1.55;color:#1a1a1a;">'
				. nl2br( esc_html( trim( $para ) ) )
				. '</p>';
		}

		$opt_out = '';
		if ( $to_email && is_email( $to_email ) ) {
			$url     = $this->opt_out_url( $to_email );
			$opt_out = '<p style="margin:1.25em 0 0;font-size:12px;color:#888;">'
				. esc_html__( 'Prefer not to get these emails?', 'amy-agent' )
				. ' <a href="' . esc_url( $url ) . '" style="color:#666;">'
				. esc_html__( 'Unsubscribe', 'amy-agent' )
				. '</a></p>';
		}

		return '<div style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.55;">'
			. $html
			. '<p style="margin:2em 0 0;font-size:13px;color:#666;">— OGC NewFinity<br>'
			. '<a href="mailto:' . esc_attr( $from_email ) . '" style="color:#666;">'
			. esc_html( $from_email ) . '</a></p>'
			. $opt_out
			. '</div>';
	}

	/**
	 * @param string $email Recipient.
	 * @return bool
	 */
	private function is_recipient_suppressed( $email ) {
		if ( ! $this->api_client ) {
			return false;
		}
		$result = $this->api_client->check_email_suppressed( $email );
		if ( ! $result['ok'] || ! is_array( $result['body'] ) ) {
			return false;
		}
		return ! empty( $result['body']['suppressed'] );
	}

	/**
	 * @param string $email  Address.
	 * @param string $reason Reason.
	 * @param string $source Source key.
	 * @return bool
	 */
	private function persist_suppression( $email, $reason, $source ) {
		if ( ! $this->api_client ) {
			return false;
		}
		$result = $this->api_client->add_email_suppression(
			array(
				'email'  => strtolower( $email ),
				'reason' => $reason,
				'source' => $source,
			)
		);
		return (bool) $result['ok'];
	}

	/**
	 * Persist send results to the Python history store.
	 *
	 * @param string              $subject    Subject.
	 * @param string              $body       Plain body.
	 * @param string              $from_email From.
	 * @param array<int, array>   $results    Per-recipient results.
	 * @return array<string, mixed>
	 */
	private function record_outbound_history( $subject, $body, $from_email, array $results ) {
		if ( ! $this->api_client ) {
			return array(
				'ok'      => false,
				'message' => 'no_api_client',
			);
		}
		$payload = array(
			'subject'    => $subject,
			'body'       => $body,
			'from_email' => $from_email,
			'wp_user_id' => get_current_user_id(),
			'channel'    => 'fluentsmtp',
			'recipients' => array_map(
				static function ( $row ) {
					return array(
						'email' => isset( $row['email'] ) ? (string) $row['email'] : '',
						'ok'    => ! empty( $row['ok'] ),
						'error' => isset( $row['error'] ) ? (string) $row['error'] : null,
					);
				},
				$results
			),
		);
		$result = $this->api_client->record_email_outbound( $payload );
		return array(
			'ok'      => (bool) $result['ok'],
			'error'   => $result['error'],
			'body'    => $result['body'],
			'message' => $result['ok']
				? 'recorded'
				: ( $result['error'] ? $result['error'] : 'history_failed' ),
		);
	}
}
