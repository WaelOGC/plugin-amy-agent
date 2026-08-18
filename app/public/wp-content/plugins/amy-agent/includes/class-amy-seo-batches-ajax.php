<?php
/**
 * Admin-AJAX handlers for SEO Tasks batch runs (proxies to Python).
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Nonce-protected admin-ajax actions for SEO batch runs.
 */
class Amy_Seo_Batches_Ajax {

	const MAX_ITEMS = 500;

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
		add_action( 'wp_ajax_amy_seo_batch_start', array( $this, 'ajax_start' ) );
		add_action( 'wp_ajax_amy_seo_batch_continue', array( $this, 'ajax_continue' ) );
		add_action( 'wp_ajax_amy_seo_batch_stop', array( $this, 'ajax_stop' ) );
		add_action( 'wp_ajax_amy_seo_batch_get', array( $this, 'ajax_get' ) );
	}

	/**
	 * Shared gate: capability + SEO Tasks nonce.
	 */
	private function guard() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to manage SEO tasks.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( Amy_Seo_Tasks_Ajax::NONCE_ACTION, 'nonce' );
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
	 * @return string
	 */
	private function request_batch_id() {
		$id = isset( $_REQUEST['batch_run_id'] ) ? sanitize_text_field( wp_unslash( $_REQUEST['batch_run_id'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
		return $id;
	}

	/**
	 * POST /v1/seo-tasks/batches.
	 */
	public function ajax_start() {
		$this->guard();

		$content_type = isset( $_POST['content_type'] ) ? sanitize_key( wp_unslash( $_POST['content_type'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified in guard().
		if ( ! in_array( $content_type, array( 'post', 'page', 'category', 'tag', 'media' ), true ) ) {
			wp_send_json_error(
				array( 'message' => __( 'A valid content type is required.', 'amy-agent' ) ),
				400
			);
		}

		$mode = isset( $_POST['mode'] ) ? sanitize_key( wp_unslash( $_POST['mode'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		if ( ! in_array( $mode, array( 'manual', 'auto' ), true ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Mode must be manual or automatic.', 'amy-agent' ) ),
				400
			);
		}

		$batch_size = isset( $_POST['batch_size'] ) ? absint( wp_unslash( $_POST['batch_size'] ) ) : 5; // phpcs:ignore WordPress.Security.NonceVerification.Missing
		if ( $batch_size < 1 ) {
			$batch_size = 5;
		}

		$raw_items = array();
		if ( isset( $_POST['items'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing
			$decoded = json_decode( wp_unslash( $_POST['items'] ), true ); // phpcs:ignore WordPress.Security.NonceVerification.Missing, WordPress.Security.ValidatedSanitizedInput.InputNotSanitized
			if ( is_array( $decoded ) ) {
				$raw_items = $decoded;
			}
		}

		$items = $this->sanitize_items( $raw_items );
		if ( empty( $items ) ) {
			wp_send_json_error(
				array( 'message' => __( 'At least one item is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->start_seo_batch(
			array(
				'content_type' => $content_type,
				'mode'         => $mode,
				'batch_size'   => $batch_size,
				'items'        => $items,
			)
		);
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * POST /v1/seo-tasks/batches/{id}/continue.
	 */
	public function ajax_continue() {
		$this->guard();

		$id = $this->request_batch_id();
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Batch run ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->continue_seo_batch( $id );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * POST /v1/seo-tasks/batches/{id}/stop.
	 */
	public function ajax_stop() {
		$this->guard();

		$id = $this->request_batch_id();
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Batch run ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->stop_seo_batch( $id );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * GET /v1/seo-tasks/batches/{id}.
	 */
	public function ajax_get() {
		$this->guard();

		$id = $this->request_batch_id();
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Batch run ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->get_seo_batch( $id );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * Keep item shape; cap length; do not rewrite snapshot field values.
	 *
	 * @param array<int, mixed> $raw Raw items.
	 * @return array<int, array{item_id: int, title: string, snapshot: array}>
	 */
	private function sanitize_items( array $raw ) {
		$out = array();
		foreach ( $raw as $item ) {
			if ( ! is_array( $item ) ) {
				continue;
			}
			$item_id = absint( $item['item_id'] ?? 0 );
			if ( $item_id < 1 ) {
				continue;
			}
			$snapshot = $item['snapshot'] ?? array();
			if ( ! is_array( $snapshot ) ) {
				$snapshot = array();
			}
			$out[] = array(
				'item_id'  => $item_id,
				'title'    => sanitize_text_field( (string) ( $item['title'] ?? '' ) ),
				'snapshot' => $snapshot,
			);
			if ( count( $out ) >= self::MAX_ITEMS ) {
				break;
			}
		}
		return $out;
	}
}
