<?php
/**
 * Main plugin loader.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Boots Amy Agent subsystems.
 */
class Amy_Plugin {

	/**
	 * Singleton instance.
	 *
	 * @var Amy_Plugin|null
	 */
	private static $instance = null;

	/**
	 * @var Amy_Settings
	 */
	public $settings;

	/**
	 * @var Amy_Admin_Menu
	 */
	public $admin_menu;

	/**
	 * @var Amy_Api_Client
	 */
	public $api_client;

	/**
	 * @var Amy_Rest
	 */
	public $rest;

	/**
	 * @var Amy_Theme_Bridge
	 */
	public $theme_bridge;

	/**
	 * @var Amy_Assets
	 */
	public $assets;

	/**
	 * @var Amy_Submit_Idea
	 */
	public $submit_idea;

	/**
	 * @var Amy_Submit_Idea_Mail
	 */
	public $submit_idea_mail;

	/**
	 * Returns the singleton instance.
	 *
	 * @return Amy_Plugin
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Constructor.
	 */
	private function __construct() {
		$this->settings         = new Amy_Settings();
		$this->admin_menu       = new Amy_Admin_Menu( $this->settings );
		$this->api_client       = new Amy_Api_Client( $this->settings );
		$this->rest             = new Amy_Rest( $this->api_client, $this->settings );
		$this->theme_bridge     = new Amy_Theme_Bridge( $this->settings );
		$this->assets           = new Amy_Assets( $this->settings );
		$this->submit_idea      = new Amy_Submit_Idea( $this->settings );
		$this->submit_idea_mail = new Amy_Submit_Idea_Mail();

		$this->settings->register();
		$this->admin_menu->register();
		$this->rest->register();
		$this->theme_bridge->register();
		$this->assets->register();
		$this->submit_idea->register();
		$this->submit_idea_mail->register();
	}

	/**
	 * Activation: seed default options if missing.
	 */
	public static function activate() {
		$defaults = array(
			'amy_agent_enabled'       => '0',
			'amy_agent_service_url'   => 'http://127.0.0.1:8765',
			'amy_agent_shared_secret' => '',
			'amy_agent_ai_provider'   => 'gemini',
			'amy_agent_ai_api_key'    => '',
			'amy_agent_ai_model'      => '',
			'amy_agent_avatar_url'    => '',
		);

		foreach ( $defaults as $key => $value ) {
			if ( false === get_option( $key, false ) ) {
				add_option( $key, $value );
			}
		}
	}

	/**
	 * Deactivation hook (no destructive cleanup).
	 */
	public static function deactivate() {
		// Intentionally empty — options remain until uninstall.
	}
}
