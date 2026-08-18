<?php
/**
 * Admin-AJAX handlers for SEO Tasks (proxies to Python service).
 *
 * WordPress core REST (`/wp/v2/posts|pages|media`) is used by the admin page
 * to read/write Yoast meta. These actions only talk to amy-agent-service.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Nonce-protected admin-ajax actions for SEO checks.
 */
class Amy_Seo_Tasks_Ajax {

	const NONCE_ACTION = 'amy_agent_seo_tasks';

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
		add_action( 'wp_ajax_amy_seo_check', array( $this, 'ajax_check' ) );
		add_action( 'wp_ajax_amy_seo_checks_list', array( $this, 'ajax_list' ) );
		add_action( 'wp_ajax_amy_seo_check_get', array( $this, 'ajax_get' ) );
		add_action( 'wp_ajax_amy_seo_check_approve', array( $this, 'ajax_approve' ) );
		add_action( 'wp_ajax_amy_seo_check_reject', array( $this, 'ajax_reject' ) );
	}

	/**
	 * Shared gate: capability + nonce.
	 */
	private function guard() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to manage SEO tasks.', 'amy-agent' ) ),
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
	 * POST snapshot to Python /v1/seo-tasks/check.
	 */
	public function ajax_check() {
		$this->guard();

		$raw = array();
		if ( isset( $_POST['snapshot'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified in guard().
			$decoded = json_decode( wp_unslash( $_POST['snapshot'] ), true ); // phpcs:ignore WordPress.Security.NonceVerification.Missing, WordPress.Security.ValidatedSanitizedInput.InputNotSanitized
			if ( is_array( $decoded ) ) {
				$raw = $decoded;
			}
		}

		$payload = $this->sanitize_snapshot( $raw );
		if ( null === $payload || $payload['wp_post_id'] < 1 ) {
			wp_send_json_error(
				array( 'message' => __( 'A valid published post or page is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->seo_check( $payload );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * List stored checks.
	 */
	public function ajax_list() {
		$this->guard();

		$status  = null;
		$verdict = null;
		if ( isset( $_REQUEST['status'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
			$status = sanitize_key( wp_unslash( $_REQUEST['status'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			if ( ! in_array( $status, array( 'pending_approval', 'approved', 'rejected' ), true ) ) {
				$status = null;
			}
		}
		if ( isset( $_REQUEST['verdict'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			$verdict = sanitize_key( wp_unslash( $_REQUEST['verdict'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			if ( ! in_array( $verdict, array( 'red', 'orange', 'green' ), true ) ) {
				$verdict = null;
			}
		}

		$content_type = null;
		if ( isset( $_REQUEST['content_type'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			$content_type = sanitize_key( wp_unslash( $_REQUEST['content_type'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			if ( ! in_array( $content_type, array( 'post', 'page', 'category', 'tag', 'media' ), true ) ) {
				$content_type = null;
			}
		}

		$result = $this->api_client->list_seo_checks( $status, $verdict, $content_type );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array( 'checks' => array() ) );
	}

	/**
	 * Single check detail.
	 */
	public function ajax_get() {
		$this->guard();

		$id = isset( $_REQUEST['check_id'] ) ? sanitize_text_field( wp_unslash( $_REQUEST['check_id'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Check ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->get_seo_check( $id );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * Record approval after WordPress has written the fields via core REST.
	 */
	public function ajax_approve() {
		$this->guard();

		$id = isset( $_POST['check_id'] ) ? sanitize_text_field( wp_unslash( $_POST['check_id'] ) ) : '';
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Check ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$fields = array();
		if ( isset( $_POST['approved_fields'] ) ) {
			$decoded = json_decode( wp_unslash( $_POST['approved_fields'] ), true ); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput.InputNotSanitized
			if ( is_array( $decoded ) ) {
				$fields = $this->sanitize_approved_fields( $decoded );
			}
		}

		$result = $this->api_client->approve_seo_check( $id, $fields );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * Record rejection. No WordPress write.
	 */
	public function ajax_reject() {
		$this->guard();

		$id = isset( $_POST['check_id'] ) ? sanitize_text_field( wp_unslash( $_POST['check_id'] ) ) : '';
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Check ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$reason = isset( $_POST['reason'] ) ? sanitize_textarea_field( wp_unslash( $_POST['reason'] ) ) : '';
		$reason = '' !== $reason ? $reason : null;

		$result = $this->api_client->reject_seo_check( $id, $reason );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * @param array<string, mixed> $raw Raw snapshot.
	 * @return array<string, mixed>|null
	 */
	private function sanitize_snapshot( array $raw ) {
		$post_type = isset( $raw['post_type'] ) ? sanitize_key( (string) $raw['post_type'] ) : '';
		if ( ! in_array( $post_type, array( 'post', 'page' ), true ) ) {
			return null;
		}

		return array(
			'wp_post_id'            => absint( $raw['wp_post_id'] ?? 0 ),
			'post_type'             => $post_type,
			'title'                 => sanitize_text_field( (string) ( $raw['title'] ?? '' ) ),
			'content_excerpt'       => sanitize_textarea_field( (string) ( $raw['content_excerpt'] ?? '' ) ),
			'focus_keyphrase'       => sanitize_text_field( (string) ( $raw['focus_keyphrase'] ?? '' ) ),
			'seo_title'             => sanitize_text_field( (string) ( $raw['seo_title'] ?? '' ) ),
			'meta_description'      => sanitize_textarea_field( (string) ( $raw['meta_description'] ?? '' ) ),
			'has_featured_image'    => ! empty( $raw['has_featured_image'] ),
			'featured_image_alt'    => sanitize_text_field( (string) ( $raw['featured_image_alt'] ?? '' ) ),
			'og_title'              => sanitize_text_field( (string) ( $raw['og_title'] ?? '' ) ),
			'og_description'        => sanitize_textarea_field( (string) ( $raw['og_description'] ?? '' ) ),
			'og_image'              => esc_url_raw( (string) ( $raw['og_image'] ?? '' ) ),
			'twitter_title'         => sanitize_text_field( (string) ( $raw['twitter_title'] ?? '' ) ),
			'twitter_description'   => sanitize_textarea_field( (string) ( $raw['twitter_description'] ?? '' ) ),
			'twitter_image'         => esc_url_raw( (string) ( $raw['twitter_image'] ?? '' ) ),
			'category_count'        => absint( $raw['category_count'] ?? 0 ),
		);
	}

	/**
	 * @param array<string, mixed> $raw Raw approved fields.
	 * @return array<string, mixed>
	 */
	private function sanitize_approved_fields( array $raw ) {
		$out   = array();
		$text  = array( 'focus_keyphrase', 'seo_title', 'og_title', 'twitter_title', 'featured_image_alt' );
		$area  = array( 'meta_description', 'og_description', 'twitter_description' );
		$urls  = array( 'og_image', 'twitter_image' );

		foreach ( $text as $key ) {
			if ( isset( $raw[ $key ] ) && '' !== trim( (string) $raw[ $key ] ) ) {
				$out[ $key ] = sanitize_text_field( (string) $raw[ $key ] );
			}
		}
		foreach ( $area as $key ) {
			if ( isset( $raw[ $key ] ) && '' !== trim( (string) $raw[ $key ] ) ) {
				$out[ $key ] = sanitize_textarea_field( (string) $raw[ $key ] );
			}
		}
		foreach ( $urls as $key ) {
			if ( isset( $raw[ $key ] ) && '' !== trim( (string) $raw[ $key ] ) ) {
				$url = esc_url_raw( (string) $raw[ $key ] );
				if ( '' !== $url ) {
					$out[ $key ] = $url;
				}
			}
		}

		if ( isset( $raw['category_ids'] ) && is_array( $raw['category_ids'] ) ) {
			$ids = array();
			foreach ( $raw['category_ids'] as $id ) {
				$id = absint( $id );
				if ( $id > 0 ) {
					$ids[] = $id;
				}
			}
			if ( ! empty( $ids ) ) {
				$out['category_ids'] = array_values( array_unique( $ids ) );
			}
		}

		return $out;
	}
}
