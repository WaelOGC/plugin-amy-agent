<?php
/**
 * Top-level Amy admin menu and dashboard pages.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers Amy → Overview / Settings / placeholders in wp-admin.
 */
class Amy_Admin_Menu {

	const PARENT_SLUG = 'amy-overview';

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

		$placeholders = array(
			'amy-brand-avatar'    => __( 'Brand & Avatar', 'amy-agent' ),
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
	 * Enqueue overview styles on the Amy overview screen.
	 *
	 * @param string $hook_suffix Current admin page hook.
	 */
	public function enqueue_assets( $hook_suffix ) {
		if ( 'toplevel_page_amy-overview' !== $hook_suffix ) {
			return;
		}

		wp_enqueue_style(
			'amy-agent-admin-overview',
			AMY_AGENT_URL . 'admin/css/admin-overview.css',
			array(),
			AMY_AGENT_VERSION
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
				'slug'        => 'amy-brand-avatar',
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
