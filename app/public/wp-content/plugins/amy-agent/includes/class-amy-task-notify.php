<?php
/**
 * Task Service outbound notify — FluentSMTP email + Telegram Admin Bot relay.
 *
 * Called by the Python service (shared secret) for assign / mid / expiry templates.
 * Never uses AgentMail or personal Gmail.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Channel adapter for task transactional mail + Telegram.
 */
class Amy_Task_Notify {

	const USER_META_CHAT_ID = 'amy_telegram_chat_id';

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @var Amy_Telegram
	 */
	private $telegram;

	/**
	 * Last wp_mail_failed message (request-scoped).
	 *
	 * @var string
	 */
	private $last_mail_error = '';

	/**
	 * @param Amy_Settings $settings Settings.
	 * @param Amy_Telegram $telegram Telegram bot (reuse Admin Bot #11).
	 */
	public function __construct( Amy_Settings $settings, Amy_Telegram $telegram ) {
		$this->settings = $settings;
		$this->telegram = $telegram;
	}

	/**
	 * Register REST route for service → WP outbound.
	 */
	public function register() {
		add_action( 'rest_api_init', array( $this, 'register_rest_routes' ) );
		add_action( 'wp_mail_failed', array( $this, 'capture_mail_failure' ) );
	}

	/**
	 * @param WP_Error $error Mail error.
	 */
	public function capture_mail_failure( $error ) {
		if ( is_wp_error( $error ) ) {
			$this->last_mail_error = $error->get_error_message();
			// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
			error_log( '[amy-agent] task notify wp_mail_failed: ' . $this->last_mail_error );
		}
	}

	/**
	 * REST: POST /amy-agent/v1/task-notify
	 */
	public function register_rest_routes() {
		register_rest_route(
			'amy-agent/v1',
			'/task-notify',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'handle_task_notify' ),
				'permission_callback' => array( $this, 'verify_amy_secret' ),
			)
		);
	}

	/**
	 * Shared secret gate (same header as service → WP would expect).
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
	 * Relay body from Python task_notify.dispatch_task_notify.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_task_notify( $request ) {
		$params = $request->get_json_params();
		if ( ! is_array( $params ) ) {
			return new WP_REST_Response(
				array(
					'ok'       => false,
					'message'  => 'Invalid JSON body.',
					'channels' => array(
						'email'    => 'bad_request',
						'telegram' => 'bad_request',
					),
				),
				400
			);
		}

		$event      = isset( $params['event'] ) ? sanitize_key( (string) $params['event'] ) : '';
		$wp_user_id = isset( $params['wp_user_id'] ) ? absint( $params['wp_user_id'] ) : 0;
		$subject    = isset( $params['subject'] ) ? sanitize_text_field( (string) $params['subject'] ) : '';
		$body       = isset( $params['body'] ) ? sanitize_textarea_field( (string) $params['body'] ) : '';
		$telegram   = isset( $params['telegram_html'] ) ? (string) $params['telegram_html'] : '';

		if ( ! in_array( $event, array( 'assign', 'mid_progress', 'expiry' ), true ) ) {
			return new WP_REST_Response(
				array(
					'ok'       => false,
					'message'  => 'Unknown event.',
					'channels' => array(
						'email'    => 'bad_event',
						'telegram' => 'bad_event',
					),
				),
				400
			);
		}
		if ( ! $wp_user_id || '' === $subject || '' === trim( $body ) ) {
			return new WP_REST_Response(
				array(
					'ok'       => false,
					'message'  => 'wp_user_id, subject, and body are required.',
					'channels' => array(
						'email'    => 'bad_request',
						'telegram' => 'bad_request',
					),
				),
				400
			);
		}

		$email_status = $this->send_email( $wp_user_id, $subject, $body );
		$tg_status    = $this->send_telegram( $wp_user_id, $telegram ? $telegram : $body );

		return new WP_REST_Response(
			array(
				'ok'       => true,
				'event'    => $event,
				'channels' => array(
					'email'    => $email_status,
					'telegram' => $tg_status,
				),
			),
			200
		);
	}

	/**
	 * @param int    $wp_user_id Recipient.
	 * @param string $subject    Subject.
	 * @param string $body       Plain text body.
	 * @return string Status token.
	 */
	public function send_email( $wp_user_id, $subject, $body ) {
		$user = get_userdata( (int) $wp_user_id );
		if ( ! $user || ! is_email( $user->user_email ) ) {
			return 'no_email';
		}

		$from_email = $this->settings->get_marketing_from_email();
		$from_name  = $this->settings->get_marketing_from_name();
		if ( ! $this->is_allowed_from( $from_email ) ) {
			return 'from_blocked';
		}

		$this->last_mail_error = '';

		$from_email_cb = function () use ( $from_email ) {
			return $from_email;
		};
		$from_name_cb  = function () use ( $from_name ) {
			return $from_name;
		};

		add_filter( 'wp_mail_from', $from_email_cb, 99 );
		add_filter( 'wp_mail_from_name', $from_name_cb, 99 );
		add_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );

		$headers = array(
			sprintf( 'From: %s <%s>', $this->encode_from_name( $from_name ), $from_email ),
			sprintf( 'Reply-To: %s', $from_email ),
		);
		$html    = $this->build_message_html( $body, $from_email );
		$ok      = wp_mail( $user->user_email, $subject, $html, $headers );

		remove_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );
		remove_filter( 'wp_mail_from', $from_email_cb, 99 );
		remove_filter( 'wp_mail_from_name', $from_name_cb, 99 );

		if ( ! $ok ) {
			return $this->last_mail_error ? 'wp_mail_failed' : 'wp_mail_false';
		}
		return 'sent';
	}

	/**
	 * @param int    $wp_user_id Recipient WP user.
	 * @param string $text       Plain or HTML-ish Telegram body.
	 * @return string Status token.
	 */
	public function send_telegram( $wp_user_id, $text ) {
		if ( ! $this->settings->is_telegram_enabled() ) {
			return 'disabled';
		}
		$chat_id = $this->resolve_chat_id( (int) $wp_user_id );
		if ( ! $chat_id ) {
			return 'not_linked';
		}
		$result = $this->telegram->send_message_to_chat( $chat_id, $text, true );
		return ! empty( $result['ok'] ) ? 'sent' : 'send_failed';
	}

	/**
	 * Resolve Telegram chat id for a WP user (user meta, then Admin Bot whitelist).
	 *
	 * @param int $wp_user_id WP user id.
	 * @return int|null
	 */
	public function resolve_chat_id( $wp_user_id ) {
		$wp_user_id = (int) $wp_user_id;
		$meta       = (int) get_user_meta( $wp_user_id, self::USER_META_CHAT_ID, true );
		if ( $meta > 0 ) {
			return $meta;
		}
		foreach ( $this->telegram->get_whitelist() as $row ) {
			if ( ! is_array( $row ) ) {
				continue;
			}
			if ( (int) ( $row['wp_user_id'] ?? 0 ) === $wp_user_id && ! empty( $row['telegram_id'] ) ) {
				return (int) $row['telegram_id'];
			}
		}
		return null;
	}

	/**
	 * Persist chat link for assignee self-serve connect.
	 *
	 * @param int $wp_user_id  WP user.
	 * @param int $telegram_id Telegram user/chat id (private chats match).
	 */
	public static function link_user_chat( $wp_user_id, $telegram_id ) {
		update_user_meta( (int) $wp_user_id, self::USER_META_CHAT_ID, (int) $telegram_id );
	}

	/**
	 * @param int $wp_user_id WP user.
	 */
	public static function unlink_user_chat( $wp_user_id ) {
		delete_user_meta( (int) $wp_user_id, self::USER_META_CHAT_ID );
	}

	/**
	 * @return string
	 */
	public function html_content_type() {
		return 'text/html';
	}

	/**
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
		return (bool) apply_filters( 'amy_task_notify_allow_from', true, $email );
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
		$name = str_replace( array( "\r", "\n", '<', '>' ), '', $name );
		return $name;
	}

	/**
	 * @param string $body       Plain body.
	 * @param string $from_email From shown in footer.
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
			. '<p style="margin:2em 0 0;font-size:13px;color:#666;">— Amy Task Service · OGC NewFinity<br>'
			. '<a href="mailto:' . esc_attr( $from_email ) . '" style="color:#666;">'
			. esc_html( $from_email ) . '</a></p>'
			. '</div>';
	}
}
