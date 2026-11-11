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

	const OPTION_WEBHOOK_SECRET = 'amy_agent_telegram_webhook_secret';
	const OPTION_BOT_USERNAME   = 'amy_agent_telegram_bot_username';
	const OPTION_CHATS          = 'amy_agent_telegram_chats';

	const TRANSIENT_UPDATES     = 'amy_tg_update_ids';
	const TRANSIENT_RATE_USER    = 'amy_tg_rate_';
	const TRANSIENT_DENY_NOTICE  = 'amy_tg_deny_';
	const TRANSIENT_SLOW_NOTICE  = 'amy_tg_slow_';

	const MAX_MESSAGE_LENGTH = 4000;
	const RATE_LIMIT_PER_MIN = 20;

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
				array( 'message' => __( 'Telegram webhooks require HTTPS. Connect is disabled on non-HTTPS sites.', 'amy-agent' ) ),
				400
			);
		}

		$token = $this->get_bot_token();
		if ( '' === $token ) {
			wp_send_json_error(
				array( 'message' => __( 'Save a bot token in settings first.', 'amy-agent' ) ),
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
			wp_send_json_error(
				array( 'message' => $set['error'] ? $set['error'] : __( 'setWebhook failed.', 'amy-agent' ) ),
				502
			);
		}

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

		wp_send_json_success(
			array(
				'message' => __( 'Telegram webhook disconnected and chat mappings cleared.', 'amy-agent' ),
			)
		);
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
	 * Send test message to each whitelisted admin.
	 */
	public function ajax_test() {
		$this->guard();

		if ( ! $this->is_telegram_enabled() || '' === $this->get_bot_token() ) {
			wp_send_json_error(
				array( 'message' => __( 'Enable the bot and save a token first.', 'amy-agent' ) ),
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

		$chat_id        = (int) $chat['id'];
		$telegram_id    = (int) $from['id'];
		$whitelist_row  = $this->find_whitelist_row( $telegram_id );

		if ( null === $whitelist_row ) {
			$this->maybe_send_unlisted_notice( $chat_id, $telegram_id );
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$wp_user = get_userdata( $whitelist_row['wp_user_id'] );
		if ( ! $wp_user || ! user_can( $wp_user, 'manage_options' ) ) {
			$this->send_message(
				$chat_id,
				__( 'Your WordPress link is no longer valid.', 'amy-agent' ),
				false
			);
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		if ( $this->is_rate_limited( $telegram_id ) ) {
			$slow_key = self::TRANSIENT_SLOW_NOTICE . $telegram_id;
			if ( ! get_transient( $slow_key ) ) {
				set_transient( $slow_key, '1', MINUTE_IN_SECONDS );
				$this->send_message( $chat_id, __( 'Slow down a little 🙂', 'amy-agent' ), false );
			}
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}
		$this->bump_rate_limit( $telegram_id );

		$text = isset( $message['text'] ) ? (string) $message['text'] : '';
		if ( '' === $text ) {
			$this->send_message(
				$chat_id,
				__( 'I can only read text messages for now.', 'amy-agent' ),
				false
			);
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		if ( str_starts_with( $text, '/' ) ) {
			$this->handle_command( $chat_id, $text, $whitelist_row, $wp_user );
			return new WP_REST_Response( array( 'ok' => true ), 200 );
		}

		$this->handle_plain_text( $chat_id, $text, $whitelist_row, $wp_user );

		return new WP_REST_Response( array( 'ok' => true ), 200 );
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
	 * @param int                                      $chat_id Chat id.
	 * @param string                                   $text    Full message text.
	 * @param array{telegram_id:int,label:string,wp_user_id:int} $row     Whitelist row.
	 * @param WP_User                                  $wp_user Linked user.
	 */
	private function handle_command( $chat_id, $text, $row, $wp_user ) {
		$cmd = strtolower( trim( strtok( $text, " \n\r\t" ) ) );

		if ( '/start' === $cmd || '/help' === $cmd ) {
			$help = __( "I'm Amy — your admin assistant. Chat here like Dashboard Chat. Commands: /new, /whoami, /help.", 'amy-agent' );
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
			$this->clear_chat_conversation( $chat_id );
			$this->send_message( $chat_id, __( 'Started a new conversation.', 'amy-agent' ), false );
			return;
		}

		$this->send_message( $chat_id, __( 'Unknown command. Try /help.', 'amy-agent' ), false );
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
	 * @param string $text Markdown-ish text.
	 * @return string
	 */
	public static function markdown_to_telegram_html( $text ) {
		$text = (string) $text;
		$text = htmlspecialchars( $text, ENT_NOQUOTES | ENT_SUBSTITUTE, 'UTF-8' );

		$text = preg_replace_callback(
			'/```[\w-]*\r?\n([\s\S]*?)```/',
			static function ( $m ) {
				return '<pre>' . $m[1] . '</pre>';
			},
			$text
		);

		$text = preg_replace( '/`([^`]+)`/', '<code>$1</code>', $text );

		$text = preg_replace_callback(
			'/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/',
			static function ( $m ) {
				$url = esc_url( $m[2], array( 'http', 'https' ) );
				if ( '' === $url ) {
					return $m[0];
				}
				return '<a href="' . $url . '">' . $m[1] . '</a>';
			},
			$text
		);

		$text = preg_replace( '/\*\*([^*]+)\*\*/', '<b>$1</b>', $text );
		$text = preg_replace( '/(?<!\*)\*([^*\n]+)\*(?!\*)/', '<i>$1</i>', $text );
		$text = preg_replace( '/\b_([^_\n]+)_\b/', '<i>$1</i>', $text );

		$lines = explode( "\n", $text );
		foreach ( $lines as $i => $line ) {
			if ( preg_match( '/^(\*|-)  /', $line ) ) {
				$lines[ $i ] = '• ' . substr( $line, 2 );
			}
		}
		$text = implode( "\n", $lines );

		return self::balance_telegram_html_tags( $text );
	}

	/**
	 * Close any unclosed supported tags (best-effort).
	 *
	 * @param string $html HTML fragment.
	 * @return string
	 */
	private static function balance_telegram_html_tags( $html ) {
		$tags  = array( 'b', 'i', 'code', 'pre', 'a' );
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
	 * Send a message to a chat (HTML with plain fallback).
	 *
	 * @param int    $chat_id    Chat id.
	 * @param string $text       Message body.
	 * @param bool   $allow_html Whether to use HTML parse mode.
	 * @return array{ok:bool,error:string|null}
	 */
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
				if ( ! $result['ok'] && 400 === (int) $result['status'] ) {
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
