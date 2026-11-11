<?php
/**
 * Admin-AJAX: Email Marketing send via wp_mail (FluentSMTP).
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
	 * Last wp_mail_failed message (request-scoped).
	 *
	 * @var string
	 */
	private $last_mail_error = '';

	/**
	 * @param Amy_Settings $settings Settings instance.
	 */
	public function __construct( Amy_Settings $settings ) {
		$this->settings = $settings;
	}

	/**
	 * Register AJAX actions (logged-in admins only).
	 */
	public function register() {
		add_action( 'wp_ajax_amy_email_marketing_send', array( $this, 'ajax_send' ) );
		add_action( 'wp_mail_failed', array( $this, 'capture_mail_failure' ) );
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
					'message' => __( 'From address must be your domain mailbox set in Amy → Settings → General (example default: hello@ogcnewfinity.com). Personal Gmail and AgentMail are never used.', 'amy-agent' ),
				),
				400
			);
		}

		$results = array();
		$sent    = 0;
		$failed  = 0;

		$from_email_cb = function () use ( $from_email ) {
			return $from_email;
		};
		$from_name_cb  = function () use ( $from_name ) {
			return $from_name;
		};

		add_filter( 'wp_mail_from', $from_email_cb, 99 );
		add_filter( 'wp_mail_from_name', $from_name_cb, 99 );
		add_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );

		foreach ( $recipients as $to ) {
			$this->last_mail_error = '';
			$headers               = array(
				sprintf( 'From: %s <%s>', $this->encode_from_name( $from_name ), $from_email ),
				sprintf( 'Reply-To: %s', $from_email ),
			);

			$html_body = $this->build_message_html( $body, $from_email );
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
		}

		remove_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );
		remove_filter( 'wp_mail_from', $from_email_cb, 99 );
		remove_filter( 'wp_mail_from_name', $from_name_cb, 99 );

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
					'results'    => $results,
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
					$failed > 0
						? ' ' . sprintf(
							/* translators: %d: failed count */
							__( '%d failed — see FluentSMTP logs.', 'amy-agent' ),
							$failed
						)
						: ''
				),
				'from_email' => $from_email,
				'sent'       => $sent,
				'failed'     => $failed,
				'results'    => $results,
			)
		);
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
		$email = strtolower( trim( (string) $email ) );
		if ( '' === $email || ! is_email( $email ) ) {
			return false;
		}
		$blocked = array(
			'gmail.com',
			'googlemail.com',
			'agentmail.to',
			'yahoo.com',
			'outlook.com',
			'hotmail.com',
			'live.com',
			'icloud.com',
		);
		$host = substr( strrchr( $email, '@' ), 1 );
		if ( in_array( $host, $blocked, true ) ) {
			return false;
		}
		/**
		 * Filter whether a marketing From address is allowed.
		 *
		 * @param bool   $allowed Default: domain mailbox not on free-webmail blocklist.
		 * @param string $email   Candidate From address.
		 */
		return (bool) apply_filters( 'amy_email_marketing_allow_from', true, $email );
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
	 * Build a simple HTML body from plain draft text.
	 *
	 * @param string $body       Plain message.
	 * @param string $from_email From address shown in footer.
	 * @return string
	 */
	private function build_message_html( $body, $from_email ) {
		$paragraphs = preg_split( "/\n{2,}/", trim( (string) $body ) ) ?: array();
		$html       = '';
		foreach ( $paragraphs as $para ) {
			$html .= '<p style="margin:0 0 1em;line-height:1.55;color:#1a1a1a;">'
				. nl2br( esc_html( trim( $para ) ) )
				. '</p>';
		}

		return '<div style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.55;">'
			. $html
			. '<p style="margin:2em 0 0;font-size:13px;color:#666;">— OGC NewFinity<br>'
			. '<a href="mailto:' . esc_attr( $from_email ) . '" style="color:#666;">'
			. esc_html( $from_email ) . '</a></p>'
			. '</div>';
	}
}
