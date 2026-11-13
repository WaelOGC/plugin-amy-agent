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
				'restUrl'        => esc_url_raw( rest_url( 'amy-agent/v1/chat' ) ),
				'nonce'          => wp_create_nonce( 'wp_rest' ),
				'pageUrl'        => esc_url_raw( home_url( add_query_arg( array() ) ) ),
				'pageSlug'       => is_singular() ? (string) get_post_field( 'post_name', get_queried_object_id() ) : '',
				'avatarUrl'      => esc_url_raw( $this->settings->get_avatar_url() ),
				'closingWishes'  => $this->settings->is_closing_wishes_enabled(),
				'uploadsEnabled' => $this->settings->is_public_chat_uploads_enabled(),
				'uploadNotify'   => $this->settings->is_public_chat_upload_notify_enabled(),
				'uploadUrl'      => esc_url_raw( rest_url( 'amy-agent/v1/chat/upload' ) ),
				'filesUrl'       => esc_url_raw( rest_url( 'amy-agent/v1/chat/files' ) ),
				'i18n'           => array(
					'title'             => __( 'Amy', 'amy-agent' ),
					'subtitle'          => __( 'OGC NewFinity assistant', 'amy-agent' ),
					'subtitleCompact'   => __( 'AI assistant', 'amy-agent' ),
					'subtitleExpanded'  => __( 'OGC NewFinity assistant', 'amy-agent' ),
					'placeholder'       => __( 'Ask Amy anything…', 'amy-agent' ),
					'attach'            => __( 'Attach a file', 'amy-agent' ),
					'attachUploadImage' => __( 'Upload image', 'amy-agent' ),
					'attachUploadImageHint' => __( 'JPEG, PNG, WebP', 'amy-agent' ),
					'attachUploadDoc'   => __( 'Upload document', 'amy-agent' ),
					'attachUploadDocHint' => __( 'PDF, up to 10 pages', 'amy-agent' ),
					'uploadInfo'        => __( 'Upload information', 'amy-agent' ),
					'uploadInfoAccepted' => __( 'Accepted: JPEG, PNG, WebP images and PDF (max 10 pages)', 'amy-agent' ),
					'uploadInfoLimits'  => __( 'Up to 5 MB per file, up to 3 files per message', 'amy-agent' ),
					'uploadInfoSensitive' => __( "Please don't upload sensitive personal data.", 'amy-agent' ),
					'uploadInfoRetention' => __( 'Files are deleted automatically after 7 days.', 'amy-agent' ),
					'sensitiveNotice'   => __( "Please don't upload sensitive personal data.", 'amy-agent' ),
					'fileExpired'       => __( 'File expired', 'amy-agent' ),
					'removeFile'        => __( 'Remove attachment', 'amy-agent' ),
					'uploadFailed'      => __( 'Could not upload that file.', 'amy-agent' ),
					'uploadRateLimited' => __( "You've reached the upload limit for now, please try again in a bit.", 'amy-agent' ),
					'tooManyFiles'      => __( 'You can only attach a few files at a time.', 'amy-agent' ),
					'send'            => __( 'Send', 'amy-agent' ),
					'open'            => __( 'Open Amy chat', 'amy-agent' ),
					'close'           => __( 'Close Amy chat', 'amy-agent' ),
					'unavailable'     => __( 'Amy is unavailable right now.', 'amy-agent' ),
					'thinking'        => __( 'Amy is typing…', 'amy-agent' ),
					'greeting'        => __( 'Hi — I\'m Amy. How can I help you today?', 'amy-agent' ),
					'newChat'         => __( 'New chat', 'amy-agent' ),
					'history'         => __( 'History', 'amy-agent' ),
					'expand'          => __( 'Expand chat', 'amy-agent' ),
					'collapse'        => __( 'Collapse chat', 'amy-agent' ),
					'historyEmpty'    => __( 'No previous chats yet.', 'amy-agent' ),
					'historyBack'     => __( 'Back to chat', 'amy-agent' ),
					'today'           => __( 'Today', 'amy-agent' ),
					'yesterday'       => __( 'Yesterday', 'amy-agent' ),
					'untitledChat'    => __( 'Chat', 'amy-agent' ),
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
