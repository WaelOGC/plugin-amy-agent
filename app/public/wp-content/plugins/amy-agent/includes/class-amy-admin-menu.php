<?php
/**
 * Top-level Amy admin menu and dashboard pages.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers Amy → Overview / Settings / Brand & Avatar / placeholders in wp-admin.
 */
class Amy_Admin_Menu {

	const PARENT_SLUG     = 'amy-overview';
	const BRAND_PAGE_SLUG = 'amy-brand-avatar';

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @param Amy_Settings $settings Settings instance (existing settings page).
	 */
	public function __construct( Amy_Settings $settings ) {
		$this->settings = $settings;
	}

	/**
	 * Wire admin menu hooks.
	 */
	public function register() {
		add_action( 'admin_menu', array( $this, 'add_menu' ) );
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_assets' ) );
	}

	/**
	 * Register top-level Amy menu and subpages.
	 */
	public function add_menu() {
		add_menu_page(
			__( 'Amy', 'amy-agent' ),
			__( 'Amy', 'amy-agent' ),
			'manage_options',
			self::PARENT_SLUG,
			array( $this, 'render_overview' ),
			'dashicons-format-chat',
			58
		);

		add_submenu_page(
			self::PARENT_SLUG,
			__( 'Overview', 'amy-agent' ),
			__( 'Overview', 'amy-agent' ),
			'manage_options',
			self::PARENT_SLUG,
			array( $this, 'render_overview' )
		);

		add_submenu_page(
			self::PARENT_SLUG,
			__( 'Settings', 'amy-agent' ),
			__( 'Settings', 'amy-agent' ),
			'manage_options',
			Amy_Settings::PAGE_SLUG,
			array( $this->settings, 'render_page' )
		);

		add_submenu_page(
			self::PARENT_SLUG,
			__( 'Brand & Avatar', 'amy-agent' ),
			__( 'Brand & Avatar', 'amy-agent' ),
			'manage_options',
			self::BRAND_PAGE_SLUG,
			array( $this, 'render_brand_page' )
		);

		$placeholders = array(
			'amy-chat'            => __( 'Chat', 'amy-agent' ),
			'amy-analytics'       => __( 'Analytics', 'amy-agent' ),
			'amy-seo-tasks'       => __( 'SEO Tasks', 'amy-agent' ),
			'amy-email-marketing' => __( 'Email Marketing', 'amy-agent' ),
		);

		foreach ( $placeholders as $slug => $title ) {
			add_submenu_page(
				self::PARENT_SLUG,
				$title,
				$title,
				'manage_options',
				$slug,
				function () use ( $title ) {
					$this->render_placeholder( $title );
				}
			);
		}
	}

	/**
	 * Enqueue overview / brand assets on their screens only.
	 *
	 * @param string $hook_suffix Current admin page hook.
	 */
	public function enqueue_assets( $hook_suffix ) {
		if ( 'toplevel_page_amy-overview' === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-overview',
				AMY_AGENT_URL . 'admin/css/admin-overview.css',
				array(),
				AMY_AGENT_VERSION
			);
			return;
		}

		if ( 'amy-overview_page_amy-brand-avatar' !== $hook_suffix ) {
			return;
		}

		wp_enqueue_media();

		wp_enqueue_style(
			'amy-agent-admin-brand',
			AMY_AGENT_URL . 'admin/css/admin-brand.css',
			array(),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-agent-admin-brand',
			AMY_AGENT_URL . 'admin/js/admin-brand.js',
			array( 'jquery' ),
			AMY_AGENT_VERSION,
			true
		);

		wp_localize_script(
			'amy-agent-admin-brand',
			'amyAgentBrand',
			array(
				'defaultAvatarUrl' => esc_url_raw( $this->settings->get_default_avatar_url() ),
				'i18n'             => array(
					'title'       => __( 'Select Amy avatar', 'amy-agent' ),
					'button'      => __( 'Use this image', 'amy-agent' ),
					'invalidType' => __( 'Please choose a JPG, PNG, or WebP image.', 'amy-agent' ),
				),
			)
		);
	}

	/**
	 * Overview dashboard with links to each Amy section.
	 */
	public function render_overview() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$cards = array(
			array(
				'slug'        => Amy_Settings::PAGE_SLUG,
				'title'       => __( 'Settings', 'amy-agent' ),
				'description' => __( 'Connect the Python service, shared secret, and AI provider.', 'amy-agent' ),
			),
			array(
				'slug'        => self::BRAND_PAGE_SLUG,
				'title'       => __( 'Brand & Avatar', 'amy-agent' ),
				'description' => __( 'Manage Amy’s look, name, and avatar.', 'amy-agent' ),
			),
			array(
				'slug'        => 'amy-chat',
				'title'       => __( 'Chat', 'amy-agent' ),
				'description' => __( 'Configure chat behavior and conversation settings.', 'amy-agent' ),
			),
			array(
				'slug'        => 'amy-analytics',
				'title'       => __( 'Analytics', 'amy-agent' ),
				'description' => __( 'Review usage and performance insights.', 'amy-agent' ),
			),
			array(
				'slug'        => 'amy-seo-tasks',
				'title'       => __( 'SEO Tasks', 'amy-agent' ),
				'description' => __( 'Plan and track SEO-related work for Amy.', 'amy-agent' ),
			),
			array(
				'slug'        => 'amy-email-marketing',
				'title'       => __( 'Email Marketing', 'amy-agent' ),
				'description' => __( 'Email campaigns and automation powered by Amy.', 'amy-agent' ),
			),
		);
		?>
		<div class="wrap amy-agent-overview">
			<h1><?php echo esc_html__( 'Amy', 'amy-agent' ); ?></h1>
			<p class="amy-agent-overview__intro">
				<?php echo esc_html__( 'Your digital employee dashboard. Choose a section to get started.', 'amy-agent' ); ?>
			</p>
			<div class="amy-agent-overview__grid">
				<?php foreach ( $cards as $card ) : ?>
					<a class="amy-agent-overview__card" href="<?php echo esc_url( admin_url( 'admin.php?page=' . $card['slug'] ) ); ?>">
						<h2 class="amy-agent-overview__card-title"><?php echo esc_html( $card['title'] ); ?></h2>
						<p class="amy-agent-overview__card-desc"><?php echo esc_html( $card['description'] ); ?></p>
					</a>
				<?php endforeach; ?>
			</div>
		</div>
		<?php
	}

	/**
	 * Brand & Avatar settings (custom avatar via Media Library).
	 */
	public function render_brand_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$custom  = $this->settings->get_custom_avatar_url();
		$preview = $this->settings->get_avatar_url();
		$default = $this->settings->get_default_avatar_url();
		?>
		<div class="wrap amy-agent-brand">
			<h1><?php echo esc_html__( 'Brand & Avatar', 'amy-agent' ); ?></h1>
			<p class="amy-agent-brand__hint">
				<?php echo esc_html__( 'Choose the avatar shown on Amy’s floating chat button and chat header. JPG, PNG, or WebP recommended.', 'amy-agent' ); ?>
			</p>

			<?php settings_errors(); ?>

			<form method="post" action="options.php">
				<?php settings_fields( 'amy_agent_settings' ); ?>

				<div class="amy-agent-brand__preview-wrap">
					<img
						id="amy-agent-avatar-preview"
						class="amy-agent-brand__preview"
						src="<?php echo esc_url( $preview ); ?>"
						alt="<?php echo esc_attr__( 'Amy avatar preview', 'amy-agent' ); ?>"
						width="96"
						height="96"
						decoding="async"
					/>
				</div>

				<input
					type="hidden"
					id="amy_agent_avatar_url"
					name="<?php echo esc_attr( Amy_Settings::OPTION_AVATAR_URL ); ?>"
					value="<?php echo esc_attr( $custom ); ?>"
				/>

				<div class="amy-agent-brand__actions">
					<button type="button" class="button" id="amy-agent-select-avatar">
						<?php echo esc_html__( 'Select image', 'amy-agent' ); ?>
					</button>
					<button type="button" class="button" id="amy-agent-reset-avatar">
						<?php echo esc_html__( 'Reset to default', 'amy-agent' ); ?>
					</button>
					<?php submit_button( __( 'Save', 'amy-agent' ), 'primary', 'submit', false ); ?>
				</div>

				<p class="description">
					<?php
					if ( '' === $custom ) {
						echo esc_html__( 'Currently using the bundled default avatar. Select a custom image and save to replace it.', 'amy-agent' );
					} else {
						echo esc_html__( 'A custom avatar is saved. Reset to default clears it after you save.', 'amy-agent' );
					}
					?>
				</p>
				<p class="description screen-reader-text">
					<?php echo esc_html( $default ); ?>
				</p>
			</form>
		</div>
		<?php
	}

	/**
	 * Empty placeholder admin page.
	 *
	 * @param string $title Page title.
	 */
	public function render_placeholder( $title ) {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap">
			<h1><?php echo esc_html( $title ); ?></h1>
			<p><?php echo esc_html__( 'Coming soon.', 'amy-agent' ); ?></p>
		</div>
		<?php
	}
}
