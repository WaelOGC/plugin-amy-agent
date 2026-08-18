<?php
/**
 * Yoast taxonomy SEO title / meta description bridge for categories and tags.
 *
 * Yoast stores these in the serialized `wpseo_taxonomy_meta` option, not core
 * term meta. Reads/writes go through WPSEO_Taxonomy_Meta so values show up in
 * Yoast's own term-edit UI.
 *
 * Verified against Yoast SEO 28.3 (2026-08-18): stored keys are `wpseo_title`
 * and `wpseo_desc`. `set_value()` prepends `wpseo_` when missing, so the
 * meta_key arguments `title` and `desc` are the correct write keys.
 * `get_term_meta( $term_id, $taxonomy )` returns the full array; the optional
 * third argument is the key *without* the `wpseo_` prefix (`title` / `desc`).
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Nonce-protected admin-ajax actions for category/tag Yoast fields.
 */
class Amy_Seo_Taxonomy_Meta {

	const ALLOWED_TAXONOMIES = array( 'category', 'tag' );

	/**
	 * Register AJAX actions.
	 */
	public function register() {
		add_action( 'wp_ajax_amy_seo_term_get', array( $this, 'ajax_term_get' ) );
		add_action( 'wp_ajax_amy_seo_term_write', array( $this, 'ajax_term_write' ) );
	}

	/**
	 * Shared gate: capability + SEO Tasks nonce.
	 *
	 * @param string $capability Required capability.
	 */
	private function guard( $capability = 'manage_options' ) {
		if ( ! current_user_can( $capability ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to manage SEO tasks.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( Amy_Seo_Tasks_Ajax::NONCE_ACTION, 'nonce' );
	}

	/**
	 * Fail with a JSON error if Yoast's taxonomy meta API is not available.
	 */
	private function require_yoast() {
		if ( class_exists( 'WPSEO_Taxonomy_Meta' ) ) {
			return;
		}
		wp_send_json_error(
			array( 'message' => __( 'Yoast SEO is not active, so category and tag SEO fields cannot be read or written.', 'amy-agent' ) ),
			400
		);
	}

	/**
	 * Map the public taxonomy alias to the WordPress taxonomy slug.
	 *
	 * @return array{alias: string, taxonomy: string}|null
	 */
	private function parse_taxonomy() {
		$alias = isset( $_REQUEST['taxonomy'] ) ? sanitize_key( wp_unslash( $_REQUEST['taxonomy'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
		if ( ! in_array( $alias, self::ALLOWED_TAXONOMIES, true ) ) {
			return null;
		}
		return array(
			'alias'    => $alias,
			'taxonomy' => ( 'tag' === $alias ) ? 'post_tag' : 'category',
		);
	}

	/**
	 * Read a string value from a Yoast term-meta array.
	 *
	 * @param mixed  $meta Yoast get_term_meta() result.
	 * @param string $key  Stored key including wpseo_ prefix.
	 * @return string
	 */
	private function meta_string( $meta, $key ) {
		if ( ! is_array( $meta ) || ! isset( $meta[ $key ] ) ) {
			return '';
		}
		return is_string( $meta[ $key ] ) ? $meta[ $key ] : (string) $meta[ $key ];
	}

	/**
	 * GET current Yoast + core fields for one category or tag.
	 */
	public function ajax_term_get() {
		$this->guard( 'manage_options' );
		$this->require_yoast();

		$parsed = $this->parse_taxonomy();
		if ( null === $parsed ) {
			wp_send_json_error(
				array( 'message' => __( 'Taxonomy must be category or tag.', 'amy-agent' ) ),
				400
			);
		}

		$term_id = isset( $_REQUEST['term_id'] ) ? absint( wp_unslash( $_REQUEST['term_id'] ) ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
		if ( $term_id < 1 ) {
			wp_send_json_error(
				array( 'message' => __( 'A valid term ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$term = get_term( $term_id, $parsed['taxonomy'] );
		if ( ! $term || is_wp_error( $term ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Term not found.', 'amy-agent' ) ),
				404
			);
		}

		$meta = WPSEO_Taxonomy_Meta::get_term_meta( $term_id, $parsed['taxonomy'] );
		$seo_title        = $this->meta_string( $meta, 'wpseo_title' );
		$meta_description = $this->meta_string( $meta, 'wpseo_desc' );

		wp_send_json_success(
			array(
				'taxonomy'          => $parsed['alias'],
				'term_id'           => $term_id,
				'name'              => $term->name,
				'seo_title'         => $seo_title,
				'meta_description'  => $meta_description,
				'term_description'  => (string) term_description( $term_id, $parsed['taxonomy'] ),
			)
		);
	}

	/**
	 * WRITE Yoast SEO title / meta description for one category or tag.
	 */
	public function ajax_term_write() {
		$this->guard( 'manage_categories' );
		$this->require_yoast();

		$parsed = $this->parse_taxonomy();
		if ( null === $parsed ) {
			wp_send_json_error(
				array( 'message' => __( 'Taxonomy must be category or tag.', 'amy-agent' ) ),
				400
			);
		}

		$term_id = isset( $_POST['term_id'] ) ? absint( wp_unslash( $_POST['term_id'] ) ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified in guard().
		if ( $term_id < 1 ) {
			wp_send_json_error(
				array( 'message' => __( 'A valid term ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$term = get_term( $term_id, $parsed['taxonomy'] );
		if ( ! $term || is_wp_error( $term ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Term not found.', 'amy-agent' ) ),
				404
			);
		}

		$written = array();
		if ( isset( $_POST['seo_title'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified in guard().
			$title = sanitize_text_field( wp_unslash( $_POST['seo_title'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Missing
			if ( '' !== trim( $title ) ) {
				WPSEO_Taxonomy_Meta::set_value( $term_id, $parsed['taxonomy'], 'title', $title );
				$written['seo_title'] = $title;
			}
		}
		if ( isset( $_POST['meta_description'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified in guard().
			$desc = sanitize_textarea_field( wp_unslash( $_POST['meta_description'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Missing
			if ( '' !== trim( $desc ) ) {
				WPSEO_Taxonomy_Meta::set_value( $term_id, $parsed['taxonomy'], 'desc', $desc );
				$written['meta_description'] = $desc;
			}
		}

		wp_send_json_success(
			array(
				'taxonomy' => $parsed['alias'],
				'term_id'  => $term_id,
				'written'  => $written,
			)
		);
	}
}
