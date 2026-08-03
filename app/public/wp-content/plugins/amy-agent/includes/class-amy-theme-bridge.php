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
}
