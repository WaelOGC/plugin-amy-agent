<?php
/**
 * Front-end asset enqueue for the floating chat widget.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Loads the site-wide tracking beacon on every front-end page, and the
 * floating widget only when Amy is ready.
 */
class Amy_Assets {

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
	 * Register front-end hooks.
	 */
	public function register() {
		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue' ) );
		add_action( 'wp_footer', array( $this, 'render_mount' ), 5 );
	}

	/**
	 * Tracking beacon loads on every front-end page, independent of the widget.
	 */
	private function enqueue_tracking_beacon() {
		wp_enqueue_script(
			'amy-agent-tracking',
			AMY_AGENT_URL . 'public/js/tracking-beacon.js',
			array(),
			AMY_AGENT_VERSION,
			true
		);

		wp_localize_script(
			'amy-agent-tracking',
			'amyAgentTracking',
			array(
				'restUrl' => esc_url_raw( rest_url( 'amy-agent/v1/track' ) ),
				'nonce'   => wp_create_nonce( 'wp_rest' ),
			)
		);
	}

	/**
	 * Whether the floating widget should load on this request.
	 *
	 * @return bool
	 */
	private function should_load() {
		if ( is_admin() ) {
			return false;
		}
		return (bool) apply_filters( 'ogc_amy_agent_is_active', $this->settings->is_ready() );
	}

	/**
	 * Enqueue site-wide tracking beacon (always) and widget assets (when Amy is active).
	 */
	public function enqueue() {
		if ( is_admin() ) {
			return;
		}

		$this->enqueue_tracking_beacon();

		if ( ! $this->should_load() ) {
			return;
		}

		wp_enqueue_style(
			'amy-agent-widget',
			AMY_AGENT_URL . 'public/css/widget.css',
			array(),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-agent-widget',
			AMY_AGENT_URL . 'public/js/widget.js',
			array( 'amy-agent-tracking' ),
			AMY_AGENT_VERSION,
			true
		);

		wp_localize_script(
			'amy-agent-widget',
			'amyAgentWidget',
			array(
				'restUrl'   => esc_url_raw( rest_url( 'amy-agent/v1/chat' ) ),
				'nonce'     => wp_create_nonce( 'wp_rest' ),
				'pageUrl'   => esc_url_raw( home_url( add_query_arg( array() ) ) ),
				'pageSlug'  => is_singular() ? (string) get_post_field( 'post_name', get_queried_object_id() ) : '',
				'avatarUrl' => esc_url_raw( $this->settings->get_avatar_url() ),
				'i18n'      => array(
					'title'         => __( 'Amy', 'amy-agent' ),
					'subtitle'      => __( 'OGC NewFinity assistant', 'amy-agent' ),
					'placeholder'   => __( 'Ask Amy anything…', 'amy-agent' ),
					'send'          => __( 'Send', 'amy-agent' ),
					'open'          => __( 'Open Amy chat', 'amy-agent' ),
					'close'         => __( 'Close Amy chat', 'amy-agent' ),
					'unavailable'   => __( 'Amy is unavailable right now.', 'amy-agent' ),
					'thinking'      => __( 'Amy is typing…', 'amy-agent' ),
					'greeting'      => __( 'Hi — I\'m Amy. How can I help you today?', 'amy-agent' ),
				),
			)
		);
	}

	/**
	 * Mount point for the widget (JS builds the UI inside).
	 */
	public function render_mount() {
		if ( ! $this->should_load() ) {
			return;
		}
		echo '<div id="amy-agent-root" class="amy-agent-root" hidden></div>';
	}
}
