<?php
/**
 * HTTP client for the Amy Python service.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Proxies internal requests to amy-agent-service. Never calls AI providers.
 */
class Amy_Api_Client {

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @param Amy_Settings $settings Settings instance.
	 */
	public function __construct( Amy_Settings $settings ) {
		$this->settings = $settings;
	}

	/**
	 * GET /v1/health on the Python service.
	 *
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function health() {
		return $this->request( 'GET', '/v1/health' );
	}

	/**
	 * POST /v1/config/validate — schema check only in Phase 1.
	 *
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function validate_config() {
		return $this->request(
			'POST',
			'/v1/config/validate',
			array(
				'ai' => $this->settings->get_ai_config(),
			)
		);
	}

	/**
	 * POST /v1/chat — forwards to Python with AI config from settings.
	 *
	 * @param array $payload Chat request body (without ai; ai is merged from settings).
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function chat( array $payload ) {
		$payload['ai'] = $this->settings->get_ai_config();
		return $this->request( 'POST', '/v1/chat', $payload, 60 );
	}

	/**
	 * Perform an authenticated request to the Python service.
	 *
	 * @param string     $method  HTTP method.
	 * @param string     $path    Path beginning with /.
	 * @param array|null $body    JSON body for POST/PUT.
	 * @param int        $timeout Timeout in seconds.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function request( $method, $path, $body = null, $timeout = 15 ) {
		$base = $this->settings->get_service_url();
		if ( '' === $base ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Service URL is not configured.',
			);
		}

		$secret = $this->settings->get_shared_secret();
		if ( '' === $secret ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Shared secret is not configured.',
			);
		}

		$url  = $base . $path;
		$args = array(
			'method'  => strtoupper( $method ),
			'timeout' => (int) $timeout,
			'headers' => array(
				'Accept'       => 'application/json',
				'X-Amy-Secret' => $secret,
			),
		);

		if ( null !== $body ) {
			$args['headers']['Content-Type'] = 'application/json';
			$args['body']                    = wp_json_encode( $body );
		}

		$response = wp_remote_request( $url, $args );

		if ( is_wp_error( $response ) ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => $response->get_error_message(),
			);
		}

		$status  = (int) wp_remote_retrieve_response_code( $response );
		$raw     = wp_remote_retrieve_body( $response );
		$decoded = json_decode( $raw, true );

		return array(
			'ok'          => $status >= 200 && $status < 300,
			'status_code' => $status,
			'body'        => is_array( $decoded ) ? $decoded : null,
			'error'       => ( $status >= 200 && $status < 300 ) ? null : ( is_array( $decoded ) && isset( $decoded['message'] ) ? (string) $decoded['message'] : 'Request failed.' ),
		);
	}
}
