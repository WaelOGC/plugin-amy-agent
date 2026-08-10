<?php
/**
 * Top-level Amy admin menu and dashboard pages.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers Amy → Overview / My Profile / Settings / Brand & Avatar / placeholders in wp-admin.
 */
class Amy_Admin_Menu {

	const PARENT_SLUG          = 'amy-overview';
	const MY_PROFILE_PAGE_SLUG = 'amy-my-profile';
	const BRAND_PAGE_SLUG      = 'amy-brand-avatar';

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @var string|false|null
	 */
	private $hook_overview;

	/**
	 * @var string|false|null
	 */
	private $hook_my_profile;

	/**
	 * @var string|false|null
	 */
	private $hook_settings;

	/**
	 * @var string|false|null
	 */
	private $hook_brand;

	/**
	 * @var array<string, string|false>
	 */
	private $hook_placeholders = array();

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

		$this->hook_overview = add_submenu_page(
			self::PARENT_SLUG,
			__( 'Overview', 'amy-agent' ),
			__( 'Overview', 'amy-agent' ),
			'manage_options',
			self::PARENT_SLUG,
			array( $this, 'render_overview' )
		);

		$this->hook_my_profile = add_submenu_page(
			self::PARENT_SLUG,
			__( 'My Profile', 'amy-agent' ),
			__( 'My Profile', 'amy-agent' ),
			'manage_options',
			self::MY_PROFILE_PAGE_SLUG,
			array( $this, 'render_my_profile' )
		);

		$this->hook_settings = add_submenu_page(
			self::PARENT_SLUG,
			__( 'Settings', 'amy-agent' ),
			__( 'Settings', 'amy-agent' ),
			'manage_options',
			Amy_Settings::PAGE_SLUG,
			array( $this->settings, 'render_page' )
		);
		$this->settings->set_page_hook( $this->hook_settings );

		$this->hook_brand = add_submenu_page(
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
			$this->hook_placeholders[ $slug ] = add_submenu_page(
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
	 * Enqueue overview / my profile / brand assets on their screens only.
	 *
	 * @param string $hook_suffix Current admin page hook.
	 */
	public function enqueue_assets( $hook_suffix ) {
		if ( $this->hook_overview === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-overview-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-overview',
				AMY_AGENT_URL . 'admin/css/admin-overview.css',
				array( 'amy-agent-admin-overview-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);
			return;
		}

		if ( $this->hook_my_profile === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-my-profile-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-my-profile',
				AMY_AGENT_URL . 'admin/css/admin-my-profile.css',
				array( 'amy-agent-admin-my-profile-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);
			return;
		}

		if ( $this->hook_brand !== $hook_suffix ) {
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

		$coming_soon = __( '(coming soon)', 'amy-agent' );

		$top_stats = array(
			// TODO: wire to Task Service once built.
			array(
				'label' => __( 'Tasks in Progress', 'amy-agent' ),
			),
			// TODO: wire to Task Service once built.
			array(
				'label' => __( 'Tasks Due Soon', 'amy-agent' ),
			),
			// TODO: wire to Chat once built.
			array(
				'label' => __( 'Chats This Week', 'amy-agent' ),
			),
			// TODO: wire to SEO Tasks once built.
			array(
				'label' => __( 'Average SEO Score', 'amy-agent' ),
			),
		);

		$cards = array(
			array(
				// TODO: point to amy-task-service once its menu page exists.
				'slug'        => '',
				'href'        => '#',
				'title'       => __( 'Task Service', 'amy-agent' ),
				'description' => __( 'Assign, track, and escalate work across the team and Amy.', 'amy-agent' ),
				'icon'        => 'yes-alt',
				'hero'        => true,
				'metrics'     => array(
					// TODO: wire to Task Service once built.
					__( 'Open', 'amy-agent' ),
					// TODO: wire to Task Service once built.
					__( 'Urgent', 'amy-agent' ),
				),
			),
			array(
				'slug'        => 'amy-analytics',
				'title'       => __( 'Analytics', 'amy-agent' ),
				'description' => __( 'Review site usage and performance insights.', 'amy-agent' ),
				'icon'        => 'chart-bar',
				'metrics'     => array(
					// TODO: wire to Analytics once built.
					__( 'Visitors', 'amy-agent' ),
					// TODO: wire to Analytics once built.
					__( 'Page views', 'amy-agent' ),
				),
			),
			array(
				'slug'        => 'amy-seo-tasks',
				'title'       => __( 'SEO Tasks', 'amy-agent' ),
				'description' => __( 'Find and fix SEO issues across your content.', 'amy-agent' ),
				'icon'        => 'search',
				'metrics'     => array(
					// TODO: wire to SEO Tasks once built.
					__( 'Open issues', 'amy-agent' ),
					// TODO: wire to SEO Tasks once built.
					__( 'Fixed', 'amy-agent' ),
				),
			),
			array(
				'slug'        => 'amy-email-marketing',
				'title'       => __( 'Email Marketing', 'amy-agent' ),
				'description' => __( 'One-to-one sends and campaign status powered by Amy.', 'amy-agent' ),
				'icon'        => 'email',
				'metrics'     => array(
					// TODO: wire to Email Marketing once built.
					__( 'Open rate', 'amy-agent' ),
					// TODO: wire to Email Marketing once built.
					__( 'Drafts', 'amy-agent' ),
				),
			),
			array(
				'slug'        => 'amy-chat',
				'title'       => __( 'Chat', 'amy-agent' ),
				'description' => __( 'Talk with Amy the Leader from the dashboard.', 'amy-agent' ),
				'icon'        => 'format-chat',
				'metrics'     => array(
					// TODO: wire to Chat once built.
					__( 'Active now', 'amy-agent' ),
					// TODO: wire to Chat once built.
					__( 'This week', 'amy-agent' ),
				),
			),
			array(
				// TODO: point to amy-admin-roles once its menu page exists.
				'slug'        => '',
				'href'        => '#',
				'title'       => __( 'Admin Roles & Social', 'amy-agent' ),
				'description' => __( 'Team permissions and connected social platforms.', 'amy-agent' ),
				'icon'        => 'groups',
				'metrics'     => array(
					// TODO: wire to Admin Roles & Social once built.
					__( 'Team members', 'amy-agent' ),
					// TODO: wire to Admin Roles & Social once built.
					__( 'Platforms', 'amy-agent' ),
				),
			),
			array(
				'slug'        => Amy_Settings::PAGE_SLUG,
				'title'       => __( 'Settings', 'amy-agent' ),
				'description' => __( 'Connect the Python service, shared secret, and AI provider.', 'amy-agent' ),
				'icon'        => 'admin-generic',
			),
			array(
				'slug'        => self::BRAND_PAGE_SLUG,
				'title'       => __( 'Brand & Avatar', 'amy-agent' ),
				'description' => __( 'Manage Amy’s look, name, and avatar.', 'amy-agent' ),
				'icon'        => 'admin-users',
			),
		);
		?>
		<div class="wrap amy-agent-overview">
			<header class="amy-agent-overview__header">
				<span class="amy-agent-overview__eyebrow"><?php echo esc_html__( 'AMY · DIGITAL EMPLOYEE', 'amy-agent' ); ?></span>
				<h1 class="amy-agent-overview__title"><?php echo esc_html__( 'Overview', 'amy-agent' ); ?></h1>
				<p class="amy-agent-overview__intro">
					<?php echo esc_html__( 'Your command center — status of every Amy tool at a glance.', 'amy-agent' ); ?>
				</p>
				<span class="amy-agent-overview__underline" aria-hidden="true"></span>
				<div class="amy-agent-overview__orbit" aria-hidden="true">
					<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" focusable="false">
						<circle cx="60" cy="60" r="10" fill="currentColor" opacity="0.9"/>
						<ellipse cx="60" cy="60" rx="48" ry="18" stroke="currentColor" stroke-width="1.5" transform="rotate(0 60 60)"/>
						<ellipse cx="60" cy="60" rx="48" ry="18" stroke="currentColor" stroke-width="1.5" transform="rotate(60 60 60)"/>
						<ellipse cx="60" cy="60" rx="48" ry="18" stroke="currentColor" stroke-width="1.5" transform="rotate(120 60 60)"/>
						<circle cx="108" cy="60" r="3" fill="currentColor"/>
						<circle cx="36" cy="18.5" r="2.5" fill="currentColor"/>
						<circle cx="36" cy="101.5" r="2.5" fill="currentColor"/>
					</svg>
				</div>
			</header>

			<div class="amy-agent-overview__stats">
				<?php foreach ( $top_stats as $stat ) : ?>
					<div class="amy-agent-overview__stat">
						<p class="amy-agent-overview__stat-label"><?php echo esc_html( $stat['label'] ); ?></p>
						<p class="amy-agent-overview__stat-value">
							—
							<span class="amy-agent-overview__coming-soon"><?php echo esc_html( $coming_soon ); ?></span>
						</p>
					</div>
				<?php endforeach; ?>
			</div>

			<div class="amy-agent-overview__grid">
				<?php foreach ( $cards as $card ) : ?>
					<?php
					$is_hero = ! empty( $card['hero'] );
					$card_classes = 'amy-agent-overview__card';
					if ( $is_hero ) {
						$card_classes .= ' amy-agent-overview__card--hero';
					}

					if ( ! empty( $card['href'] ) ) {
						$card_url = $card['href'];
					} else {
						$card_url = admin_url( 'admin.php?page=' . $card['slug'] );
					}
					?>
					<article class="<?php echo esc_attr( $card_classes ); ?>">
						<div class="amy-agent-overview__card-top">
							<span class="amy-agent-overview__card-icon" aria-hidden="true">
								<span class="dashicons dashicons-<?php echo esc_attr( $card['icon'] ); ?>"></span>
							</span>
							<div class="amy-agent-overview__card-heading">
								<h2 class="amy-agent-overview__card-title"><?php echo esc_html( $card['title'] ); ?></h2>
								<p class="amy-agent-overview__card-desc"><?php echo esc_html( $card['description'] ); ?></p>
							</div>
						</div>

						<?php if ( ! empty( $card['metrics'] ) ) : ?>
							<div class="amy-agent-overview__card-metrics">
								<?php foreach ( $card['metrics'] as $metric_label ) : ?>
									<div class="amy-agent-overview__card-metric">
										<p class="amy-agent-overview__card-metric-label"><?php echo esc_html( $metric_label ); ?></p>
										<p class="amy-agent-overview__card-metric-value">
											—
											<span class="amy-agent-overview__coming-soon"><?php echo esc_html( $coming_soon ); ?></span>
										</p>
									</div>
								<?php endforeach; ?>
							</div>
						<?php endif; ?>

						<a
							class="amy-agent-overview__card-link"
							href="<?php echo '#' === $card_url ? '#' : esc_url( $card_url ); ?>"
						>
							<?php echo esc_html__( 'See more →', 'amy-agent' ); ?>
						</a>
					</article>
				<?php endforeach; ?>
			</div>
		</div>
		<?php
	}

	/**
	 * My Profile — personal task activity for the logged-in user.
	 */
	public function render_my_profile() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap amy-agent-my-profile">
			<header class="amy-agent-my-profile__header">
				<h1 class="amy-agent-my-profile__title"><?php echo esc_html__( 'My Profile', 'amy-agent' ); ?></h1>
				<p class="amy-agent-my-profile__intro">
					<?php echo esc_html__( 'Your personal task activity.', 'amy-agent' ); ?>
				</p>
				<span class="amy-agent-my-profile__underline" aria-hidden="true"></span>
			</header>

			<div class="amy-agent-my-profile__sections">
				<section class="amy-agent-my-profile__section">
					<h2 class="amy-agent-my-profile__section-title"><?php echo esc_html__( 'Open Tasks', 'amy-agent' ); ?></h2>
					<?php
					// TODO: replace empty state with real task query once Task Service exists.
					?>
					<div class="amy-agent-my-profile__empty">
						<span class="amy-agent-my-profile__empty-icon" aria-hidden="true">
							<span class="dashicons dashicons-clipboard"></span>
						</span>
						<p class="amy-agent-my-profile__empty-text">
							<?php echo esc_html__( 'No tasks yet — Task Service is being built next.', 'amy-agent' ); ?>
						</p>
					</div>
				</section>

				<section class="amy-agent-my-profile__section">
					<h2 class="amy-agent-my-profile__section-title"><?php echo esc_html__( 'Completed Tasks', 'amy-agent' ); ?></h2>
					<?php
					// TODO: replace empty state with real task query once Task Service exists.
					?>
					<div class="amy-agent-my-profile__empty">
						<span class="amy-agent-my-profile__empty-icon" aria-hidden="true">
							<span class="dashicons dashicons-yes-alt"></span>
						</span>
						<p class="amy-agent-my-profile__empty-text">
							<?php echo esc_html__( 'Nothing completed yet.', 'amy-agent' ); ?>
						</p>
					</div>
				</section>

				<section class="amy-agent-my-profile__section">
					<h2 class="amy-agent-my-profile__section-title"><?php echo esc_html__( 'Recent Activity', 'amy-agent' ); ?></h2>
					<?php
					// TODO: replace empty state with real activity query once Task Service exists.
					?>
					<div class="amy-agent-my-profile__empty">
						<span class="amy-agent-my-profile__empty-icon" aria-hidden="true">
							<span class="dashicons dashicons-backup"></span>
						</span>
						<p class="amy-agent-my-profile__empty-text">
							<?php echo esc_html__( 'No activity yet.', 'amy-agent' ); ?>
						</p>
					</div>
				</section>
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
