<?php
/**
 * Private Telegram Admin Bot — webhook, Bot API proxy, and admin AJAX.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Telegram Admin Bot (WordPress-owned token, webhook secret, whitelist).
 */
class Amy_Telegram {

	const NONCE_ACTION = 'amy_agent_telegram';

	const OPTION_WEBHOOK_SECRET    = 'amy_agent_telegram_webhook_secret';
	const OPTION_BOT_USERNAME      = 'amy_agent_telegram_bot_username';
	const OPTION_WEBHOOK_CONNECTED = 'amy_agent_telegram_webhook_connected';
	const OPTION_CHATS             = 'amy_agent_telegram_chats';

	const TRANSIENT_UPDATES     = 'amy_tg_update_ids';
	const TRANSIENT_RATE_USER    = 'amy_tg_rate_';
	const TRANSIENT_DENY_NOTICE  = 'amy_tg_deny_';
	const TRANSIENT_SLOW_NOTICE  = 'amy_tg_slow_';
	const TRANSIENT_CONNECT_CODE = 'amy_tg_connect_';

	const MAX_MESSAGE_LENGTH = 4000;
	const RATE_LIMIT_PER_MIN = 20;
	const CONNECT_CODE_TTL   = 900; // 15 minutes.

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @var Amy_Api_Client
	 */
	private $api_client;

	/**
	 * @param Amy_Settings   $settings   Plugin settings.
	 * @param Amy_Api_Client $api_client Service client.
	 */
	public function __construct( Amy_Settings $settings, Amy_Api_Client $api_client ) {
		$this->settings   = $settings;
		$this->api_client = $api_client;
	}

	/**
	 * Register REST route and admin-ajax handlers.
	 */
	public function register() {
		add_action( 'rest_api_init', array( $this, 'register_rest_routes' ) );
		add_action( 'wp_ajax_amy_telegram_connect', array( $this, 'ajax_connect' ) );
		add_action( 'wp_ajax_amy_telegram_disconnect', array( $this, 'ajax_disconnect' ) );
		add_action( 'wp_ajax_amy_telegram_status', array( $this, 'ajax_status' ) );
		add_action( 'wp_ajax_amy_telegram_test', array( $this, 'ajax_test' ) );
		add_action( 'wp_ajax_amy_telegram_user_link_start', array( $this, 'ajax_user_link_start' ) );
		add_action( 'wp_ajax_amy_telegram_user_unlink', array( $this, 'ajax_user_unlink' ) );
	}

	/**
	 * Register webhook REST route.
	 */
	public function register_rest_routes() {
		register_rest_route(
			'amy-agent/v1',
			'/telegram/webhook',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'handle_webhook' ),
				'permission_callback' => array( $this, 'verify_webhook_secret' ),
			)
		);
	}

	/**
	 * @param WP_REST_Request $request Incoming webhook.
	 * @return true|WP_Error
	 */
	public function verify_webhook_secret( $request ) {
		$stored = (string) get_option( self::OPTION_WEBHOOK_SECRET, '' );
		if ( '' === $stored ) {
			return new WP_Error( 'amy_telegram_forbidden', '', array( 'status' => 403 ) );
		}
		$header = $request->get_header( 'x-telegram-bot-api-secret-token' );
		if ( ! is_string( $header ) || '' === $header || ! hash_equals( $stored, $header ) ) {
			return new WP_Error( 'amy_telegram_forbidden', '', array( 'status' => 403 ) );
		}
		return true;
	}

	/**
	 * Shared gate: capability + nonce.
	 */
	private function guard() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to manage Telegram.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( self::NONCE_ACTION, 'nonce' );
	}

	/**
	 * @return string Bot token from options (empty if unset).
	 */
	private function get_bot_token() {
		return trim( (string) get_option( Amy_Settings::OPTION_TELEGRAM_TOKEN, '' ) );
	}

	/**
	 * @return bool
	 */
	private function is_telegram_enabled() {
		return '1' === (string) get_option( Amy_Settings::OPTION_TELEGRAM_ENABLED, '0' );
	}

	/**
	 * @return array<int, array{telegram_id:int,label:string,wp_user_id:int}>
	 */
	public function get_whitelist() {
		$rows = get_option( Amy_Settings::OPTION_TELEGRAM_ADMINS, array() );
		return is_array( $rows ) ? $rows : array();
	}

	/**
	 * @param int $telegram_id Telegram user id.
	 * @return array{telegram_id:int,label:string,wp_user_id:int}|null
	 */
	private function find_whitelist_row( $telegram_id ) {
		$telegram_id = (int) $telegram_id;
		foreach ( $this->get_whitelist() as $row ) {
			if ( ! is_array( $row ) ) {
				continue;
			}
			if ( (int) ( $row['telegram_id'] ?? 0 ) === $telegram_id ) {
				return array(
					'telegram_id' => (int) $row['telegram_id'],
					'label'         => (string) ( $row['label'] ?? '' ),
					'wp_user_id'    => (int) ( $row['wp_user_id'] ?? 0 ),
				);
			}
		}
		return null;
	}

	/**
	 * @return string
	 */
	private function generate_webhook_secret() {
		$chars  = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-';
		$secret = '';
		$max    = strlen( $chars ) - 1;
		for ( $i = 0; $i < 32; $i++ ) {
			$secret .= $chars[ wp_rand( 0, $max ) ];
		}
		return $secret;
	}

	/**
	 * Call Telegram Bot API (never logs URL or token).
	 *
	 * @param string     $method API method name.
	 * @param array|null $body   JSON body.
	 * @return array{ok:bool,status:int,data:array|null,error:string|null}
	 */
	private function telegram_api_request( $method, $body = null ) {
		$token = $this->get_bot_token();
		if ( '' === $token ) {
			return array(
				'ok'     => false,
				'status' => 0,
				'data'   => null,
				'error'  => __( 'Bot token is not configured.', 'amy-agent' ),
			);
		}

		$url = 'https://api.telegram.org/bot' . $token . '/' . rawurlencode( (string) $method );

		$args = array(
			'timeout' => 15,
			'headers' => array(
				'Content-Type' => 'application/json; charset=utf-8',
			),
		);
		if ( null !== $body ) {
			$args['body'] = wp_json_encode( $body );
		}

		$response = wp_remote_post( $url, $args );
		if ( is_wp_error( $response ) ) {
			return array(
				'ok'     => false,
				'status' => 0,
				'data'   => null,
				'error'  => $response->get_error_message(),
			);
		}

		$status = (int) wp_remote_retrieve_response_code( $response );
		$raw    = wp_remote_retrieve_body( $response );
		$data   = json_decode( $raw, true );
		$ok     = is_array( $data ) && ! empty( $data['ok'] );

		return array(
			'ok'     => $ok,
			'status' => $status,
			'data'   => is_array( $data ) ? $data : null,
			'error'  => $ok ? null : ( is_array( $data ) && ! empty( $data['description'] ) ? (string) $data['description'] : __( 'Telegram API request failed.', 'amy-agent' ) ),
		);
	}

	/**
	 * Connect webhook (uses saved token only).
	 */
	public function ajax_connect() {
		$this->guard();

		if ( ! is_ssl() ) {
			wp_send_json_error(
				array(
					'message' => __( 'Telegram webhooks require HTTPS. Ask your host for HTTPS, then reload Amy → Settings → Telegram.', 'amy-agent' ),
				),
				400
			);
		}

		$token = $this->get_bot_token();
		if ( '' === $token ) {
			wp_send_json_error(
				array(
					'message' => __( 'Bot token is missing. Amy → Settings → Telegram → paste token from BotFather → Save settings.', 'amy-agent' ),
				),
				400
			);
		}

		$me = $this->telegram_api_request( 'getMe' );
		if ( ! $me['ok'] || ! is_array( $me['data'] ) || empty( $me['data']['result'] ) ) {
			wp_send_json_error(
				array( 'message' => $me['error'] ? $me['error'] : __( 'Could not validate the bot token.', 'amy-agent' ) ),
				502
			);
		}

		$result   = $me['data']['result'];
		$username = isset( $result['username'] ) ? sanitize_text_field( (string) $result['username'] ) : '';
		update_option( self::OPTION_BOT_USERNAME, $username, false );

		$secret = (string) get_option( self::OPTION_WEBHOOK_SECRET, '' );
		if ( '' === $secret ) {
			$secret = $this->generate_webhook_secret();
			update_option( self::OPTION_WEBHOOK_SECRET, $secret, false );
		}

		$webhook_url = rest_url( 'amy-agent/v1/telegram/webhook' );
		$set         = $this->telegram_api_request(
			'setWebhook',
			array(
				'url'                  => $webhook_url,
				'secret_token'         => $secret,
				'allowed_updates'      => array( 'message' ),
				'drop_pending_updates' => true,
				'max_connections'      => 5,
			)
		);

		if ( ! $set['ok'] ) {
			update_option( self::OPTION_WEBHOOK_CONNECTED, '0', false );
			wp_send_json_error(
				array( 'message' => $set['error'] ? $set['error'] : __( 'setWebhook failed.', 'amy-agent' ) ),
				502
			);
		}

		update_option( self::OPTION_WEBHOOK_CONNECTED, '1', false );

		wp_send_json_success(
			array(
				'username'    => $username,
				'webhook_url' => $webhook_url,
				'message'     => __( 'Telegram webhook connected.', 'amy-agent' ),
			)
		);
	}

	/**
	 * Disconnect webhook.
	 */
	public function ajax_disconnect() {
		$this->guard();

		$this->telegram_api_request( 'deleteWebhook', array( 'drop_pending_updates' => true ) );
		update_option( self::OPTION_CHATS, array(), false );
		update_option( self::OPTION_WEBHOOK_CONNECTED, '0', false );

		wp_send_json_success(
			array(
				'message' => __( 'Telegram webhook disconnected and chat mappings cleared.', 'amy-agent' ),
			)
		);
	}

	/**
	 * Whether Connect last succeeded (local flag; no live Telegram probe).
	 *
	 * @return bool
	 */
	public static function is_webhook_connected() {
		return '1' === (string) get_option( self::OPTION_WEBHOOK_CONNECTED, '0' );
	}

	/**
	 * Webhook + bot status summary (no secrets).
	 */
	public function ajax_status() {
		$this->guard();

		$token    = $this->get_bot_token();
		$enabled  = $this->is_telegram_enabled();
		$username = (string) get_option( self::OPTION_BOT_USERNAME, '' );

		if ( '' === $token ) {
			update_option( self::OPTION_WEBHOOK_CONNECTED, '0', false );
			wp_send_json_success(
				array(
					'enabled'       => $enabled,
					'has_token'     => false,
					'username'      => '',
					'webhook_state' => 'not_connected',
					'webhook_url'   => '',
					'pending'       => null,
					'last_error'    => null,
				)
			);
		}

		$me = $this->telegram_api_request( 'getMe' );
		if ( $me['ok'] && is_array( $me['data'] ) && ! empty( $me['data']['result']['username'] ) ) {
			$username = sanitize_text_field( (string) $me['data']['result']['username'] );
			update_option( self::OPTION_BOT_USERNAME, $username, false );
		}

		$info            = $this->telegram_api_request( 'getWebhookInfo' );
		$expected        = rest_url( 'amy-agent/v1/telegram/webhook' );
		$webhook_state   = 'not_connected';
		$actual_url      = '';
		$pending         = null;
		$last_error      = null;

		if ( $info['ok'] && is_array( $info['data'] ) && ! empty( $info['data']['result'] ) ) {
			$wh         = $info['data']['result'];
			$actual_url = isset( $wh['url'] ) ? (string) $wh['url'] : '';
			$pending    = isset( $wh['pending_update_count'] ) ? (int) $wh['pending_update_count'] : 0;
			$last_error = ! empty( $wh['last_error_message'] ) ? sanitize_text_field( (string) $wh['last_error_message'] ) : null;

			if ( '' !== $actual_url && untrailingslashit( $actual_url ) === untrailingslashit( $expected ) ) {
				$webhook_state = $last_error ? 'error' : 'connected';
			} elseif ( '' !== $last_error ) {
				$webhook_state = 'error';
			}
		}

		update_option(
			self::OPTION_WEBHOOK_CONNECTED,
			'connected' === $webhook_state ? '1' : '0',
			false
		);

		wp_send_json_success(
			array(
				'enabled'       => $enabled,
				'has_token'     => true,
				'username'      => $username,
				'webhook_state' => $webhook_state,
				'webhook_url'   => $actual_url,
				'pending'       => $pending,
				'last_error'    => $last_error,
			)
		);
	}

	/**
	 * My Profile: mint a short-lived /start connect_<code> link for assignees.
	 */
	public function ajax_user_link_start() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( self::NONCE_ACTION, 'nonce' );

		if ( ! $this->is_telegram_enabled() || '' === $this->get_bot_token() ) {
			wp_send_json_error(
				array(
					'message' => __( 'Telegram bot is not enabled. Amy → Settings → Telegram → Enable Telegram Admin Bot, paste a BotFather token, Save settings, then Connect.', 'amy-agent' ),
				),
				400
			);
		}

		$username = (string) get_option( self::OPTION_BOT_USERNAME, '' );
		if ( '' === $username ) {
			$me = $this->telegram_api_request( 'getMe' );
			if ( $me['ok'] && is_array( $me['data'] ) && ! empty( $me['data']['result']['username'] ) ) {
				$username = sanitize_text_field( (string) $me['data']['result']['username'] );
				update_option( self::OPTION_BOT_USERNAME, $username, false );
			}
		}
		if ( '' === $username ) {
			wp_send_json_error(
				array(
					'message' => __( 'Connect the bot webhook in Settings → Telegram first. Click Connect (HTTPS required).', 'amy-agent' ),
				),
				400
			);
		}

		$code = strtolower( wp_generate_password( 10, false, false ) );
		$user_id = get_current_user_id();
		set_transient( self::TRANSIENT_CONNECT_CODE . $code, (int) $user_id, self::CONNECT_CODE_TTL );

		$deep_link = 'https://t.me/' . rawurlencode( $username ) . '?start=connect_' . rawurlencode( $code );

		wp_send_json_success(
			array(
				'code'      => $code,
				'username'  => $username,
				'deep_link' => $deep_link,
				'expires'   => self::CONNECT_CODE_TTL,
				'message'   => __( 'Open the bot link and tap Start (or send the /start command shown).', 'amy-agent' ),
			)
		);
	}

	/**
	 * My Profile: clear assignee chat-id link.
	 */
	public function ajax_user_unlink() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( self::NONCE_ACTION, 'nonce' );
		Amy_Task_Notify::unlink_user_chat( get_current_user_id() );
		wp_send_json_success(
			array( 'message' => __( 'Telegram unlinked for task alerts.', 'amy-agent' ) )
		);
	}

	/**
	 * Send test message to each whitelisted admin.
	 */
	public function ajax_test() {
		$this->guard();

		if ( ! $this->is_telegram_enabled() || '' === $this->get_bot_token() ) {
			wp_send_json_error(
				array(
					'message' => __( 'Telegram bot is not ready. Amy → Settings → Telegram → Enable Telegram Admin Bot, paste token from BotFather → Save settings, then Connect.', 'amy-agent' ),
				),
				400
			);
		}

		$results = array();
		$text    = __( '✅ Amy Telegram bot is connected.', 'amy-agent' );

		foreach ( $this->get_whitelist() as $row ) {
			if ( ! is_array( $row ) || empty( $row['telegram_id'] ) ) {
				continue;
			}
			$chat_id = (int) $row['telegram_id'];
			$label   = (string) ( $row['label'] ?? '' );
			$sent    = $this->send_message( $chat_id, $text, false );
			$results[] = array(
				'telegram_id' => $chat_id,
				'label'       => $label,
				'ok'          => $sent['ok'],
				'error'       => $sent['ok'] ? null : ( $sent['error'] ?? __( 'Send failed.', 'amy-agent' ) ),
			);
		}

		wp_send_json_success(
			array(
				'results' => $results,
			)
		);
	}

	/**
	 * Telegram webhook entry.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_webhook( $request ) {
		if ( ! $this->is_telegram_enabled() || '' === $this->get_bot_token() ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$body = $request->get_json_params();
		if ( ! is_array( $body ) ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$update_id = isset( $body['update_id'] ) ? (int) $body['update_id'] : 0;
		if ( $update_id > 0 && $this->is_duplicate_update( $update_id ) ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		if ( empty( $body['message'] ) || ! is_array( $body['message'] ) ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$message = $body['message'];
		$chat    = isset( $message['chat'] ) && is_array( $message['chat'] ) ? $message['chat'] : array();
		$from    = isset( $message['from'] ) && is_array( $message['from'] ) ? $message['from'] : array();

		if ( ( $chat['type'] ?? '' ) !== 'private' || empty( $from['id'] ) ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$chat_id     = (int) $chat['id'];
		$telegram_id = (int) $from['id'];
		$text        = isset( $message['text'] ) ? (string) $message['text'] : '';

		// Self-serve assignee connect: /start connect_<code> (before whitelist gate).
		if ( '' !== $text && $this->maybe_handle_connect_start( $chat_id, $telegram_id, $text ) ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$identity = $this->resolve_inbound_identity( $telegram_id );
		if ( null === $identity ) {
			$this->maybe_send_unlisted_notice( $chat_id, $telegram_id );
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$wp_user = get_userdata( $identity['wp_user_id'] );
		if ( ! $wp_user || ! user_can( $wp_user, 'manage_options' ) ) {
			$this->send_message(
				$chat_id,
				__( 'Your WordPress link is no longer valid.', 'amy-agent' ),
				false
			);
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$whitelist_row = array(
			'telegram_id' => $telegram_id,
			'label'       => $identity['label'],
			'wp_user_id'  => (int) $wp_user->ID,
		);

		if ( $this->is_rate_limited( $telegram_id ) ) {
			$slow_key = self::TRANSIENT_SLOW_NOTICE . $telegram_id;
			if ( ! get_transient( $slow_key ) ) {
				set_transient( $slow_key, '1', MINUTE_IN_SECONDS );
				$this->send_message( $chat_id, __( 'Slow down a little 🙂', 'amy-agent' ), false );
			}
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}
		$this->bump_rate_limit( $telegram_id );

		if ( '' === $text ) {
			$this->send_message(
				$chat_id,
				__( 'I can only read text messages for now.', 'amy-agent' ),
				false
			);
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		if ( str_starts_with( $text, '/' ) ) {
			$this->handle_command(
				$chat_id,
				$text,
				$whitelist_row,
				$wp_user,
				(bool) $identity['admin_chat']
			);
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		// Mid-progress free-text reply → progress note (P1); else Admin Bot chat.
		if ( $this->maybe_save_progress_note( $chat_id, $text, $wp_user ) ) {
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		if ( ! $identity['admin_chat'] ) {
			$this->send_message(
				$chat_id,
				__( 'Thanks — your message was received. For Amy chat, ask an admin to add you to the Telegram whitelist in Settings.', 'amy-agent' ),
				false
			);
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$this->handle_plain_text( $chat_id, $text, $whitelist_row, $wp_user );

		return new WP_REST_Response( array( 'ok' => true ), 200 );
	}

	/**
	 * Whitelist admin row or assignee user-meta link.
	 *
	 * @param int $telegram_id Telegram user id.
	 * @return array{wp_user_id:int,label:string,admin_chat:bool}|null
	 */
	private function resolve_inbound_identity( $telegram_id ) {
		$row = $this->find_whitelist_row( $telegram_id );
		if ( null !== $row ) {
			return array(
				'wp_user_id'  => (int) $row['wp_user_id'],
				'label'       => (string) $row['label'],
				'admin_chat'  => true,
			);
		}

		$users = get_users(
			array(
				'meta_key'   => Amy_Task_Notify::USER_META_CHAT_ID,
				'meta_value' => (string) (int) $telegram_id,
				'number'     => 1,
				'fields'     => array( 'ID', 'display_name' ),
			)
		);
		if ( empty( $users ) ) {
			return null;
		}
		$user = $users[0];
		return array(
			'wp_user_id' => (int) $user->ID,
			'label'      => (string) $user->display_name,
			'admin_chat' => false,
		);
	}

	/**
	 * @param int    $chat_id     Chat id.
	 * @param int    $telegram_id Telegram user id.
	 * @param string $text        Message text.
	 * @return bool True if handled as connect.
	 */
	private function maybe_handle_connect_start( $chat_id, $telegram_id, $text ) {
		$parts = preg_split( '/\s+/', trim( $text ), 2 );
		$cmd   = strtolower( (string) ( $parts[0] ?? '' ) );
		$arg   = isset( $parts[1] ) ? trim( (string) $parts[1] ) : '';

		// Deep link: /start connect_<code>
		if ( '/start' === $cmd && str_starts_with( $arg, 'connect_' ) ) {
			$code = substr( $arg, strlen( 'connect_' ) );
			return $this->complete_connect_code( $chat_id, $telegram_id, $code );
		}
		return false;
	}

	/**
	 * @param int    $chat_id     Chat id.
	 * @param int    $telegram_id Telegram user id.
	 * @param string $code        Connect code.
	 * @return bool
	 */
	private function complete_connect_code( $chat_id, $telegram_id, $code ) {
		$code = strtolower( preg_replace( '/[^a-z0-9]/i', '', (string) $code ) );
		if ( '' === $code ) {
			return false;
		}
		$key     = self::TRANSIENT_CONNECT_CODE . $code;
		$user_id = (int) get_transient( $key );
		if ( $user_id < 1 ) {
			$this->send_message(
				$chat_id,
				__( 'That connect link expired or is invalid. Generate a new one from Amy → My Profile.', 'amy-agent' ),
				false
			);
			return true;
		}
		delete_transient( $key );
		Amy_Task_Notify::link_user_chat( $user_id, $telegram_id );
		$wp_user = get_userdata( $user_id );
		$name    = $wp_user ? $wp_user->display_name : ( 'user #' . $user_id );
		$this->send_message(
			$chat_id,
			sprintf(
				/* translators: %s: WordPress display name */
				__( 'Linked to %s. You will receive task assign / progress / expiry alerts here when the bot is enabled.', 'amy-agent' ),
				$name
			),
			false
		);
		return true;
	}

	/**
	 * If a mid-progress ask is pending for this user, store free text as a note.
	 *
	 * @param int     $chat_id Chat id.
	 * @param string  $text    Reply text.
	 * @param WP_User $wp_user Linked user.
	 * @return bool True when consumed as progress note.
	 */
	private function maybe_save_progress_note( $chat_id, $text, $wp_user ) {
		if ( ! $this->settings->is_service_configured() ) {
			return false;
		}
		$result = $this->api_client->consume_telegram_progress_reply(
			(int) $wp_user->ID,
			$text
		);
		if ( ! $result['ok'] || ! is_array( $result['body'] ) ) {
			return false;
		}
		if ( empty( $result['body']['saved'] ) ) {
			return false;
		}
		$this->send_message(
			$chat_id,
			__( 'Thanks — your progress update was saved on the task.', 'amy-agent' ),
			false
		);
		return true;
	}

	/**
	 * @param int $update_id Telegram update id.
	 * @return bool
	 */
	private function is_duplicate_update( $update_id ) {
		$ids = get_transient( self::TRANSIENT_UPDATES );
		if ( ! is_array( $ids ) ) {
			$ids = array();
		}
		if ( in_array( $update_id, $ids, true ) ) {
			return true;
		}
		$ids[] = $update_id;
		if ( count( $ids ) > 50 ) {
			$ids = array_slice( $ids, -50 );
		}
		set_transient( self::TRANSIENT_UPDATES, $ids, DAY_IN_SECONDS );
		return false;
	}

	/**
	 * @param int $chat_id     Chat id.
	 * @param int $telegram_id User id for message text.
	 */
	private function maybe_send_unlisted_notice( $chat_id, $telegram_id ) {
		$key = self::TRANSIENT_DENY_NOTICE . $chat_id;
		if ( get_transient( $key ) ) {
			return;
		}
		set_transient( $key, '1', MINUTE_IN_SECONDS );

		$msg = sprintf(
			/* translators: %d: Telegram user id */
			__( 'This is a private bot. Your Telegram ID is %d. Ask the site admin to add it in Amy → Settings → Telegram.', 'amy-agent' ),
			$telegram_id
		);
		$this->send_message( $chat_id, $msg, false );
	}

	/**
	 * @param int $telegram_id User id.
	 * @return bool
	 */
	private function is_rate_limited( $telegram_id ) {
		$key  = self::TRANSIENT_RATE_USER . $telegram_id;
		$data = get_transient( $key );
		if ( ! is_array( $data ) ) {
			return false;
		}
		$count = (int) ( $data['count'] ?? 0 );
		return $count >= self::RATE_LIMIT_PER_MIN;
	}

	/**
	 * @param int $telegram_id User id.
	 */
	private function bump_rate_limit( $telegram_id ) {
		$key  = self::TRANSIENT_RATE_USER . $telegram_id;
		$data = get_transient( $key );
		if ( ! is_array( $data ) ) {
			$data = array( 'count' => 0 );
		}
		$data['count'] = (int) ( $data['count'] ?? 0 ) + 1;
		set_transient( $key, $data, MINUTE_IN_SECONDS );
	}

	/**
	 * @param int                                      $chat_id    Chat id.
	 * @param string                                   $text       Full message text.
	 * @param array{telegram_id:int,label:string,wp_user_id:int} $row Whitelist/assignee row.
	 * @param WP_User                                  $wp_user    Linked user.
	 * @param bool                                     $admin_chat True when Telegram whitelist allows Amy chat.
	 */
	private function handle_command( $chat_id, $text, $row, $wp_user, $admin_chat = false ) {
		$parts = preg_split( '/\s+/', trim( $text ), 2 );
		$raw_cmd = isset( $parts[0] ) ? strtolower( (string) $parts[0] ) : '';
		// Telegram may send /analytics@BotName — strip the bot suffix.
		$cmd = preg_replace( '/@.*/', '', $raw_cmd );
		$arg = isset( $parts[1] ) ? trim( (string) $parts[1] ) : '';

		if ( '/start' === $cmd || '/help' === $cmd ) {
			if ( $admin_chat ) {
				$help = __( "I'm Amy — your admin assistant. Chat here like Dashboard Chat. Commands: /analytics, /new, /whoami, /help.", 'amy-agent' );
			} else {
				$help = __( "I'm Amy. Commands: /whoami, /help. For Amy chat + /analytics, ask an admin to add you to the Telegram whitelist in Settings.", 'amy-agent' );
			}
			$this->send_message( $chat_id, $help, false );
			return;
		}

		if ( '/whoami' === $cmd ) {
			$line = sprintf(
				"Telegram ID: %d\nWordPress: %s (%s)",
				(int) $row['telegram_id'],
				$wp_user->display_name,
				$wp_user->user_email
			);
			$this->send_message( $chat_id, $line, false );
			return;
		}

		if ( '/new' === $cmd ) {
			if ( ! $admin_chat ) {
				$this->send_message(
					$chat_id,
					__( 'Thanks — your message was received. For Amy chat, ask an admin to add you to the Telegram whitelist in Settings.', 'amy-agent' ),
					false
				);
				return;
			}
			$this->clear_chat_conversation( $chat_id );
			$this->send_message( $chat_id, __( 'Started a new conversation.', 'amy-agent' ), false );
			return;
		}

		if ( '/analytics' === $cmd ) {
			if ( ! $admin_chat ) {
				$this->send_message(
					$chat_id,
					__( 'Thanks — your message was received. For Amy chat, ask an admin to add you to the Telegram whitelist in Settings.', 'amy-agent' ),
					false
				);
				return;
			}
			if ( '' !== $arg ) {
				// Custom follow-up after the slash → same admin chat brain (fresh snapshot).
				$this->handle_plain_text(
					$chat_id,
					sprintf(
						/* translators: %s: admin Analytics follow-up question */
						__( 'Regarding Amy Analytics: %s', 'amy-agent' ),
						$arg
					),
					$row,
					$wp_user
				);
				return;
			}
			$this->handle_analytics_slash( $chat_id );
			return;
		}

		$this->send_message( $chat_id, __( 'Unknown command. Try /help.', 'amy-agent' ), false );
	}

	/**
	 * Fresh Analytics pull for Telegram /analytics (deterministic slash reply).
	 *
	 * @param int $chat_id Telegram chat id.
	 */
	private function handle_analytics_slash( $chat_id ) {
		if ( ! $this->settings->is_ready() ) {
			$this->send_message(
				$chat_id,
				__( 'Analytics unavailable right now. Check Amy → Settings → Connection / Overview.', 'amy-agent' ),
				false
			);
			return;
		}

		$result = $this->api_client->get_analytics_summary( true );
		if ( ! $result['ok'] || ! is_array( $result['body'] ) ) {
			$this->send_message(
				$chat_id,
				__( 'Analytics unavailable right now. Check Amy → Settings → Connection / Overview.', 'amy-agent' ),
				false
			);
			return;
		}

		$body = $result['body'];
		$reply = '';
		if ( ! empty( $body['slash_reply'] ) && is_string( $body['slash_reply'] ) ) {
			$reply = $body['slash_reply'];
		} elseif ( ! empty( $body['summary'] ) && is_string( $body['summary'] ) ) {
			$reply = $body['summary'];
		}

		if ( '' === $reply ) {
			$this->send_message(
				$chat_id,
				__( 'Analytics unavailable right now. Check Amy → Settings → Connection / Overview.', 'amy-agent' ),
				false
			);
			return;
		}

		// Slash replies may include Markdown from the service (recommendations).
		$this->send_message( $chat_id, $reply, true );
	}

	/**
	 * @param int                                      $chat_id Chat id.
	 * @param string                                   $text    Message text.
	 * @param array{telegram_id:int,label:string,wp_user_id:int} $row     Whitelist row.
	 * @param WP_User                                  $wp_user Linked user.
	 */
	private function handle_plain_text( $chat_id, $text, $row, $wp_user ) {
		if ( ! $this->settings->is_ready() ) {
			$this->send_message(
				$chat_id,
				__( 'Amy could not answer right now, try again in a moment.', 'amy-agent' ),
				false
			);
			return;
		}

		$conversation_id = $this->get_chat_conversation_id( $chat_id );
		if ( null !== $conversation_id ) {
			$check = $this->api_client->get_conversation(
				$conversation_id,
				$wp_user->ID,
				true
			);
			if ( 404 === (int) $check['status_code'] ) {
				$conversation_id = null;
			}
		}

		if ( null === $conversation_id ) {
			$title = 'Telegram: ' . ( '' !== $row['label'] ? $row['label'] : $wp_user->display_name );
			$created = $this->api_client->create_conversation( $wp_user->ID, 'admin', $title );
			if ( ! $created['ok'] || ! is_array( $created['body'] ) || empty( $created['body']['id'] ) ) {
				$this->send_message(
					$chat_id,
					__( 'Amy could not answer right now, try again in a moment.', 'amy-agent' ),
					false
				);
				return;
			}
			$conversation_id = (string) $created['body']['id'];
			$this->set_chat_conversation( $chat_id, $conversation_id );
		}

		$this->telegram_api_request(
			'sendChatAction',
			array(
				'chat_id' => $chat_id,
				'action'  => 'typing',
			)
		);

		$session_id = 'tg-' . $chat_id;
		$payload    = array(
			'session_id'      => $session_id,
			'mode'            => 'admin',
			'conversation_id' => $conversation_id,
			'wp_user_id'      => (int) $wp_user->ID,
			'is_full_admin'   => true,
			'wp_user_name'    => $wp_user->display_name,
			'wp_user_email'   => $wp_user->user_email,
			'messages'        => array(
				array(
					'role'    => 'user',
					'content' => $text,
				),
			),
		);

		$result = $this->api_client->chat( $payload );
		if ( ! $result['ok'] || ! is_array( $result['body'] ) ) {
			$this->send_message(
				$chat_id,
				__( 'Amy could not answer right now, try again in a moment.', 'amy-agent' ),
				false
			);
			return;
		}

		$reply_text = '';
		if ( ! empty( $result['body']['reply']['content'] ) ) {
			$reply_text = (string) $result['body']['reply']['content'];
		} elseif ( ! empty( $result['body']['message'] ) ) {
			$reply_text = (string) $result['body']['message'];
		}

		if ( '' === trim( $reply_text ) ) {
			$this->send_message(
				$chat_id,
				__( 'Amy could not answer right now, try again in a moment.', 'amy-agent' ),
				false
			);
			return;
		}

		$this->send_message( $chat_id, $reply_text, true );
	}

	/**
	 * @param int $chat_id Chat id.
	 * @return string|null
	 */
	private function get_chat_conversation_id( $chat_id ) {
		$map = get_option( self::OPTION_CHATS, array() );
		if ( ! is_array( $map ) ) {
			return null;
		}
		$key = (string) (int) $chat_id;
		return isset( $map[ $key ] ) && '' !== (string) $map[ $key ] ? (string) $map[ $key ] : null;
	}

	/**
	 * @param int    $chat_id         Chat id.
	 * @param string $conversation_id Conversation id.
	 */
	private function set_chat_conversation( $chat_id, $conversation_id ) {
		$map         = get_option( self::OPTION_CHATS, array() );
		if ( ! is_array( $map ) ) {
			$map = array();
		}
		$map[ (string) (int) $chat_id ] = (string) $conversation_id;
		update_option( self::OPTION_CHATS, $map, false );
	}

	/**
	 * @param int $chat_id Chat id.
	 */
	private function clear_chat_conversation( $chat_id ) {
		$map = get_option( self::OPTION_CHATS, array() );
		if ( ! is_array( $map ) ) {
			return;
		}
		unset( $map[ (string) (int) $chat_id ] );
		update_option( self::OPTION_CHATS, $map, false );
	}

	/**
	 * Split long text for Telegram size limits.
	 *
	 * @param string $text Raw text.
	 * @return string[]
	 */
	public static function split_message_chunks( $text ) {
		$text = (string) $text;
		if ( strlen( $text ) <= self::MAX_MESSAGE_LENGTH ) {
			return array( $text );
		}

		$chunks  = array();
		$rest    = $text;
		$max     = self::MAX_MESSAGE_LENGTH;

		while ( strlen( $rest ) > $max ) {
			$slice = substr( $rest, 0, $max );
			$break = max(
				strrpos( $slice, "\n\n" ),
				strrpos( $slice, "\n" ),
				strrpos( $slice, ' ' )
			);
			if ( false === $break || $break < (int) ( $max * 0.5 ) ) {
				$break = $max;
			} else {
				++$break;
			}
			$chunks[] = substr( $rest, 0, $break );
			$rest     = substr( $rest, $break );
		}
		if ( '' !== $rest ) {
			$chunks[] = $rest;
		}
		return $chunks;
	}

	/**
	 * Convert assistant Markdown to Telegram HTML (parse_mode HTML).
	 *
	 * Telegram supports only a small HTML subset — no headings or list tags —
	 * so Markdown headings become bold lines and bullets become "• " prefixes.
	 * Raw Markdown markers (#, leading * / -) must not reach the final text.
	 *
	 * @param string $text Markdown-ish text.
	 * @return string
	 */
	public static function markdown_to_telegram_html( $text ) {
		$text = (string) $text;
		$text = htmlspecialchars( $text, ENT_NOQUOTES | ENT_SUBSTITUTE, 'UTF-8' );

		$placeholders = array();
		$store        = static function ( $html ) use ( &$placeholders ) {
			$key                    = "\x00TG" . count( $placeholders ) . "\x00";
			$placeholders[ $key ] = $html;
			return $key;
		};

		$text = preg_replace_callback(
			'/```[\w-]*\r?\n([\s\S]*?)```/',
			static function ( $m ) use ( $store ) {
				return $store( '<pre>' . $m[1] . '</pre>' );
			},
			$text
		);

		$text = preg_replace_callback(
			'/`([^`]+)`/',
			static function ( $m ) use ( $store ) {
				return $store( '<code>' . $m[1] . '</code>' );
			},
			$text
		);

		$text = preg_replace_callback(
			'/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/',
			static function ( $m ) use ( $store ) {
				$url = esc_url( $m[2], array( 'http', 'https' ) );
				if ( '' === $url ) {
					return $m[0];
				}
				return $store( '<a href="' . $url . '">' . $m[1] . '</a>' );
			},
			$text
		);

		$lines   = explode( "\n", $text );
		$out     = array();
		$bq_buf  = array();
		$flush_bq = static function () use ( &$bq_buf, &$out ) {
			if ( empty( $bq_buf ) ) {
				return;
			}
			$out[]  = '<blockquote>' . implode( "\n", $bq_buf ) . '</blockquote>';
			$bq_buf = array();
		};

		foreach ( $lines as $line ) {
			// htmlspecialchars turns ">" into "&gt;" before this pass.
			if ( preg_match( '/^&gt;\s?(.*)$/', $line, $m ) ) {
				$bq_buf[] = $m[1];
				continue;
			}
			$flush_bq();

			if ( preg_match( '/^#{1,6}\s*(.+)$/', $line, $m ) ) {
				$title = trim( $m[1] );
				$title = preg_replace( '/\*\*([^*]+)\*\*/', '$1', $title );
				$out[] = '<b>' . $title . '</b>';
				continue;
			}
			if ( preg_match( '/^#{1,6}\s*$/', $line ) ) {
				continue;
			}
			if ( preg_match( '/^[\*\-]\s+(.+)$/', $line, $m ) ) {
				$out[] = '• ' . $m[1];
				continue;
			}
			$out[] = $line;
		}
		$flush_bq();
		$text = implode( "\n", $out );

		$text = preg_replace( '/\*\*([^*]+)\*\*/', '<b>$1</b>', $text );
		$text = preg_replace( '/(?<!\*)\*([^*\n]+)\*(?!\*)/', '<i>$1</i>', $text );
		$text = preg_replace( '/\b_([^_\n]+)_\b/', '<i>$1</i>', $text );

		if ( ! empty( $placeholders ) ) {
			$text = str_replace( array_keys( $placeholders ), array_values( $placeholders ), $text );
		}

		return self::balance_telegram_html_tags( $text );
	}

	/**
	 * Close any unclosed supported tags (best-effort).
	 *
	 * @param string $html HTML fragment.
	 * @return string
	 */
	private static function balance_telegram_html_tags( $html ) {
		$tags  = array( 'b', 'i', 'code', 'pre', 'a', 'blockquote' );
		$stack = array();
		$parts = preg_split( '/(<\/?[^>]+>)/', $html, -1, PREG_SPLIT_DELIM_CAPTURE );
		if ( ! is_array( $parts ) ) {
			return $html;
		}

		$out = '';
		foreach ( $parts as $part ) {
			if ( preg_match( '#^</([a-z]+)>$#i', $part, $m ) ) {
				$name = strtolower( $m[1] );
				if ( in_array( $name, $tags, true ) ) {
					while ( ! empty( $stack ) ) {
						$top = array_pop( $stack );
						if ( $top === $name ) {
							break;
						}
						$out .= '</' . $top . '>';
					}
				}
				$out .= $part;
				continue;
			}
			if ( preg_match( '#^<([a-z]+)(?:\s[^>]*)?>$#i', $part, $m ) ) {
				$name = strtolower( $m[1] );
				if ( in_array( $name, $tags, true ) ) {
					$stack[] = $name;
				}
			}
			$out .= $part;
		}
		while ( ! empty( $stack ) ) {
			$out .= '</' . array_pop( $stack ) . '>';
		}
		return $out;
	}

	/**
	 * Public send for Task Service outbound (reuses Admin Bot token).
	 *
	 * @param int    $chat_id    Chat id.
	 * @param string $text       Message body.
	 * @param bool   $allow_html Whether to use HTML parse mode.
	 * @return array{ok:bool,error:string|null}
	 */
	public function send_message_to_chat( $chat_id, $text, $allow_html = true ) {
		return $this->send_message( (int) $chat_id, (string) $text, (bool) $allow_html );
	}

	/**
	 * Send a photo to a chat (multipart Bot API).
	 *
	 * @param int    $chat_id    Chat id.
	 * @param string $file_path  Local readable image path.
	 * @param string $caption    Optional caption.
	 * @param bool   $allow_html Whether caption uses HTML parse mode.
	 * @return array{ok:bool,error:string|null}
	 */
	public function send_photo_to_chat( $chat_id, $file_path, $caption = '', $allow_html = false ) {
		$token = $this->get_bot_token();
		if ( '' === $token ) {
			return array(
				'ok'    => false,
				'error' => __( 'Bot token is not configured.', 'amy-agent' ),
			);
		}
		$file_path = (string) $file_path;
		if ( '' === $file_path || ! is_readable( $file_path ) ) {
			return array(
				'ok'    => false,
				'error' => __( 'Photo file is not readable.', 'amy-agent' ),
			);
		}
		if ( ! class_exists( 'CURLFile' ) ) {
			return array(
				'ok'    => false,
				'error' => __( 'CURLFile is required for photo uploads.', 'amy-agent' ),
			);
		}

		$url  = 'https://api.telegram.org/bot' . $token . '/sendPhoto';
		$post = array(
			'chat_id' => (int) $chat_id,
			'photo'   => new \CURLFile( $file_path, 'image/jpeg', basename( $file_path ) ),
		);
		$caption = trim( (string) $caption );
		if ( '' !== $caption ) {
			$post['caption'] = $caption;
			if ( $allow_html ) {
				$post['parse_mode'] = 'HTML';
			}
		}

		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_init
		$ch = curl_init( $url );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_setopt
		curl_setopt_array(
			$ch,
			array(
				CURLOPT_POST           => true,
				CURLOPT_POSTFIELDS     => $post,
				CURLOPT_RETURNTRANSFER => true,
				CURLOPT_TIMEOUT        => 30,
			)
		);
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_exec
		$raw = curl_exec( $ch );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_errno
		$errno = curl_errno( $ch );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_error
		$errstr = curl_error( $ch );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_close
		curl_close( $ch );

		if ( $errno ) {
			return array(
				'ok'    => false,
				'error' => $errstr ? $errstr : __( 'Telegram photo upload failed.', 'amy-agent' ),
			);
		}

		$data = json_decode( (string) $raw, true );
		$ok   = is_array( $data ) && ! empty( $data['ok'] );
		return array(
			'ok'    => $ok,
			'error' => $ok ? null : ( is_array( $data ) && ! empty( $data['description'] ) ? (string) $data['description'] : __( 'Telegram API request failed.', 'amy-agent' ) ),
		);
	}

	/**
	 * Send a message to a chat (HTML with plain fallback).
	 *
	 * @param int    $chat_id    Chat id.
	 * @param string $text       Message body.
	 * @param bool   $allow_html Whether to use HTML parse mode.
	 * @return array{ok:bool,error:string|null}
	 */
	/**
	 * Whether a Bot API response is a parse_mode / entities rejection.
	 *
	 * Telegram often returns HTTP 200 with JSON ``ok:false`` and
	 * ``error_code:400`` (description mentions parse entities). Checking only
	 * the HTTP status misses those and skips the HTML→safe fallback.
	 *
	 * @param array{ok:bool,status:int,data:array|null,error:string|null} $result API result.
	 * @return bool
	 */
	public static function is_telegram_parse_error( array $result ) {
		if ( ! empty( $result['ok'] ) ) {
			return false;
		}
		$error_code = 0;
		if ( isset( $result['data'] ) && is_array( $result['data'] ) && isset( $result['data']['error_code'] ) ) {
			$error_code = (int) $result['data']['error_code'];
		}
		if ( 400 === (int) $result['status'] || 400 === $error_code ) {
			return true;
		}
		$err = isset( $result['error'] ) ? strtolower( (string) $result['error'] ) : '';
		return ( false !== strpos( $err, 'parse' ) ) || ( false !== strpos( $err, 'entities' ) );
	}

	/**
	 * Drop blockquote wrappers but keep inner HTML (bold etc.) for a safer retry.
	 *
	 * @param string $html HTML from markdown_to_telegram_html().
	 * @return string
	 */
	public static function strip_telegram_blockquotes( $html ) {
		$html = (string) $html;
		$html = str_replace( array( '<blockquote>', '</blockquote>' ), '', $html );
		return $html;
	}

	private function send_message( $chat_id, $text, $allow_html ) {
		$chunks = self::split_message_chunks( $text );
		$last   = array( 'ok' => true, 'error' => null );

		foreach ( $chunks as $chunk ) {
			if ( $allow_html ) {
				$html   = self::markdown_to_telegram_html( $chunk );
				$result = $this->telegram_api_request(
					'sendMessage',
					array(
						'chat_id'                  => $chat_id,
						'text'                     => $html,
						'parse_mode'               => 'HTML',
						'disable_web_page_preview' => true,
					)
				);
				// Retry without blockquotes (keep <b>/<i>/…) before plain text.
				if ( self::is_telegram_parse_error( $result ) && false !== strpos( $html, '<blockquote>' ) ) {
					$safe   = self::strip_telegram_blockquotes( $html );
					$result = $this->telegram_api_request(
						'sendMessage',
						array(
							'chat_id'                  => $chat_id,
							'text'                     => $safe,
							'parse_mode'               => 'HTML',
							'disable_web_page_preview' => true,
						)
					);
				}
				if ( self::is_telegram_parse_error( $result ) ) {
					// Last resort: still convert Markdown→HTML markers to visible
					// structure by stripping tags but keeping the converted bullets.
					// Prefer plain original chunk so raw ** is visible for debugging
					// rather than silently dropping formatting with no send.
					$result = $this->telegram_api_request(
						'sendMessage',
						array(
							'chat_id'                  => $chat_id,
							'text'                     => $chunk,
							'disable_web_page_preview' => true,
						)
					);
				}
			} else {
				$result = $this->telegram_api_request(
					'sendMessage',
					array(
						'chat_id'                  => $chat_id,
						'text'                     => $chunk,
						'disable_web_page_preview' => true,
					)
				);
			}

			$last = array(
				'ok'    => $result['ok'],
				'error' => $result['error'],
			);
			if ( ! $result['ok'] ) {
				break;
			}
		}

		return $last;
	}
}
