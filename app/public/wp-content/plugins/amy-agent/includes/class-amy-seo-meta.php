<?php
/**
 * Registers SEO plugin post-meta keys for core REST read/write.
 *
 * Yoast is the only provider wired today. Field names used by Amy (focus_keyphrase,
 * seo_title, …) stay provider-agnostic; this class maps them onto Yoast meta keys
 * so a later provider can be added without changing the check/approval API.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Exposes Yoast SEO post meta through /wp/v2/posts and /wp/v2/pages.
 */
class Amy_Seo_Meta {

	/**
	 * Writable Yoast keys: Amy field name => meta key.
	 *
	 * @return array<string, string>
	 */
	public static function writable_field_map() {
		return array(
			'focus_keyphrase'   => '_yoast_wpseo_focuskw',
			'seo_title'         => '_yoast_wpseo_title',
			'meta_description'  => '_yoast_wpseo_metadesc',
			'og_title'          => '_yoast_wpseo_opengraph-title',
			'og_description'    => '_yoast_wpseo_opengraph-description',
			'og_image'          => '_yoast_wpseo_opengraph-image',
			'twitter_title'     => '_yoast_wpseo_twitter-title',
			'twitter_description' => '_yoast_wpseo_twitter-description',
			'twitter_image'     => '_yoast_wpseo_twitter-image',
		);
	}

	/**
	 * Read-only Yoast score keys (Amy reads these; she never writes them).
	 *
	 * @return array<string, string>
	 */
	public static function readonly_field_map() {
		return array(
			'seo_score'         => '_yoast_wpseo_linkdex',
			'readability_score' => '_yoast_wpseo_content_score',
		);
	}

	/**
	 * Image URL fields (esc_url_raw).
	 *
	 * @return string[]
	 */
	public static function url_meta_keys() {
		return array(
			'_yoast_wpseo_opengraph-image',
			'_yoast_wpseo_twitter-image',
		);
	}

	/**
	 * Hook registration.
	 */
	public function register() {
		add_action( 'init', array( $this, 'register_meta' ), 20 );
	}

	/**
	 * register_post_meta() with show_in_rest so core REST can read/write Yoast fields.
	 *
	 * Intentionally not registered:
	 * - `_yoast_wpseo_focuskeywords` (Yoast Premium related keyphrases).
	 * - `_wp_attachment_image_alt` — core already exposes this as `alt_text` on
	 *   `/wp/v2/media/{id}`, alongside title, caption (`excerpt`), and
	 *   description (`content`). Duplicating it would not add a write path.
	 */
	public function register_meta() {
		$post_types = array( 'post', 'page' );
		$url_keys   = self::url_meta_keys();

		foreach ( $post_types as $post_type ) {
			foreach ( self::writable_field_map() as $meta_key ) {
				$is_url = in_array( $meta_key, $url_keys, true );
				register_post_meta(
					$post_type,
					$meta_key,
					array(
						'type'              => 'string',
						'single'            => true,
						'default'           => '',
						'show_in_rest'      => true,
						'sanitize_callback' => $is_url ? 'esc_url_raw' : 'sanitize_text_field',
						'auth_callback'     => array( __CLASS__, 'auth_can_edit_post' ),
					)
				);
			}

			foreach ( self::readonly_field_map() as $meta_key ) {
				register_post_meta(
					$post_type,
					$meta_key,
					array(
						'type'              => 'string',
						'single'            => true,
						'default'           => '',
						'show_in_rest'      => true,
						'sanitize_callback' => 'sanitize_text_field',
						'auth_callback'     => array( __CLASS__, 'auth_read_only' ),
					)
				);
			}
		}
	}

	/**
	 * Same capability Yoast expects for editing a post's SEO meta: edit_post
	 * (maps to edit_page for pages via WP meta caps). Does not loosen access.
	 *
	 * @param bool   $allowed   Whether the user can add this meta.
	 * @param string $meta_key  Meta key.
	 * @param int    $object_id Post ID.
	 * @return bool
	 */
	public static function auth_can_edit_post( $allowed, $meta_key, $object_id ) {
		unset( $allowed, $meta_key );
		return current_user_can( 'edit_post', (int) $object_id );
	}

	/**
	 * Block REST writes of Yoast's computed scores. Reads still work via show_in_rest.
	 *
	 * @return bool
	 */
	public static function auth_read_only() {
		return false;
	}
}
