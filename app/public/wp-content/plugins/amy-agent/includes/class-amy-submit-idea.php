<?php
/**
 * Submit Your Idea — conversational UI mount + assets.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Renders the Amy Submit Idea experience and enqueues its assets on the
 * Submit Your Idea page only.
 */
class Amy_Submit_Idea {

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
	 * Register theme hooks and asset enqueue.
	 */
	public function register() {
		add_filter( 'ogc_amy_agent_is_active', array( $this, 'filter_is_active' ) );
		add_action( 'ogc_submit_idea_render', array( $this, 'render' ) );
		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue' ) );
	}

	/**
	 * Theme filter: suppress the manual form when Amy is ready.
	 *
	 * @param bool $active Theme default.
	 * @return bool
	 */
	public function filter_is_active( $active ) {
		if ( $this->settings->is_ready() ) {
			return true;
		}
		return (bool) $active;
	}

	/**
	 * Whether the current request is the Submit Your Idea page.
	 *
	 * @return bool
	 */
	private function is_submit_idea_page() {
		if ( is_admin() ) {
			return false;
		}
		if ( is_page( 'submit-idea' ) ) {
			return true;
		}
		$slug = is_singular() ? (string) get_post_field( 'post_name', get_queried_object_id() ) : '';
		return 'submit-idea' === $slug;
	}

	/**
	 * Enqueue Submit Idea CSS/JS only on the Submit Your Idea page when ready.
	 */
	public function enqueue() {
		if ( ! $this->settings->is_ready() || ! $this->is_submit_idea_page() ) {
			return;
		}

		wp_enqueue_style(
			'amy-submit-idea',
			AMY_AGENT_URL . 'public/css/submit-idea.css',
			array(),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-submit-idea',
			AMY_AGENT_URL . 'public/js/submit-idea.js',
			array(),
			AMY_AGENT_VERSION,
			true
		);

		wp_enqueue_style(
			'amy-avatar',
			AMY_AGENT_URL . 'public/css/amy-avatar.css',
			array( 'amy-submit-idea' ),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-avatar',
			AMY_AGENT_URL . 'public/js/amy-avatar.js',
			array( 'amy-submit-idea', 'ogc-three' ),
			AMY_AGENT_VERSION,
			true
		);

		wp_localize_script(
			'amy-submit-idea',
			'amySubmitIdea',
			array(
				'restBase'  => esc_url_raw( rest_url( 'amy-agent/v1/submit-idea' ) ),
				'restNonce' => wp_create_nonce( 'wp_rest' ),
				'ajaxUrl'   => esc_url_raw( admin_url( 'admin-ajax.php' ) ),
				'ajaxNonce' => wp_create_nonce( 'amy_submit_idea_notify' ),
				'avatarBaseImage'       => esc_url_raw( AMY_AGENT_URL . 'public/images/amy-avatar-base.jpg' ),
				'avatarEyesImage'       => esc_url_raw( AMY_AGENT_URL . 'public/images/amy-avatar-eyes.png' ),
				'avatarMouthHappyImage' => esc_url_raw( AMY_AGENT_URL . 'public/images/amy-avatar-mouth-happy.png' ),
				'avatarMouthSadImage'   => esc_url_raw( AMY_AGENT_URL . 'public/images/amy-avatar-mouth-sad.png' ),
				'i18n'      => array(
					'chooseService'   => __( 'Choose a service to get started', 'amy-agent' ),
					'submitAnswers'   => __( 'Submit', 'amy-agent' ),
					'yes'             => __( 'Yes', 'amy-agent' ),
					'no'              => __( 'No', 'amy-agent' ),
					'send'            => __( 'Send', 'amy-agent' ),
					'thinking'        => __( 'Amy is typing…', 'amy-agent' ),
					'unavailable'     => __( 'Something went wrong. Please try again.', 'amy-agent' ),
					'required'        => __( 'Please fill in all required fields.', 'amy-agent' ),
					'emailRequired'   => __( 'Please enter a valid email address.', 'amy-agent' ),
					'emailLabel'      => __( 'Email', 'amy-agent' ),
					'whatsappLabel'   => __( 'WhatsApp (optional)', 'amy-agent' ),
					'contactSubmit'   => __( 'Send my idea', 'amy-agent' ),
					'uploadHint'      => __( 'Drag & drop files here, or click to browse (images, PDF, DOC — max 10 MB)', 'amy-agent' ),
					'uploadError'     => __( 'Could not upload that file.', 'amy-agent' ),
					'thankYou'        => __( 'Thank you — our team will respond within 48 hours to the email you provided.', 'amy-agent' ),
					'summaryPrompt'   => __( 'Does this summary look correct?', 'amy-agent' ),
					'deepDivePlaceholder' => __( 'Tell Amy what to change…', 'amy-agent' ),
					'startConversation' => __( 'Start', 'amy-agent' ),
				),
			)
		);
	}

	/**
	 * Theme action: mount point for the conversational Submit Idea UI.
	 */
	public function render() {
		if ( ! $this->settings->is_ready() ) {
			return;
		}

		echo '<div id="amy-submit-idea-root" class="amy-submit-idea" aria-live="polite"></div>';
	}
}
