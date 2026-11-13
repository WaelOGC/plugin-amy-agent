<?php
/**
 * Public chat upload alerts — admin email + Telegram whitelist relay.
 *
 * Called by the Python service when a visitor uploads in public chat.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Outbound notify for public-chat file uploads.
 */
class Amy_Chat_Upload_Notify {

	const MAX_TELEGRAM_PHOTO_BYTES = 1_500_000;

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
	 * @param Amy_Telegram $telegram Telegram bot.
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
			error_log( '[amy-agent] chat upload notify wp_mail_failed: ' . $this->last_mail_error );
		}
	}

	/**
	 * REST: POST /amy-agent/v1/chat-upload-notify
	 */
	public function register_rest_routes() {
		register_rest_route(
			'amy-agent/v1',
			'/chat-upload-notify',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'handle_chat_upload_notify' ),
				'permission_callback' => array( $this, 'verify_amy_secret' ),
			)
		);
	}

	/**
	 * Shared secret gate.
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
	 * Relay body from Python public_chat_upload_notify.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_chat_upload_notify( $request ) {
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

		$subject       = isset( $params['subject'] ) ? sanitize_text_field( (string) $params['subject'] ) : '';
		$body          = isset( $params['body'] ) ? sanitize_textarea_field( (string) $params['body'] ) : '';
		$telegram_html = isset( $params['telegram_html'] ) ? (string) $params['telegram_html'] : '';
		$attachments   = isset( $params['attachments'] ) && is_array( $params['attachments'] ) ? $params['attachments'] : array();

		if ( '' === $subject || '' === trim( $body ) ) {
			return new WP_REST_Response(
				array(
					'ok'       => false,
					'message'  => 'subject and body are required.',
					'channels' => array(
						'email'    => 'bad_request',
						'telegram' => 'bad_request',
					),
				),
				400
			);
		}

		$email_status = $this->send_admin_email( $subject, $body, $attachments );
		$tg_status    = $this->send_telegram_admins( $telegram_html ? $telegram_html : $body, $attachments );

		return new WP_REST_Response(
			array(
				'ok'       => true,
				'channels' => array(
					'email'    => $email_status,
					'telegram' => $tg_status,
				),
			),
			200
		);
	}

	/**
	 * @param string $subject     Email subject.
	 * @param string $body        Plain text body.
	 * @param array  $attachments Payload attachment refs with data_base64.
	 * @return string Status token.
	 */
	private function send_admin_email( $subject, $body, array $attachments ) {
		$to = (string) get_option( 'admin_email' );
		$to = (string) apply_filters( 'amy_public_chat_upload_admin_email', $to );
		if ( ! is_email( $to ) ) {
			return 'no_email';
		}

		$this->last_mail_error = '';

		$temp_files = array();
		$paths      = array();

		foreach ( $attachments as $item ) {
			if ( ! is_array( $item ) ) {
				continue;
			}
			$b64 = isset( $item['data_base64'] ) ? (string) $item['data_base64'] : '';
			if ( '' === $b64 ) {
				continue;
			}
			$raw = base64_decode( $b64, true );
			if ( false === $raw || '' === $raw ) {
				continue;
			}
			$filename = isset( $item['filename'] ) ? sanitize_file_name( (string) $item['filename'] ) : 'upload.jpg';
			if ( '' === $filename ) {
				$filename = 'upload.jpg';
			}
			$tmp = wp_tempnam( $filename );
			if ( ! $tmp ) {
				continue;
			}
			// phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_file_put_contents
			if ( false === file_put_contents( $tmp, $raw ) ) {
				wp_delete_file( $tmp );
				continue;
			}
			$temp_files[] = $tmp;
			$paths[]      = $tmp;
		}

		$headers = array( 'Content-Type: text/plain; charset=UTF-8' );
		$ok      = wp_mail( $to, $subject, $body, $headers, $paths );

		foreach ( $temp_files as $path ) {
			wp_delete_file( $path );
		}

		if ( ! $ok ) {
			return $this->last_mail_error ? 'wp_mail_failed' : 'wp_mail_false';
		}
		return 'sent';
	}

	/**
	 * Notify each whitelisted Telegram admin.
	 *
	 * @param string $text        Telegram HTML body.
	 * @param array  $attachments Optional base64 image for sendPhoto.
	 * @return string Status token.
	 */
	private function send_telegram_admins( $text, array $attachments ) {
		if ( ! $this->settings->is_telegram_enabled() ) {
			return 'disabled';
		}

		$list = $this->telegram->get_whitelist();
		if ( empty( $list ) ) {
			return 'no_admins';
		}

		$photo_path = null;

		foreach ( $attachments as $item ) {
			if ( ! is_array( $item ) ) {
				continue;
			}
			$b64 = isset( $item['data_base64'] ) ? (string) $item['data_base64'] : '';
			if ( '' === $b64 ) {
				continue;
			}
			$raw = base64_decode( $b64, true );
			if ( false === $raw || strlen( $raw ) > self::MAX_TELEGRAM_PHOTO_BYTES ) {
				continue;
			}
			$ctype = isset( $item['content_type'] ) ? (string) $item['content_type'] : '';
			if ( '' !== $ctype && 0 !== strpos( $ctype, 'image/' ) ) {
				continue;
			}
			$tmp = wp_tempnam( 'amy-tg-upload.jpg' );
			if ( ! $tmp ) {
				continue;
			}
			// phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_file_put_contents
			if ( false === file_put_contents( $tmp, $raw ) ) {
				wp_delete_file( $tmp );
				continue;
			}
			$photo_path = $tmp;
			break;
		}

		$sent_any = false;
		$failed   = false;

		foreach ( $list as $row ) {
			if ( ! is_array( $row ) || empty( $row['telegram_id'] ) ) {
				continue;
			}
			$chat_id = (int) $row['telegram_id'];
			if ( $chat_id <= 0 ) {
				continue;
			}

			$result = $this->telegram->send_message_to_chat( $chat_id, $text, true );
			if ( empty( $result['ok'] ) ) {
				$failed = true;
				continue;
			}
			$sent_any = true;

			if ( $photo_path ) {
				$caption = __( 'Image attached to admin email.', 'amy-agent' );
				$photo   = $this->telegram->send_photo_to_chat( $chat_id, $photo_path, $caption, false );
				if ( empty( $photo['ok'] ) ) {
					$failed = true;
				}
			} elseif ( ! empty( $attachments ) ) {
				$this->telegram->send_message_to_chat(
					$chat_id,
					__( '(Larger image attached to admin email.)', 'amy-agent' ),
					false
				);
			}
		}

		if ( $photo_path ) {
			wp_delete_file( $photo_path );
		}

		if ( ! $sent_any ) {
			return $failed ? 'send_failed' : 'no_admins';
		}
		return $failed ? 'partial' : 'sent';
	}
}
