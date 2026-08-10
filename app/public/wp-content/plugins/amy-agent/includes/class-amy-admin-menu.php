<?php
/**
 * Top-level Amy admin menu and dashboard pages.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers Amy → Overview / My Profile / Task Service / Settings / Brand & Avatar / placeholders in wp-admin.
 */
class Amy_Admin_Menu {

	const PARENT_SLUG             = 'amy-overview';
	const MY_PROFILE_PAGE_SLUG    = 'amy-my-profile';
	const TASK_SERVICE_PAGE_SLUG  = 'amy-task-service';
	const BRAND_PAGE_SLUG         = 'amy-brand-avatar';
	const USER_AVATAR_META        = 'amy_agent_user_avatar_url';

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
	private $hook_task_service;

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
		add_action( 'wp_ajax_amy_agent_save_my_profile', array( $this, 'ajax_save_my_profile' ) );
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

		$this->hook_task_service = add_submenu_page(
			self::PARENT_SLUG,
			__( 'Task Service', 'amy-agent' ),
			__( 'Task Service', 'amy-agent' ),
			'manage_options',
			self::TASK_SERVICE_PAGE_SLUG,
			array( $this, 'render_task_service' )
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
			wp_enqueue_media();

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

			wp_enqueue_script(
				'amy-agent-admin-my-profile',
				AMY_AGENT_URL . 'admin/js/admin-my-profile.js',
				array( 'jquery' ),
				AMY_AGENT_VERSION,
				true
			);

			$user = wp_get_current_user();
			wp_localize_script(
				'amy-agent-admin-my-profile',
				'amyAgentMyProfile',
				array(
					'ajaxUrl'     => admin_url( 'admin-ajax.php' ),
					'nonce'       => wp_create_nonce( 'amy_agent_save_my_profile' ),
					'gravatarUrl' => esc_url_raw( get_avatar_url( $user->ID, array( 'size' => 144 ) ) ),
					'i18n'        => array(
						'mediaTitle'   => __( 'Select profile photo', 'amy-agent' ),
						'mediaButton'  => __( 'Use this image', 'amy-agent' ),
						'invalidType'  => __( 'Please choose a JPG, PNG, or WebP image.', 'amy-agent' ),
						'invalidEmail' => __( 'Please enter a valid email address.', 'amy-agent' ),
						'saving'       => __( 'Saving…', 'amy-agent' ),
						'save'         => __( 'Save changes', 'amy-agent' ),
						'error'        => __( 'Could not save profile. Please try again.', 'amy-agent' ),
					),
				)
			);
			return;
		}

		if ( $this->hook_task_service === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-task-service-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-task-service',
				AMY_AGENT_URL . 'admin/css/admin-task-service.css',
				array( 'amy-agent-admin-task-service-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);

			wp_enqueue_script(
				'amy-agent-admin-task-service',
				AMY_AGENT_URL . 'admin/js/admin-task-service.js',
				array( 'jquery' ),
				AMY_AGENT_VERSION,
				true
			);

			wp_localize_script(
				'amy-agent-admin-task-service',
				'amyAgentTaskService',
				array(
					'tasks' => $this->get_placeholder_tasks(),
					'i18n'  => array(
						'comingSoon' => __( 'Coming soon — task creation will be available once the data layer is built.', 'amy-agent' ),
						'noResults'  => __( 'No tasks match your filters.', 'amy-agent' ),
					),
				)
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
				'slug'        => self::TASK_SERVICE_PAGE_SLUG,
				'title'       => __( 'Task Service', 'amy-agent' ),
				'description' => __( 'Assign, track, and escalate work across the team and Amy.', 'amy-agent' ),
				'icon'        => 'yes-alt',
				'hero'        => true,
				'metrics'     => array(
					// TODO: wire to Task Service real counts once the data layer is built.
					__( 'Open', 'amy-agent' ),
					// TODO: wire to Task Service real counts once the data layer is built.
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
	 * Task Service — visual board/list surface (static placeholder data this phase).
	 */
	public function render_task_service() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$coming_soon = __( '(coming soon)', 'amy-agent' );
		$stats       = array(
			array(
				'label' => __( 'Open Tasks', 'amy-agent' ),
				'icon'  => 'clipboard',
			),
			array(
				'label' => __( 'Urgent Tasks', 'amy-agent' ),
				'icon'  => 'warning',
			),
			array(
				'label' => __( 'Completed This Week', 'amy-agent' ),
				'icon'  => 'yes-alt',
			),
			array(
				'label' => __( 'Team Completion Rate', 'amy-agent' ),
				'icon'  => 'chart-bar',
			),
		);

		$columns = array(
			'todo'              => __( 'To Do', 'amy-agent' ),
			'in_progress'       => __( 'In Progress', 'amy-agent' ),
			'waiting_extension' => __( 'Waiting on Extension', 'amy-agent' ),
			'done'              => __( 'Done', 'amy-agent' ),
		);
		?>
		<div class="wrap amy-agent-task-service" id="amy-agent-task-service">
			<header class="amy-agent-task-service__header">
				<div class="amy-agent-task-service__header-main">
					<h1 class="amy-agent-task-service__title"><?php echo esc_html__( 'Task Service', 'amy-agent' ); ?></h1>
					<p class="amy-agent-task-service__intro">
						<?php echo esc_html__( 'Every task, every assignee, fully transparent.', 'amy-agent' ); ?>
					</p>
					<span class="amy-agent-task-service__underline" aria-hidden="true"></span>
				</div>
				<div class="amy-agent-task-service__header-actions">
					<button
						type="button"
						class="amy-agent-task-service__btn amy-agent-task-service__btn--accent"
						id="amy-agent-task-new"
					>
						<?php echo esc_html__( '+ New Task', 'amy-agent' ); ?>
					</button>
				</div>
			</header>

			<div class="amy-agent-task-service__stats">
				<?php foreach ( $stats as $stat ) : ?>
					<div class="amy-agent-task-service__stat">
						<span class="amy-agent-task-service__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-<?php echo esc_attr( $stat['icon'] ); ?>"></span>
						</span>
						<div class="amy-agent-task-service__stat-body">
							<p class="amy-agent-task-service__stat-label"><?php echo esc_html( $stat['label'] ); ?></p>
							<p class="amy-agent-task-service__stat-value">
								—
								<span class="amy-agent-task-service__coming-soon"><?php echo esc_html( $coming_soon ); ?></span>
							</p>
						</div>
					</div>
				<?php endforeach; ?>
			</div>

			<div class="amy-agent-task-service__toolbar">
				<div class="amy-agent-task-service__view-toggle" role="tablist" aria-label="<?php echo esc_attr__( 'Task view', 'amy-agent' ); ?>">
					<button
						type="button"
						class="amy-agent-task-service__view-btn is-active"
						role="tab"
						aria-selected="true"
						data-amy-view="board"
						id="amy-agent-view-board"
					>
						<?php echo esc_html__( 'Board', 'amy-agent' ); ?>
					</button>
					<button
						type="button"
						class="amy-agent-task-service__view-btn"
						role="tab"
						aria-selected="false"
						data-amy-view="list"
						id="amy-agent-view-list"
					>
						<?php echo esc_html__( 'List', 'amy-agent' ); ?>
					</button>
				</div>

				<div class="amy-agent-task-service__filters">
					<label class="screen-reader-text" for="amy-agent-filter-assignee"><?php echo esc_html__( 'Filter by assignee', 'amy-agent' ); ?></label>
					<select id="amy-agent-filter-assignee" class="amy-agent-task-service__select">
						<option value=""><?php echo esc_html__( 'All Assignees', 'amy-agent' ); ?></option>
					</select>

					<label class="screen-reader-text" for="amy-agent-filter-priority"><?php echo esc_html__( 'Filter by priority', 'amy-agent' ); ?></label>
					<select id="amy-agent-filter-priority" class="amy-agent-task-service__select">
						<option value=""><?php echo esc_html__( 'All Priorities', 'amy-agent' ); ?></option>
						<option value="normal"><?php echo esc_html__( 'Normal', 'amy-agent' ); ?></option>
						<option value="urgent"><?php echo esc_html__( 'Urgent', 'amy-agent' ); ?></option>
					</select>

					<label class="screen-reader-text" for="amy-agent-filter-search"><?php echo esc_html__( 'Search tasks', 'amy-agent' ); ?></label>
					<input
						type="search"
						id="amy-agent-filter-search"
						class="amy-agent-task-service__search"
						placeholder="<?php echo esc_attr__( 'Search tasks...', 'amy-agent' ); ?>"
					/>
				</div>
			</div>

			<div
				class="amy-agent-task-service__board"
				id="amy-agent-task-board"
				role="tabpanel"
				aria-labelledby="amy-agent-view-board"
			>
				<?php foreach ( $columns as $status_key => $status_label ) : ?>
					<section class="amy-agent-task-service__column" data-status="<?php echo esc_attr( $status_key ); ?>">
						<header class="amy-agent-task-service__column-header">
							<h2 class="amy-agent-task-service__column-title">
								<?php echo esc_html( $status_label ); ?>
								<span class="amy-agent-task-service__column-count" data-count-for="<?php echo esc_attr( $status_key ); ?>">0</span>
							</h2>
							<button
								type="button"
								class="amy-agent-task-service__column-add"
								disabled
								aria-disabled="true"
								title="<?php echo esc_attr__( 'Coming soon — task creation will be available once the data layer is built.', 'amy-agent' ); ?>"
							>
								<span class="dashicons dashicons-plus-alt2" aria-hidden="true"></span>
								<span class="screen-reader-text"><?php echo esc_html__( 'Quick add (coming soon)', 'amy-agent' ); ?></span>
							</button>
						</header>
						<div class="amy-agent-task-service__column-cards" data-cards-for="<?php echo esc_attr( $status_key ); ?>"></div>
					</section>
				<?php endforeach; ?>
			</div>

			<div
				class="amy-agent-task-service__list"
				id="amy-agent-task-list"
				role="tabpanel"
				aria-labelledby="amy-agent-view-list"
				hidden
			>
				<table class="amy-agent-task-service__table">
					<thead>
						<tr>
							<th scope="col"><?php echo esc_html__( 'Task', 'amy-agent' ); ?></th>
							<th scope="col"><?php echo esc_html__( 'Assignee', 'amy-agent' ); ?></th>
							<th scope="col"><?php echo esc_html__( 'Priority', 'amy-agent' ); ?></th>
							<th scope="col"><?php echo esc_html__( 'Status', 'amy-agent' ); ?></th>
							<th scope="col"><?php echo esc_html__( 'Due Date', 'amy-agent' ); ?></th>
						</tr>
					</thead>
					<tbody id="amy-agent-task-list-body"></tbody>
				</table>
				<p class="amy-agent-task-service__empty-filter" id="amy-agent-task-empty" hidden></p>
			</div>

			<div
				class="amy-agent-task-service__modal"
				id="amy-agent-task-modal"
				hidden
				role="dialog"
				aria-modal="true"
				aria-labelledby="amy-agent-task-modal-title"
			>
				<div class="amy-agent-task-service__modal-backdrop" data-amy-modal-close></div>
				<div class="amy-agent-task-service__modal-dialog">
					<header class="amy-agent-task-service__modal-header">
						<h2 id="amy-agent-task-modal-title" class="amy-agent-task-service__modal-title">
							<?php echo esc_html__( 'New Task', 'amy-agent' ); ?>
						</h2>
						<button
							type="button"
							class="amy-agent-task-service__modal-close"
							data-amy-modal-close
							aria-label="<?php echo esc_attr__( 'Close', 'amy-agent' ); ?>"
						>
							<span class="dashicons dashicons-no-alt" aria-hidden="true"></span>
						</button>
					</header>
					<form class="amy-agent-task-service__modal-form" id="amy-agent-task-form" novalidate>
						<label class="amy-agent-task-service__field" for="amy-agent-task-title">
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Title', 'amy-agent' ); ?></span>
							<input type="text" id="amy-agent-task-title" name="title" placeholder="<?php echo esc_attr__( 'What needs to be done?', 'amy-agent' ); ?>" />
						</label>

						<label class="amy-agent-task-service__field" for="amy-agent-task-assignee">
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Assignee', 'amy-agent' ); ?></span>
							<select id="amy-agent-task-assignee" name="assignee">
								<option value=""><?php echo esc_html__( 'Select assignee…', 'amy-agent' ); ?></option>
								<option value="amy"><?php echo esc_html__( 'Amy', 'amy-agent' ); ?></option>
								<option value="sarah"><?php echo esc_html__( 'Sarah Chen', 'amy-agent' ); ?></option>
								<option value="marcus"><?php echo esc_html__( 'Marcus Webb', 'amy-agent' ); ?></option>
								<option value="lena"><?php echo esc_html__( 'Lena Ortiz', 'amy-agent' ); ?></option>
							</select>
						</label>

						<fieldset class="amy-agent-task-service__field amy-agent-task-service__field--priority">
							<legend class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Priority', 'amy-agent' ); ?></legend>
							<label class="amy-agent-task-service__radio">
								<input type="radio" name="priority" value="normal" checked />
								<span><?php echo esc_html__( 'Normal', 'amy-agent' ); ?></span>
							</label>
							<label class="amy-agent-task-service__radio">
								<input type="radio" name="priority" value="urgent" />
								<span><?php echo esc_html__( 'Urgent', 'amy-agent' ); ?></span>
							</label>
						</fieldset>

						<label class="amy-agent-task-service__field" for="amy-agent-task-due">
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Due date', 'amy-agent' ); ?></span>
							<input type="date" id="amy-agent-task-due" name="due" />
						</label>

						<label class="amy-agent-task-service__field" for="amy-agent-task-description">
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Description', 'amy-agent' ); ?></span>
							<textarea id="amy-agent-task-description" name="description" rows="4" placeholder="<?php echo esc_attr__( 'Add context, links, or acceptance criteria…', 'amy-agent' ); ?>"></textarea>
						</label>

						<div class="amy-agent-task-service__modal-actions">
							<button type="button" class="amy-agent-task-service__btn amy-agent-task-service__btn--ghost" data-amy-modal-close>
								<?php echo esc_html__( 'Cancel', 'amy-agent' ); ?>
							</button>
							<button
								type="button"
								class="amy-agent-task-service__btn amy-agent-task-service__btn--accent amy-agent-task-service__btn--disabled"
								id="amy-agent-task-create"
								disabled
								aria-disabled="true"
								title="<?php echo esc_attr__( 'Coming soon — task creation will be available once the data layer is built.', 'amy-agent' ); ?>"
							>
								<?php echo esc_html__( 'Create Task', 'amy-agent' ); ?>
							</button>
						</div>
						<p class="amy-agent-task-service__coming-note">
							<?php echo esc_html__( 'Coming soon — task creation will be available once the data layer is built.', 'amy-agent' ); ?>
						</p>
					</form>
				</div>
			</div>
		</div>
		<?php
	}

	/**
	 * Static placeholder tasks for the visual-only Task Service phase.
	 *
	 * TODO: replace with real task query once the Task Service data layer
	 * (CPT/DB table + CRUD) is built in a future phase.
	 *
	 * @return array<int, array<string, mixed>>
	 */
	private function get_placeholder_tasks() {
		$amy_avatar = $this->settings->get_avatar_url();

		return array(
			array(
				'id'           => 't1',
				'title'        => 'Rewrite homepage hero copy',
				'assignee'     => 'Sarah Chen',
				'assigneeKey'  => 'sarah',
				'assigneeType' => 'human',
				'initials'     => 'SC',
				'color'        => '#3D8BFF',
				'avatarUrl'    => '',
				'priority'     => 'normal',
				'status'       => 'todo',
				'statusLabel'  => 'To Do',
				'due'          => 'Aug 14',
			),
			array(
				'id'           => 't2',
				'title'        => 'Patch login rate-limit gap',
				'assignee'     => 'Marcus Webb',
				'assigneeKey'  => 'marcus',
				'assigneeType' => 'human',
				'initials'     => 'MW',
				'color'        => '#22C55E',
				'avatarUrl'    => '',
				'priority'     => 'urgent',
				'status'       => 'todo',
				'statusLabel'  => 'To Do',
				'due'          => 'Aug 11',
			),
			array(
				'id'           => 't3',
				'title'        => 'Draft Q3 email nurture sequence',
				'assignee'     => 'Amy',
				'assigneeKey'  => 'amy',
				'assigneeType' => 'amy',
				'initials'     => 'A',
				'color'        => '#FF7A18',
				'avatarUrl'    => $amy_avatar,
				'priority'     => 'normal',
				'status'       => 'in_progress',
				'statusLabel'  => 'In Progress',
				'due'          => 'Aug 16',
			),
			array(
				'id'           => 't4',
				'title'        => 'Fix broken OG images on blog posts',
				'assignee'     => 'Lena Ortiz',
				'assigneeKey'  => 'lena',
				'assigneeType' => 'human',
				'initials'     => 'LO',
				'color'        => '#A855F7',
				'avatarUrl'    => '',
				'priority'     => 'urgent',
				'status'       => 'in_progress',
				'statusLabel'  => 'In Progress',
				'due'          => 'Aug 12',
			),
			array(
				'id'           => 't5',
				'title'        => 'Audit unused CSS on service pages',
				'assignee'     => 'Sarah Chen',
				'assigneeKey'  => 'sarah',
				'assigneeType' => 'human',
				'initials'     => 'SC',
				'color'        => '#3D8BFF',
				'avatarUrl'    => '',
				'priority'     => 'normal',
				'status'       => 'in_progress',
				'statusLabel'  => 'In Progress',
				'due'          => 'Aug 18',
			),
			array(
				'id'           => 't6',
				'title'        => 'Migrate contact form spam rules',
				'assignee'     => 'Marcus Webb',
				'assigneeKey'  => 'marcus',
				'assigneeType' => 'human',
				'initials'     => 'MW',
				'color'        => '#22C55E',
				'avatarUrl'    => '',
				'priority'     => 'normal',
				'status'       => 'waiting_extension',
				'statusLabel'  => 'Waiting on Extension',
				'due'          => 'Aug 13',
			),
			array(
				'id'           => 't7',
				'title'        => 'Prepare client kickoff deck',
				'assignee'     => 'Lena Ortiz',
				'assigneeKey'  => 'lena',
				'assigneeType' => 'human',
				'initials'     => 'LO',
				'color'        => '#A855F7',
				'avatarUrl'    => '',
				'priority'     => 'normal',
				'status'       => 'done',
				'statusLabel'  => 'Done',
				'due'          => 'Aug 9',
			),
			array(
				'id'           => 't8',
				'title'        => 'Summarize last week’s support tickets',
				'assignee'     => 'Amy',
				'assigneeKey'  => 'amy',
				'assigneeType' => 'amy',
				'initials'     => 'A',
				'color'        => '#FF7A18',
				'avatarUrl'    => $amy_avatar,
				'priority'     => 'normal',
				'status'       => 'done',
				'statusLabel'  => 'Done',
				'due'          => 'Aug 8',
			),
		);
	}

	/**
	 * My Profile — personal task activity for the logged-in user.
	 */
	public function render_my_profile() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$user        = wp_get_current_user();
		$coming_soon = __( '(coming soon)', 'amy-agent' );
		$avatar_url  = $this->get_user_avatar_url( $user->ID );
		$role_label  = $this->get_primary_role_label( $user );
		$joined      = $this->format_joined_date( $user->user_registered );
		$custom_avatar = trim( (string) get_user_meta( $user->ID, self::USER_AVATAR_META, true ) );

		$top_stats = array(
			// TODO: wire to Task Service once built.
			array(
				'label' => __( 'Open Tasks', 'amy-agent' ),
				'icon'  => 'clipboard',
			),
			// TODO: wire to Task Service once built.
			array(
				'label' => __( 'Completed Tasks', 'amy-agent' ),
				'icon'  => 'yes-alt',
			),
			// TODO: wire to Task Service / activity once built.
			array(
				'label' => __( 'This Week', 'amy-agent' ),
				'icon'  => 'calendar-alt',
			),
		);
		?>
		<div class="wrap amy-agent-my-profile">
			<header class="amy-agent-my-profile__header">
				<div class="amy-agent-my-profile__header-main">
					<h1 class="amy-agent-my-profile__title"><?php echo esc_html__( 'My Profile', 'amy-agent' ); ?></h1>
					<p class="amy-agent-my-profile__intro">
						<?php echo esc_html__( 'Your personal task activity.', 'amy-agent' ); ?>
					</p>
					<span class="amy-agent-my-profile__underline" aria-hidden="true"></span>
				</div>
				<div class="amy-agent-my-profile__header-actions">
					<a
						class="amy-agent-my-profile__btn amy-agent-my-profile__btn--accent"
						href="<?php echo esc_url( admin_url( 'admin.php?page=' . self::TASK_SERVICE_PAGE_SLUG ) ); ?>"
					>
						<?php echo esc_html__( '+ New Task', 'amy-agent' ); ?>
					</a>
				</div>
			</header>

			<section class="amy-agent-my-profile__identity" id="amy-agent-my-profile-identity" aria-label="<?php echo esc_attr__( 'Employee identity', 'amy-agent' ); ?>">
				<img
					id="amy-agent-my-profile-avatar"
					class="amy-agent-my-profile__identity-avatar"
					src="<?php echo esc_url( $avatar_url ); ?>"
					alt="<?php echo esc_attr( $user->display_name ); ?>"
					width="72"
					height="72"
					decoding="async"
				/>
				<div class="amy-agent-my-profile__identity-body">
					<div class="amy-agent-my-profile__identity-name-row">
						<h2 id="amy-agent-my-profile-name" class="amy-agent-my-profile__identity-name">
							<?php echo esc_html( $user->display_name ); ?>
						</h2>
						<?php // TODO: replace with Admin Roles & Social role once that system exists. ?>
						<span id="amy-agent-my-profile-role" class="amy-agent-my-profile__role-pill">
							<?php echo esc_html( $role_label ); ?>
						</span>
					</div>
					<p class="amy-agent-my-profile__identity-meta">
						<span id="amy-agent-my-profile-email"><?php echo esc_html( $user->user_email ); ?></span>
						<span class="amy-agent-my-profile__identity-sep" aria-hidden="true">·</span>
						<span id="amy-agent-my-profile-joined"><?php echo esc_html( $joined ); ?></span>
					</p>
				</div>
				<button
					type="button"
					class="amy-agent-my-profile__btn amy-agent-my-profile__btn--outline"
					id="amy-agent-edit-profile-open"
				>
					<?php echo esc_html__( 'Edit Profile', 'amy-agent' ); ?>
				</button>
			</section>

			<div class="amy-agent-my-profile__stats">
				<?php foreach ( $top_stats as $stat ) : ?>
					<div class="amy-agent-my-profile__stat">
						<span class="amy-agent-my-profile__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-<?php echo esc_attr( $stat['icon'] ); ?>"></span>
						</span>
						<div class="amy-agent-my-profile__stat-body">
							<p class="amy-agent-my-profile__stat-label"><?php echo esc_html( $stat['label'] ); ?></p>
							<p class="amy-agent-my-profile__stat-value">
								—
								<span class="amy-agent-my-profile__coming-soon"><?php echo esc_html( $coming_soon ); ?></span>
							</p>
						</div>
					</div>
				<?php endforeach; ?>
			</div>

			<div class="amy-agent-my-profile__layout">
				<section class="amy-agent-my-profile__panel amy-agent-my-profile__panel--open">
					<h2 class="amy-agent-my-profile__panel-title">
						<span class="amy-agent-my-profile__panel-title-icon" aria-hidden="true">
							<span class="dashicons dashicons-clipboard"></span>
						</span>
						<?php echo esc_html__( 'Open Tasks', 'amy-agent' ); ?>
					</h2>
					<?php
					// TODO: replace empty state with real task query once Task Service exists.
					?>
					<div class="amy-agent-my-profile__empty amy-agent-my-profile__empty--hero">
						<div class="amy-agent-my-profile__empty-orbit" aria-hidden="true">
							<span class="amy-agent-my-profile__empty-orbit-ring"></span>
							<span class="amy-agent-my-profile__empty-icon amy-agent-my-profile__empty-icon--lg">
								<span class="dashicons dashicons-clipboard"></span>
							</span>
						</div>
						<p class="amy-agent-my-profile__empty-text">
							<?php echo esc_html__( 'No tasks yet — open Task Service to create and track work.', 'amy-agent' ); ?>
						</p>
						<a
							class="amy-agent-my-profile__btn amy-agent-my-profile__btn--accent"
							href="<?php echo esc_url( admin_url( 'admin.php?page=' . self::TASK_SERVICE_PAGE_SLUG ) ); ?>"
						>
							<?php echo esc_html__( 'Go to Task Service', 'amy-agent' ); ?>
						</a>
					</div>
				</section>

				<div class="amy-agent-my-profile__side">
					<section class="amy-agent-my-profile__panel amy-agent-my-profile__panel--completed">
						<h2 class="amy-agent-my-profile__panel-title">
							<span class="amy-agent-my-profile__panel-title-icon" aria-hidden="true">
								<span class="dashicons dashicons-star-filled"></span>
							</span>
							<?php echo esc_html__( 'Completed Tasks', 'amy-agent' ); ?>
						</h2>
						<?php
						// TODO: replace empty state with real task query once Task Service exists.
						?>
						<div class="amy-agent-my-profile__empty">
							<span class="amy-agent-my-profile__empty-icon amy-agent-my-profile__empty-icon--star" aria-hidden="true">
								<span class="dashicons dashicons-star-filled"></span>
							</span>
							<p class="amy-agent-my-profile__empty-text">
								<?php echo esc_html__( 'Nothing completed yet.', 'amy-agent' ); ?>
							</p>
						</div>
					</section>

					<section class="amy-agent-my-profile__panel amy-agent-my-profile__panel--activity">
						<h2 class="amy-agent-my-profile__panel-title">
							<span class="amy-agent-my-profile__panel-title-icon" aria-hidden="true">
								<span class="dashicons dashicons-backup"></span>
							</span>
							<?php echo esc_html__( 'Recent Activity', 'amy-agent' ); ?>
						</h2>
						<?php
						// TODO: replace with real activity feed once available.
						?>
						<ol class="amy-agent-my-profile__timeline">
							<?php for ( $i = 0; $i < 3; $i++ ) : ?>
								<li class="amy-agent-my-profile__timeline-item">
									<span class="amy-agent-my-profile__timeline-dot" aria-hidden="true"></span>
									<div class="amy-agent-my-profile__timeline-body">
										<span class="amy-agent-my-profile__timeline-bar" aria-hidden="true"></span>
										<span class="amy-agent-my-profile__timeline-label">
											<?php echo esc_html__( 'No activity yet.', 'amy-agent' ); ?>
										</span>
									</div>
								</li>
							<?php endfor; ?>
						</ol>
					</section>
				</div>
			</div>

			<div
				class="amy-agent-my-profile__modal"
				id="amy-agent-edit-profile-modal"
				hidden
				role="dialog"
				aria-modal="true"
				aria-labelledby="amy-agent-edit-profile-title"
			>
				<div class="amy-agent-my-profile__modal-backdrop" data-amy-modal-close></div>
				<div class="amy-agent-my-profile__modal-dialog">
					<header class="amy-agent-my-profile__modal-header">
						<h2 id="amy-agent-edit-profile-title" class="amy-agent-my-profile__modal-title">
							<?php echo esc_html__( 'Edit Profile', 'amy-agent' ); ?>
						</h2>
						<button
							type="button"
							class="amy-agent-my-profile__modal-close"
							data-amy-modal-close
							aria-label="<?php echo esc_attr__( 'Close', 'amy-agent' ); ?>"
						>
							<span class="dashicons dashicons-no-alt" aria-hidden="true"></span>
						</button>
					</header>
					<form id="amy-agent-edit-profile-form" class="amy-agent-my-profile__modal-form" novalidate>
						<p class="amy-agent-my-profile__field-error" id="amy-agent-edit-profile-error" hidden></p>

						<label class="amy-agent-my-profile__field" for="amy-agent-edit-display-name">
							<span class="amy-agent-my-profile__field-label"><?php echo esc_html__( 'Display name', 'amy-agent' ); ?></span>
							<input
								type="text"
								id="amy-agent-edit-display-name"
								name="display_name"
								value="<?php echo esc_attr( $user->display_name ); ?>"
								required
								autocomplete="name"
							/>
						</label>

						<label class="amy-agent-my-profile__field" for="amy-agent-edit-email">
							<span class="amy-agent-my-profile__field-label"><?php echo esc_html__( 'Email', 'amy-agent' ); ?></span>
							<input
								type="email"
								id="amy-agent-edit-email"
								name="email"
								value="<?php echo esc_attr( $user->user_email ); ?>"
								required
								autocomplete="email"
							/>
						</label>

						<div class="amy-agent-my-profile__field amy-agent-my-profile__field--avatar">
							<span class="amy-agent-my-profile__field-label"><?php echo esc_html__( 'Avatar', 'amy-agent' ); ?></span>
							<div class="amy-agent-my-profile__avatar-editor">
								<img
									id="amy-agent-edit-avatar-preview"
									class="amy-agent-my-profile__avatar-preview"
									src="<?php echo esc_url( $avatar_url ); ?>"
									alt=""
									width="64"
									height="64"
									decoding="async"
								/>
								<input
									type="hidden"
									id="amy-agent-edit-avatar-url"
									name="avatar_url"
									value="<?php echo esc_attr( $custom_avatar ); ?>"
								/>
								<div class="amy-agent-my-profile__avatar-actions">
									<button type="button" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--outline" id="amy-agent-edit-avatar-select">
										<?php echo esc_html__( 'Select image', 'amy-agent' ); ?>
									</button>
									<button type="button" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--ghost" id="amy-agent-edit-avatar-reset">
										<?php echo esc_html__( 'Use Gravatar', 'amy-agent' ); ?>
									</button>
								</div>
							</div>
						</div>

						<div class="amy-agent-my-profile__modal-actions">
							<button type="button" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--ghost" data-amy-modal-close>
								<?php echo esc_html__( 'Cancel', 'amy-agent' ); ?>
							</button>
							<button type="submit" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--accent" id="amy-agent-edit-profile-save">
								<?php echo esc_html__( 'Save changes', 'amy-agent' ); ?>
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
		<?php
	}

	/**
	 * AJAX: save the current user's My Profile fields.
	 */
	public function ajax_save_my_profile() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to edit this profile.', 'amy-agent' ) ),
				403
			);
		}

		check_ajax_referer( 'amy_agent_save_my_profile', 'nonce' );

		$user_id = get_current_user_id();
		if ( ! $user_id ) {
			wp_send_json_error(
				array( 'message' => __( 'Not logged in.', 'amy-agent' ) ),
				401
			);
		}

		$display_name = isset( $_POST['display_name'] ) ? sanitize_text_field( wp_unslash( $_POST['display_name'] ) ) : '';
		$email        = isset( $_POST['email'] ) ? sanitize_email( wp_unslash( $_POST['email'] ) ) : '';
		$avatar_url   = isset( $_POST['avatar_url'] ) ? esc_url_raw( wp_unslash( $_POST['avatar_url'] ) ) : '';

		if ( '' === $display_name ) {
			wp_send_json_error(
				array( 'message' => __( 'Display name is required.', 'amy-agent' ) ),
				400
			);
		}

		if ( '' === $email || ! is_email( $email ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Please enter a valid email address.', 'amy-agent' ) ),
				400
			);
		}

		$email_owner = email_exists( $email );
		if ( $email_owner && (int) $email_owner !== (int) $user_id ) {
			wp_send_json_error(
				array( 'message' => __( 'That email address is already in use.', 'amy-agent' ) ),
				400
			);
		}

		if ( '' !== $avatar_url && ! $this->is_allowed_avatar_url( $avatar_url ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Please choose a JPG, PNG, or WebP image.', 'amy-agent' ) ),
				400
			);
		}

		$result = wp_update_user(
			array(
				'ID'           => $user_id,
				'display_name' => $display_name,
				'user_email'   => $email,
			)
		);

		if ( is_wp_error( $result ) ) {
			wp_send_json_error(
				array( 'message' => $result->get_error_message() ),
				400
			);
		}

		if ( '' === $avatar_url ) {
			delete_user_meta( $user_id, self::USER_AVATAR_META );
		} else {
			update_user_meta( $user_id, self::USER_AVATAR_META, $avatar_url );
		}

		$user = get_userdata( $user_id );
		wp_send_json_success(
			array(
				'displayName' => $user->display_name,
				'email'       => $user->user_email,
				'avatarUrl'   => $this->get_user_avatar_url( $user_id ),
				'gravatarUrl' => esc_url_raw( get_avatar_url( $user_id, array( 'size' => 144 ) ) ),
				'joined'      => $this->format_joined_date( $user->user_registered ),
				'roleLabel'   => $this->get_primary_role_label( $user ),
			)
		);
	}

	/**
	 * Avatar URL for a user: custom meta override, else WP Gravatar.
	 *
	 * @param int $user_id User ID.
	 * @return string
	 */
	private function get_user_avatar_url( $user_id ) {
		$custom = trim( (string) get_user_meta( $user_id, self::USER_AVATAR_META, true ) );
		if ( '' !== $custom ) {
			return esc_url_raw( $custom );
		}

		return get_avatar_url( $user_id, array( 'size' => 144 ) );
	}

	/**
	 * Human-readable primary role label for the identity pill.
	 *
	 * @param WP_User $user User object.
	 * @return string
	 */
	private function get_primary_role_label( $user ) {
		// TODO: replace with Admin Roles & Social role once that system exists.
		$roles = (array) $user->roles;
		$role  = ! empty( $roles[0] ) ? $roles[0] : '';

		$map = array(
			'administrator' => __( 'Admin', 'amy-agent' ),
			'editor'        => __( 'Editor', 'amy-agent' ),
			'author'        => __( 'Author', 'amy-agent' ),
			'contributor'   => __( 'Contributor', 'amy-agent' ),
			'subscriber'    => __( 'Subscriber', 'amy-agent' ),
		);

		if ( isset( $map[ $role ] ) ) {
			return $map[ $role ];
		}

		if ( '' === $role ) {
			return __( 'Member', 'amy-agent' );
		}

		return ucwords( str_replace( array( '-', '_' ), ' ', $role ) );
	}

	/**
	 * Format user_registered for identity meta.
	 *
	 * @param string $registered MySQL datetime.
	 * @return string
	 */
	private function format_joined_date( $registered ) {
		$timestamp = strtotime( $registered );
		if ( ! $timestamp ) {
			return '';
		}

		return sprintf(
			/* translators: %s: month day, year */
			__( 'Joined %s', 'amy-agent' ),
			date_i18n( 'F j, Y', $timestamp )
		);
	}

	/**
	 * Allow only http(s) image URLs that look like JPG/PNG/WebP (mirrors Brand picker).
	 *
	 * @param string $url Avatar URL.
	 * @return bool
	 */
	private function is_allowed_avatar_url( $url ) {
		if ( '' === $url || ! wp_http_validate_url( $url ) ) {
			return false;
		}

		$path = wp_parse_url( $url, PHP_URL_PATH );
		if ( ! is_string( $path ) || '' === $path ) {
			return false;
		}

		$ext = strtolower( pathinfo( $path, PATHINFO_EXTENSION ) );
		return in_array( $ext, array( 'jpg', 'jpeg', 'png', 'webp' ), true );
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
