<?php
/**
 * Theme integration bridge for ogc-newfinity.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Hooks into theme filter/action without modifying the theme.
 */
class Amy_Theme_Bridge {

	/**
	 * Transient key for the compact public price catalogue.
	 */
	const PRICING_CATALOGUE_TRANSIENT = 'amy_pricing_catalogue_v1';

	/**
	 * Cache TTL for the price catalogue (1 hour).
	 */
	const PRICING_CATALOGUE_TTL = HOUR_IN_SECONDS;

	/**
	 * Hard cap for pricing_catalogue sent to the Python service.
	 */
	const PRICING_CATALOGUE_MAX_CHARS = 6000;

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
	 * Register theme contract hooks.
	 *
	 * Submit Idea UI is owned by Amy_Submit_Idea; this bridge keeps the shared
	 * readiness filter used by the floating widget and theme.
	 */
	public function register() {
		add_filter( 'ogc_amy_agent_is_active', array( $this, 'filter_is_active' ) );
		add_action( 'switch_theme', array( $this, 'clear_pricing_catalogue_cache' ) );
		add_action( 'upgrader_process_complete', array( $this, 'on_upgrader_process_complete' ), 10, 2 );
	}

	/**
	 * Theme / widget filter: true only when enabled and service URL + secret are set.
	 *
	 * @param bool $active Incoming value.
	 * @return bool
	 */
	public function filter_is_active( $active ) {
		unset( $active );
		return $this->settings->is_ready();
	}

	/**
	 * Compact plain-text price catalogue for public chat (cached 1 hour).
	 *
	 * Built from theme `ogc_get_pricing_data()` when present. Empty string when
	 * the helper is missing or yields nothing usable.
	 *
	 * @return string
	 */
	public function get_pricing_catalogue() {
		$cached = get_transient( self::PRICING_CATALOGUE_TRANSIENT );
		if ( false !== $cached && is_string( $cached ) ) {
			return $this->cap_pricing_catalogue( $cached );
		}

		$catalogue = $this->build_pricing_catalogue();
		set_transient( self::PRICING_CATALOGUE_TRANSIENT, $catalogue, self::PRICING_CATALOGUE_TTL );

		return $this->cap_pricing_catalogue( $catalogue );
	}

	/**
	 * Drop the cached catalogue (theme switch / updates).
	 *
	 * @return void
	 */
	public function clear_pricing_catalogue_cache() {
		delete_transient( self::PRICING_CATALOGUE_TRANSIENT );
	}

	/**
	 * Clear catalogue cache after theme or Amy plugin updates.
	 *
	 * @param WP_Upgrader $upgrader Upgrader instance.
	 * @param array       $options  Upgrade options.
	 * @return void
	 */
	public function on_upgrader_process_complete( $upgrader, $options ) {
		unset( $upgrader );

		if ( ! is_array( $options ) ) {
			return;
		}

		$type = isset( $options['type'] ) ? (string) $options['type'] : '';
		if ( 'theme' === $type ) {
			$this->clear_pricing_catalogue_cache();
			return;
		}

		if ( 'plugin' !== $type ) {
			return;
		}

		$plugins = array();
		if ( isset( $options['plugins'] ) && is_array( $options['plugins'] ) ) {
			$plugins = $options['plugins'];
		} elseif ( isset( $options['plugin'] ) ) {
			$plugins = array( (string) $options['plugin'] );
		}

		foreach ( $plugins as $plugin ) {
			$plugin = (string) $plugin;
			if ( false !== strpos( $plugin, 'amy-agent' ) ) {
				$this->clear_pricing_catalogue_cache();
				return;
			}
		}
	}

	/**
	 * Build catalogue text from theme pricing data (no features, no HTML).
	 *
	 * @return string
	 */
	private function build_pricing_catalogue() {
		if ( ! function_exists( 'ogc_get_pricing_data' ) ) {
			return '';
		}

		$data = ogc_get_pricing_data();
		if ( ! is_array( $data ) || empty( $data ) ) {
			return '';
		}

		$blocks = array();

		foreach ( $data as $service ) {
			if ( ! is_array( $service ) ) {
				continue;
			}

			$title = $this->plain_text( isset( $service['title'] ) ? $service['title'] : '' );
			if ( '' === $title ) {
				continue;
			}

			$lines   = array( $title );
			$packages = isset( $service['packages'] ) && is_array( $service['packages'] ) ? $service['packages'] : array();

			foreach ( $packages as $package ) {
				if ( ! is_array( $package ) ) {
					continue;
				}
				$name   = $this->plain_text( isset( $package['name'] ) ? $package['name'] : '' );
				$prefix = $this->plain_text( isset( $package['price_prefix'] ) ? $package['price_prefix'] : '' );
				$price  = $this->plain_text( isset( $package['price'] ) ? $package['price'] : '' );
				$unit   = $this->plain_text( isset( $package['unit'] ) ? $package['unit'] : '' );
				if ( '' === $name || '' === $price ) {
					continue;
				}
				$mid = '' !== $prefix ? ( $prefix . ' ' . $price ) : $price;
				if ( '' !== $unit ) {
					$lines[] = $name . ' — ' . $mid . ', ' . $unit;
				} else {
					$lines[] = $name . ' — ' . $mid;
				}
			}

			$extras = isset( $service['extras'] ) && is_array( $service['extras'] ) ? $service['extras'] : array();
			foreach ( $extras as $group ) {
				if ( ! is_array( $group ) ) {
					continue;
				}
				$rows = isset( $group['rows'] ) && is_array( $group['rows'] ) ? $group['rows'] : array();
				foreach ( $rows as $row ) {
					if ( ! is_array( $row ) ) {
						continue;
					}
					$label = $this->plain_text( isset( $row['label'] ) ? $row['label'] : '' );
					$price = $this->plain_text( isset( $row['price'] ) ? $row['price'] : '' );
					if ( '' === $label || '' === $price ) {
						continue;
					}
					$lines[] = $label . ' — ' . $price;
				}
			}

			if ( count( $lines ) > 1 ) {
				$blocks[] = implode( "\n", $lines );
			}
		}

		return implode( "\n\n", $blocks );
	}

	/**
	 * Strip tags / control characters for a single field value.
	 *
	 * @param mixed $value Raw value.
	 * @return string
	 */
	private function plain_text( $value ) {
		$text = wp_strip_all_tags( (string) $value );
		$text = preg_replace( '/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', '', $text );
		return trim( (string) $text );
	}

	/**
	 * Enforce the hard character cap before sending upstream.
	 *
	 * @param string $catalogue Catalogue text.
	 * @return string
	 */
	private function cap_pricing_catalogue( $catalogue ) {
		$catalogue = (string) $catalogue;
		if ( strlen( $catalogue ) <= self::PRICING_CATALOGUE_MAX_CHARS ) {
			return $catalogue;
		}
		return substr( $catalogue, 0, self::PRICING_CATALOGUE_MAX_CHARS );
	}
}
