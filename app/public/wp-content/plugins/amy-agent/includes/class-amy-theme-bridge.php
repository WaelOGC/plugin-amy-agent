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
	 */
	public function register() {
		add_filter( 'ogc_amy_agent_is_active', array( $this, 'filter_is_active' ) );
		add_action( 'ogc_submit_idea_render', array( $this, 'render_submit_idea' ) );
	}

	/**
	 * Theme filter: true only when enabled and service URL + secret are set.
	 *
	 * @param bool $active Theme default (false).
	 * @return bool
	 */
	public function filter_is_active( $active ) {
		unset( $active );
		return $this->settings->is_ready();
	}

	/**
	 * Submit Your Idea slot — Phase 1 stub (no conversational UI yet).
	 *
	 * Only outputs when Amy is ready so the theme's manual form stays alone otherwise.
	 * When ready, the theme hides the manual form; we leave a placeholder comment until Phase 3.
	 */
	public function render_submit_idea() {
		if ( ! $this->settings->is_ready() ) {
			return;
		}

		// Phase 1: no UI. Conversational intake lands here in a later phase.
		echo "\n<!-- Amy Agent: ogc_submit_idea_render stub (Phase 1 — conversational UI not implemented yet) -->\n";
	}
}
