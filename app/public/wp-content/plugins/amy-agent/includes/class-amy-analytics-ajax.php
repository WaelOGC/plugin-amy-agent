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
		add_action( 'wp_ajax_amy_analytics_closing_wish_effect', array( $this, 'ajax_closing_wish_effect' ) );
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
	 * Connection / misconfig failures (status_code 0) become HTTP 502 so they are
	 * distinguishable from a true PHP fatal 500. Upstream 4xx/5xx are forwarded.
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
		$upstream = isset( $result['status_code'] ) ? (int) $result['status_code'] : 0;
		if ( $upstream <= 0 ) {
			// Service URL/secret missing, DNS/connect refused, timeout, etc.
			$status = 502;
		} elseif ( $upstream < 400 ) {
			$status = 500;
		} else {
			$status = $upstream;
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

		$has_email = null;
		if ( isset( $_REQUEST['has_email'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
			$raw = strtolower( sanitize_text_field( wp_unslash( $_REQUEST['has_email'] ) ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			if ( in_array( $raw, array( '1', 'true', 'yes' ), true ) ) {
				$has_email = true;
			} elseif ( in_array( $raw, array( '0', 'false', 'no' ), true ) ) {
				$has_email = false;
			}
		}

		$result = $this->api_client->list_leads( $status, $has_email );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array( 'leads' => array() ) );
	}

	/**
	 * Closing-wish effect metrics via amy_analytics_closing_wish_effect.
	 */
	public function ajax_closing_wish_effect() {
		$this->guard();

		$days = 30;
		if ( isset( $_REQUEST['days'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
			$days = (int) wp_unslash( $_REQUEST['days'] ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		}

		$result = $this->api_client->get_closing_wish_effect( $days );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}
}
