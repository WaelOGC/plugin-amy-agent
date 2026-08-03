<?php
/**
 * WordPress REST API routes for Amy Agent.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Browser-facing REST routes (health + public chat).
 */
class Amy_Rest {

	const NAMESPACE = 'amy-agent/v1';

	/**
	 * Max chat requests per IP per window.
	 */
	const RATE_LIMIT_MAX = 20;

	/**
	 * Rate-limit window in seconds.
	 */
	const RATE_LIMIT_WINDOW = 60;

	/**
	 * @var Amy_Api_Client
	 */
	private $api_client;

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @param Amy_Api_Client $api_client API client.
	 * @param Amy_Settings   $settings   Settings.
	 */
	public function __construct( Amy_Api_Client $api_client, Amy_Settings $settings ) {
		$this->api_client = $api_client;
		$this->settings   = $settings;
	}

	/**
	 * Register routes.
	 */
	public function register() {
		add_action( 'rest_api_init', array( $this, 'register_routes' ) );
	}

	/**
	 * Route definitions.
	 */
	public function register_routes() {
		register_rest_route(
			self::NAMESPACE,
			'/health',
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'handle_health' ),
				'permission_callback' => array( $this, 'can_manage' ),
			)
		);

		register_rest_route(
			self::NAMESPACE,
			'/chat',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'handle_chat' ),
				'permission_callback' => array( $this, 'can_chat' ),
				'args'                => array(
					'session_id' => array(
						'required'          => true,
						'type'              => 'string',
						'sanitize_callback' => 'sanitize_text_field',
					),
					'mode'       => array(
						'required'          => false,
						'type'              => 'string',
						'default'           => 'general',
						'sanitize_callback' => 'sanitize_key',
					),
					'messages'   => array(
						'required' => true,
						'type'     => 'array',
					),
					'page'       => array(
						'required' => false,
						'type'     => 'object',
					),
					'context'    => array(
						'required' => false,
						'type'     => 'object',
					),
				),
			)
		);
	}

	/**
	 * @return bool
	 */
	public function can_manage() {
		return current_user_can( 'manage_options' );
	}

	/**
	 * Public chat with same-origin REST nonce (logged-in or visitor).
	 *
	 * @param WP_REST_Request $request Request.
	 * @return bool|WP_Error
	 */
	public function can_chat( $request ) {
		$nonce = $request->get_header( 'X-WP-Nonce' );
		if ( ! $nonce || ! wp_verify_nonce( $nonce, 'wp_rest' ) ) {
			return new WP_Error(
				'amy_rest_forbidden',
				__( 'Invalid or missing REST nonce.', 'amy-agent' ),
				array( 'status' => 403 )
			);
		}
		return true;
	}

	/**
	 * Checks WP settings presence and Python /v1/health reachability.
	 *
	 * @return WP_REST_Response
	 */
	public function handle_health() {
		$settings_ok = $this->settings->is_service_configured();
		$python      = null;

		if ( $settings_ok ) {
			$python = $this->api_client->health();
		}

		$python_ok = is_array( $python ) && ! empty( $python['ok'] );

		$data = array(
			'ok'             => $settings_ok && $python_ok,
			'plugin_version' => AMY_AGENT_VERSION,
			'settings'       => array(
				'enabled'            => $this->settings->is_enabled(),
				'service_configured' => $settings_ok,
				'provider'           => $this->settings->get_ai_provider(),
				'has_api_key'        => '' !== $this->settings->get_ai_api_key(),
			),
			'python'         => $python,
		);

		$status = $data['ok'] ? 200 : 503;
		return new WP_REST_Response( $data, $status );
	}

	/**
	 * Public chat proxy → Python service.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function handle_chat( $request ) {
		if ( ! $this->settings->is_ready() ) {
			return new WP_REST_Response(
				array(
					'error'   => 'not_available',
					'message' => __( 'Amy is not available right now.', 'amy-agent' ),
				),
				503
			);
		}

		if ( $this->is_rate_limited() ) {
			return new WP_REST_Response(
				array(
					'error'   => 'rate_limited',
					'message' => __( 'Too many messages. Please wait a moment and try again.', 'amy-agent' ),
				),
				429
			);
		}

		$session_id = (string) $request->get_param( 'session_id' );
		$mode       = (string) $request->get_param( 'mode' );
		if ( 'general' !== $mode ) {
			$mode = 'general';
		}

		$messages = $this->sanitize_messages( $request->get_param( 'messages' ) );
		if ( empty( $messages ) ) {
			return new WP_REST_Response(
				array(
					'error'   => 'invalid_request',
					'message' => __( 'At least one message is required.', 'amy-agent' ),
				),
				400
			);
		}

		$page    = $request->get_param( 'page' );
		$context = $request->get_param( 'context' );

		$payload = array(
			'session_id' => $session_id,
			'mode'       => $mode,
			'messages'   => $messages,
			'context'    => is_array( $context ) && ! empty( $context ) ? $context : (object) array(),
		);

		if ( is_array( $page ) ) {
			$payload['page'] = array(
				'url'  => isset( $page['url'] ) ? esc_url_raw( (string) $page['url'] ) : null,
				'slug' => isset( $page['slug'] ) ? sanitize_title( (string) $page['slug'] ) : null,
			);
		}

		$result = $this->api_client->chat( $payload );
		$status = (int) $result['status_code'];
		if ( $status < 100 ) {
			$status = 502;
		}

		$body = is_array( $result['body'] ) ? $result['body'] : array(
			'error'   => 'upstream_error',
			'message' => __( 'Amy is unavailable right now.', 'amy-agent' ),
		);

		// Never expose internal client error strings that might include secrets.
		if ( ! empty( $result['error'] ) && empty( $body['message'] ) ) {
			$body['message'] = __( 'Amy is unavailable right now.', 'amy-agent' );
		}

		return new WP_REST_Response( $body, $status );
	}

	/**
	 * @param mixed $messages Raw messages array.
	 * @return array<int, array{role: string, content: string}>
	 */
	private function sanitize_messages( $messages ) {
		if ( ! is_array( $messages ) ) {
			return array();
		}

		$allowed_roles = array( 'user', 'assistant', 'system' );
		$clean         = array();

		foreach ( $messages as $msg ) {
			if ( ! is_array( $msg ) ) {
				continue;
			}
			$role    = isset( $msg['role'] ) ? sanitize_key( (string) $msg['role'] ) : '';
			$content = isset( $msg['content'] ) ? sanitize_textarea_field( (string) $msg['content'] ) : '';
			if ( ! in_array( $role, $allowed_roles, true ) || '' === $content ) {
				continue;
			}
			$clean[] = array(
				'role'    => $role,
				'content' => $content,
			);
			if ( count( $clean ) >= 40 ) {
				break;
			}
		}

		return $clean;
	}

	/**
	 * Transient-based per-IP rate limit.
	 *
	 * @return bool True when the caller should be blocked.
	 */
	private function is_rate_limited() {
		$ip = $this->get_client_ip();
		$key = 'amy_rl_' . md5( $ip );
		$count = (int) get_transient( $key );

		if ( $count >= self::RATE_LIMIT_MAX ) {
			return true;
		}

		set_transient( $key, $count + 1, self::RATE_LIMIT_WINDOW );
		return false;
	}

	/**
	 * @return string
	 */
	private function get_client_ip() {
		$ip = isset( $_SERVER['REMOTE_ADDR'] ) ? (string) wp_unslash( $_SERVER['REMOTE_ADDR'] ) : '';
		return $ip ? $ip : 'unknown';
	}
}
