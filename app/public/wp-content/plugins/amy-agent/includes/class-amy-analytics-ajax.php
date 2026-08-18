<?php
/**
 * Admin-AJAX handlers for Analytics (proxies to Python service).
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Nonce-protected admin-ajax actions for analytics leads.
 */
class Amy_Analytics_Ajax {

	const NONCE_ACTION = 'amy_agent_analytics';

	/**
	 * @var Amy_Api_Client
	 */
	private $api_client;

	/**
	 * @param Amy_Api_Client $api_client API client.
	 */
	public function __construct( Amy_Api_Client $api_client ) {
		$this->api_client = $api_client;
	}

	/**
	 * Register AJAX actions.
	 */
	public function register() {
		add_action( 'wp_ajax_amy_analytics_leads_list', array( $this, 'ajax_leads_list' ) );
	}

	/**
	 * Shared gate: capability + nonce.
	 */
	private function guard() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to view analytics.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( self::NONCE_ACTION, 'nonce' );
	}

	/**
	 * Forward a failed API response as JSON error.
	 *
	 * @param array{ok: bool, status_code: int, body: array|null, error: string|null} $result API result.
	 */
	private function send_api_error( array $result ) {
		$message = __( 'Request failed.', 'amy-agent' );
		if ( ! empty( $result['error'] ) ) {
			$message = (string) $result['error'];
		} elseif ( is_array( $result['body'] ) && ! empty( $result['body']['message'] ) ) {
			$message = (string) $result['body']['message'];
		}
		$status = ! empty( $result['status_code'] ) ? (int) $result['status_code'] : 500;
		if ( $status < 400 ) {
			$status = 500;
		}
		wp_send_json_error( array( 'message' => $message ), $status );
	}

	/**
	 * List leads via amy_analytics_leads_list.
	 */
	public function ajax_leads_list() {
		$this->guard();

		$status = null;
		if ( isset( $_REQUEST['status'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
			$status = sanitize_key( wp_unslash( $_REQUEST['status'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			if ( ! in_array( $status, array( 'cold', 'warm', 'hot' ), true ) ) {
				$status = null;
			}
		}

		$result = $this->api_client->list_leads( $status );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array( 'leads' => array() ) );
	}
}
