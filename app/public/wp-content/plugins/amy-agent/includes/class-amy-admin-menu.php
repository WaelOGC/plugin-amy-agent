<?php
/**
 * Top-level Amy admin menu and dashboard pages.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers Amy → Overview / My Profile / Task Service / Analytics / Email Marketing / SEO Tasks / Settings / Brand & Avatar in wp-admin.
 */
class Amy_Admin_Menu {

	const PARENT_SLUG             = 'amy-overview';
	const MY_PROFILE_PAGE_SLUG    = 'amy-my-profile';
	const TASK_SERVICE_PAGE_SLUG  = 'amy-task-service';
	const ANALYTICS_PAGE_SLUG       = 'amy-analytics';
	const EMAIL_MARKETING_PAGE_SLUG = 'amy-email-marketing';
	const SEO_TASKS_PAGE_SLUG       = 'amy-seo-tasks';
	const BRAND_PAGE_SLUG           = 'amy-brand-avatar';
	const USER_AVATAR_META          = 'amy_agent_user_avatar_url';
	/** Per-owner Task Service backup (P3 escalate fallback). */
	const USER_TASK_BACKUP_META     = 'amy_task_backup_wp_user_id';

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
	private $hook_analytics;

	/**
	 * @var string|false|null
	 */
	private $hook_email_marketing;

	/**
	 * @var string|false|null
	 */
	private $hook_seo_tasks;

	/**
	 * @var string|false|null
	 */
	private $hook_chat;

	/**
	 * @var string|false|null
	 */
	private $hook_settings;

	/**
	 * @var string|false|null
	 */
	private $hook_brand;

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
		add_action( 'wp_ajax_amy_agent_save_task_backup', array( $this, 'ajax_save_task_backup' ) );
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
		if ( $this->hook_task_service ) {
			add_action( 'load-' . $this->hook_task_service, array( $this, 'add_task_service_help_tabs' ) );
		}

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

		$this->hook_chat = add_submenu_page(
			self::PARENT_SLUG,
			__( 'Chat', 'amy-agent' ),
			__( 'Chat', 'amy-agent' ),
			'manage_options',
			'amy-chat',
			array( $this, 'render_chat_page' )
		);

		$this->hook_analytics = add_submenu_page(
			self::PARENT_SLUG,
			__( 'Analytics', 'amy-agent' ),
			__( 'Analytics', 'amy-agent' ),
			'manage_options',
			self::ANALYTICS_PAGE_SLUG,
			array( $this, 'render_analytics_page' )
		);

		$this->hook_seo_tasks = add_submenu_page(
			self::PARENT_SLUG,
			__( 'SEO Tasks', 'amy-agent' ),
			__( 'SEO Tasks', 'amy-agent' ),
			'manage_options',
			self::SEO_TASKS_PAGE_SLUG,
			array( $this, 'render_seo_tasks_page' )
		);

		$this->hook_email_marketing = add_submenu_page(
			self::PARENT_SLUG,
			__( 'Email Marketing', 'amy-agent' ),
			__( 'Email Marketing', 'amy-agent' ),
			'manage_options',
			self::EMAIL_MARKETING_PAGE_SLUG,
			array( $this, 'render_email_marketing_page' )
		);
		if ( $this->hook_email_marketing ) {
			add_action( 'load-' . $this->hook_email_marketing, array( $this, 'add_email_marketing_help_tabs' ) );
		}
	}

	/**
	 * WP Screen Help for Amy → Task Service (mirrors empty-state / connection help).
	 */
	public function add_task_service_help_tabs() {
		$screen = get_current_screen();
		if ( ! $screen ) {
			return;
		}

		$connection_url = esc_url( $this->settings->settings_deep_link( 'connection', 'connection' ) );
		$telegram_url   = esc_url( $this->settings->settings_deep_link( 'telegram', 'telegram' ) );
		$profile_url    = esc_url( admin_url( 'admin.php?page=' . self::MY_PROFILE_PAGE_SLUG ) );

		$screen->add_help_tab(
			array(
				'id'      => 'amy-task-service-overview',
				'title'   => __( 'Task Service', 'amy-agent' ),
				'content' => '<p>' . esc_html__( 'Board and list of tasks backed by your Amy Python service. Create work, assign humans or Amy, and track status.', 'amy-agent' ) . '</p>',
			)
		);

		$screen->add_help_tab(
			array(
				'id'      => 'amy-task-service-connection',
				'title'   => __( 'Connection', 'amy-agent' ),
				'content' => Amy_Settings::build_help_tab_steps_html(
					__( 'If the board is empty or fails to load, check the Amy Python service host first.', 'amy-agent' ),
					array(
						__( 'Amy → Settings → Connection: set Python service URL and shared secret, then Check connection.', 'amy-agent' ),
						__( 'Confirm Enable Amy is on under Settings → General.', 'amy-agent' ),
					),
					'<p><a href="' . $connection_url . '">' . esc_html__( 'Open Settings → Connection', 'amy-agent' ) . '</a></p>'
				),
			)
		);

		$screen->add_help_tab(
			array(
				'id'      => 'amy-task-service-telegram',
				'title'   => __( 'Telegram alerts', 'amy-agent' ),
				'content' => Amy_Settings::build_help_tab_steps_html(
					__( 'Task alerts reuse the Admin Bot from Settings → Telegram (no second bot stack).', 'amy-agent' ),
					array_merge(
						Amy_Settings::get_telegram_connect_next_steps(),
						array(
							__( 'Assignees link their chat id under Amy → My Profile → Telegram task alerts.', 'amy-agent' ),
						)
					),
					'<p><a href="' . $telegram_url . '">' . esc_html__( 'Open Settings → Telegram', 'amy-agent' ) . '</a> · <a href="' . $profile_url . '">' . esc_html__( 'Open My Profile → Telegram', 'amy-agent' ) . '</a></p>'
				),
			)
		);

		$screen->set_help_sidebar(
			'<p><strong>' . esc_html__( 'Quick links', 'amy-agent' ) . '</strong></p>' .
			'<p><a href="' . $connection_url . '">' . esc_html__( 'Settings → Connection', 'amy-agent' ) . '</a></p>' .
			'<p><a href="' . $telegram_url . '">' . esc_html__( 'Settings → Telegram', 'amy-agent' ) . '</a></p>' .
			'<p><a href="' . $profile_url . '">' . esc_html__( 'My Profile → Telegram', 'amy-agent' ) . '</a></p>'
		);
	}

	/**
	 * WP Screen Help for Amy → Email Marketing (mirrors From playbook).
	 */
	public function add_email_marketing_help_tabs() {
		$screen = get_current_screen();
		if ( ! $screen ) {
			return;
		}

		$from_url = esc_url( $this->settings->settings_deep_link( 'general', 'general-from' ) );

		$screen->add_help_tab(
			array(
				'id'      => 'amy-email-overview',
				'title'   => __( 'Email Marketing', 'amy-agent' ),
				'content' => '<p>' . esc_html__( 'Audience from Amy Analytics visitor emails. Approve the draft, then click Send — nothing auto-sends. Treat as lead-only until consent is confirmed. Never personal Gmail or AgentMail.', 'amy-agent' ) . '</p>',
			)
		);

		$screen->add_help_tab(
			array(
				'id'      => 'amy-email-from',
				'title'   => Amy_Settings::get_fluentsmtp_playbook_title(),
				'content' => Amy_Settings::build_help_tab_steps_html(
					Amy_Settings::get_fluentsmtp_playbook_intro(),
					Amy_Settings::get_fluentsmtp_playbook_steps( Amy_Settings::DEFAULT_MARKETING_FROM_EMAIL ),
					'<p><a href="' . $from_url . '">' . esc_html__( 'Change Marketing From in Settings', 'amy-agent' ) . '</a></p>'
				),
			)
		);

		$screen->set_help_sidebar(
			'<p><strong>' . esc_html__( 'Where', 'amy-agent' ) . '</strong></p>' .
			'<p><a href="' . $from_url . '">' . esc_html__( 'Settings → General → Marketing From', 'amy-agent' ) . '</a></p>' .
			'<p>' . (
				Amy_Settings::is_fluentsmtp_active()
					? '<a href="' . esc_url( Amy_Settings::get_fluentsmtp_connections_url() ) . '">' . esc_html__( 'FluentSMTP → Connections', 'amy-agent' ) . '</a>'
					: '<a href="' . esc_url( Amy_Settings::get_fluentsmtp_install_url() ) . '">' . esc_html__( 'Install FluentSMTP', 'amy-agent' ) . '</a>'
			) . '</p>'
		);
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

			$this->enqueue_notifications_assets();
			$this->sync_dashboard_users_to_service();

			wp_enqueue_script(
				'amy-agent-admin-my-profile',
				AMY_AGENT_URL . 'admin/js/admin-my-profile.js',
				array( 'jquery', 'amy-agent-admin-notifications' ),
				AMY_AGENT_VERSION,
				true
			);

			$user            = wp_get_current_user();
			$tg_chat_id      = (int) get_user_meta( $user->ID, Amy_Task_Notify::USER_META_CHAT_ID, true );
			$tg_bot_username = (string) get_option( Amy_Telegram::OPTION_BOT_USERNAME, '' );
			wp_localize_script(
				'amy-agent-admin-my-profile',
				'amyAgentMyProfile',
				array(
					'ajaxUrl'     => admin_url( 'admin-ajax.php' ),
					'nonce'       => wp_create_nonce( 'amy_agent_save_my_profile' ),
					'telegramNonce' => wp_create_nonce( Amy_Telegram::NONCE_ACTION ),
					'gravatarUrl' => esc_url_raw( get_avatar_url( $user->ID, array( 'size' => 144 ) ) ),
					'telegram'    => array(
						'linked'      => $tg_chat_id > 0,
						'chatId'      => $tg_chat_id > 0 ? $tg_chat_id : null,
						'botUsername' => $tg_bot_username,
						'settingsUrl' => admin_url( 'admin.php?page=' . Amy_Settings::PAGE_SLUG . '&tab=telegram' ),
					),
					'i18n'        => array(
						'mediaTitle'   => __( 'Select profile photo', 'amy-agent' ),
						'mediaButton'  => __( 'Use this image', 'amy-agent' ),
						'invalidType'  => __( 'Please choose a JPG, PNG, or WebP image.', 'amy-agent' ),
						'invalidEmail' => __( 'Please enter a valid email address.', 'amy-agent' ),
						'saving'       => __( 'Saving…', 'amy-agent' ),
						'save'         => __( 'Save changes', 'amy-agent' ),
						'error'        => __( 'Could not save profile. Please try again.', 'amy-agent' ),
						'tgLinking'    => __( 'Generating link…', 'amy-agent' ),
						'tgLink'       => __( 'Connect Telegram', 'amy-agent' ),
						'tgUnlink'     => __( 'Unlink Telegram', 'amy-agent' ),
						'tgUnlinking'  => __( 'Unlinking…', 'amy-agent' ),
						'tgLinked'     => __( 'Telegram linked for task alerts.', 'amy-agent' ),
						'tgOpenBot'    => __( 'Open bot & tap Start', 'amy-agent' ),
						'backupSaving' => __( 'Saving backup…', 'amy-agent' ),
						'backupSave'   => __( 'Save backup', 'amy-agent' ),
						'backupSaved'  => __( 'Backup saved.', 'amy-agent' ),
						'backupError'  => __( 'Could not save backup.', 'amy-agent' ),
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

			$this->enqueue_notifications_assets();
			$this->sync_dashboard_users_to_service();

			wp_enqueue_script(
				'amy-agent-admin-task-service',
				AMY_AGENT_URL . 'admin/js/admin-task-service.js',
				array( 'jquery', 'amy-agent-admin-notifications' ),
				AMY_AGENT_VERSION,
				true
			);

			wp_localize_script(
				'amy-agent-admin-task-service',
				'amyAgentTaskService',
				array(
					'ajaxUrl'       => admin_url( 'admin-ajax.php' ),
					'nonce'         => wp_create_nonce( Amy_Tasks_Ajax::NONCE_ACTION ),
					'currentUserId' => get_current_user_id(),
					'assignees'     => $this->get_task_assignees_for_js(),
					'amyAvatarUrl'  => $this->settings->get_avatar_url(),
					'openNewTask'   => isset( $_GET['amy_new_task'] ) && '1' === (string) wp_unslash( $_GET['amy_new_task'] ), // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- read-only UI flag
					'settingsUrls'  => array(
						'connection' => $this->settings->settings_deep_link( 'connection', 'connection' ),
						'telegram'   => $this->settings->settings_deep_link( 'telegram', 'telegram' ),
						'myProfile'  => admin_url( 'admin.php?page=' . self::MY_PROFILE_PAGE_SLUG ),
					),
					'i18n'          => array(
						'noResults'        => __( 'No tasks match your filters.', 'amy-agent' ),
						'emptyBoard'       => __( 'No tasks yet. Create one with + New Task. If the board will not load, check Amy → Settings → Connection. For Telegram alerts: Settings → Telegram, then My Profile → Telegram.', 'amy-agent' ),
						'loadError'        => __( 'Could not load tasks. Check Amy → Settings → Connection (service URL + shared secret). Telegram alerts: Settings → Telegram + My Profile → Telegram.', 'amy-agent' ),
						'helpConnection'   => __( 'Settings → Connection', 'amy-agent' ),
						'helpTelegram'     => __( 'Settings → Telegram', 'amy-agent' ),
						'helpMyProfile'    => __( 'My Profile → Telegram', 'amy-agent' ),
						'createSuccess'    => __( 'Task created.', 'amy-agent' ),
						'updateSuccess'    => __( 'Task updated.', 'amy-agent' ),
						'deleteSuccess'    => __( 'Task deleted.', 'amy-agent' ),
						'deleteConfirm'    => __( 'Delete this task? This cannot be undone.', 'amy-agent' ),
						'saving'           => __( 'Saving…', 'amy-agent' ),
						'create'           => __( 'Create Task', 'amy-agent' ),
						'save'             => __( 'Save changes', 'amy-agent' ),
						'newTask'          => __( 'New Task', 'amy-agent' ),
						'editTask'         => __( 'Edit Task', 'amy-agent' ),
						'error'            => __( 'Something went wrong. Please try again.', 'amy-agent' ),
						'titleRequired'    => __( 'Title is required.', 'amy-agent' ),
						'assigneeRequired' => __( 'Please select who should do this.', 'amy-agent' ),
						'statusTodo'           => __( 'To Do', 'amy-agent' ),
						'statusRunning'        => __( 'Amy Running', 'amy-agent' ),
						'statusInProgress'     => __( 'In Progress', 'amy-agent' ),
						'statusWaiting'        => __( 'Waiting on Extension', 'amy-agent' ),
						'statusFailed'         => __( 'Failed', 'amy-agent' ),
						'statusDone'           => __( 'Done', 'amy-agent' ),
						'amy'                  => __( 'Amy', 'amy-agent' ),
						'noDue'                => __( 'No due date', 'amy-agent' ),
						'extensionHours'       => __( 'Hours to request', 'amy-agent' ),
						'extensionSubmit'      => __( 'Request Extension', 'amy-agent' ),
						'extensionAuto'        => __( 'Extension granted automatically. Due date updated.', 'amy-agent' ),
						'extensionPending'     => __( 'Extension request sent — awaiting creator approval.', 'amy-agent' ),
						'extensionInvalid'     => __( 'Enter a positive number of hours.', 'amy-agent' ),
						'modeAmy'              => __( 'Amy', 'amy-agent' ),
						'modeHuman'            => __( 'Human', 'amy-agent' ),
						'amyCapableBadge'      => __( 'Amy-capable', 'amy-agent' ),
						'expiryActionSuccess'  => __( 'Expiry action saved.', 'amy-agent' ),
						'amyTakeDisabled'      => __( 'Only Amy-capable (digital / in-system) tasks can be handed to Amy.', 'amy-agent' ),
						'amyExecutionLive'     => __( 'Amy execution is live for digital / in-system work.', 'amy-agent' ),
					),
				)
			);
			return;
		}

		if ( $this->hook_chat === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-chat-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-chat',
				AMY_AGENT_URL . 'admin/css/admin-chat.css',
				array( 'amy-agent-admin-chat-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);

			wp_enqueue_script(
				'amy-agent-admin-chat',
				AMY_AGENT_URL . 'admin/js/admin-chat.js',
				array( 'jquery' ),
				AMY_AGENT_VERSION,
				true
			);

			$user = wp_get_current_user();
			wp_localize_script(
				'amy-agent-admin-chat',
				'amyAgentAdminChat',
				array(
					'restUrl'         => esc_url_raw( rest_url( Amy_Rest::NAMESPACE ) ),
					'restNonce'       => wp_create_nonce( 'wp_rest' ),
					'currentUserId'   => get_current_user_id(),
					'isFullAdmin'     => current_user_can( 'manage_options' ),
					'currentUserName' => $user->display_name,
					'currentUserAvatarUrl' => get_avatar_url( $user->ID, array( 'size' => 64 ) ),
					'amyAvatarUrl'    => $this->settings->get_avatar_url(),
					'uploadAccept'    => '.jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,image/*,application/pdf',
					'i18n'            => array(
						'newChat'        => __( 'New chat', 'amy-agent' ),
						'untitled'       => __( '(untitled)', 'amy-agent' ),
						'deleteConfirm'  => __( 'Delete this conversation? This cannot be undone.', 'amy-agent' ),
						'renamePrompt'   => __( 'Rename conversation', 'amy-agent' ),
						'send'           => __( 'Send', 'amy-agent' ),
						'sending'        => __( 'Sending…', 'amy-agent' ),
						'thinking'       => __( 'Amy is thinking…', 'amy-agent' ),
						'error'          => __( 'Something went wrong. Please try again.', 'amy-agent' ),
						'emptyState'     => __( 'Start a new chat or pick one from the list.', 'amy-agent' ),
						'emptyThread'    => __( 'No messages yet. Say hello to Amy.', 'amy-agent' ),
						'loadError'      => __( 'Could not load conversations. Check the Amy Agent service connection.', 'amy-agent' ),
						'exported'       => __( 'Conversation downloaded.', 'amy-agent' ),
						'export'         => __( 'Export', 'amy-agent' ),
						'rename'         => __( 'Rename', 'amy-agent' ),
						'delete'         => __( 'Delete', 'amy-agent' ),
						'attach'         => __( 'Attach a file', 'amy-agent' ),
						'uploadError'    => __( 'Could not upload that file.', 'amy-agent' ),
						'composerPlaceholder' => __( 'Message Amy…', 'amy-agent' ),
						'justNow'        => __( 'just now', 'amy-agent' ),
						'minutesAgo'     => __( 'm ago', 'amy-agent' ),
						'hoursAgo'       => __( 'h ago', 'amy-agent' ),
						'daysAgo'        => __( 'd ago', 'amy-agent' ),
						'you'            => __( 'You', 'amy-agent' ),
						'amy'            => __( 'Amy', 'amy-agent' ),
						'removeAttach'   => __( 'Remove attachment', 'amy-agent' ),
					),
				)
			);
			return;
		}

		if ( $this->hook_analytics === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-analytics-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-analytics',
				AMY_AGENT_URL . 'admin/css/admin-analytics.css',
				array( 'amy-agent-admin-analytics-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);

			wp_enqueue_script(
				'amy-agent-admin-analytics',
				AMY_AGENT_URL . 'admin/js/admin-analytics.js',
				array( 'jquery' ),
				AMY_AGENT_VERSION,
				true
			);

			wp_localize_script(
				'amy-agent-admin-analytics',
				'amyAgentAnalytics',
				array(
					'ajaxUrl' => admin_url( 'admin-ajax.php' ),
					'nonce'   => wp_create_nonce( Amy_Analytics_Ajax::NONCE_ACTION ),
					'i18n'    => array(
						'loadError'  => __( 'Could not load leads. Check the Amy Agent service connection.', 'amy-agent' ),
						'empty'      => __( 'No visitors yet.', 'amy-agent' ),
						'justNow'    => __( 'just now', 'amy-agent' ),
						'minutesAgo' => __( 'm ago', 'amy-agent' ),
						'hoursAgo'   => __( 'h ago', 'amy-agent' ),
						'daysAgo'    => __( 'd ago', 'amy-agent' ),
						'statusHot'  => __( 'Hot', 'amy-agent' ),
						'statusWarm' => __( 'Warm', 'amy-agent' ),
						'statusCold' => __( 'Cold', 'amy-agent' ),
					),
				)
			);
			return;
		}

		if ( $this->hook_email_marketing === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-email-marketing-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-email-marketing',
				AMY_AGENT_URL . 'admin/css/admin-email-marketing.css',
				array( 'amy-agent-admin-email-marketing-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);

			wp_enqueue_script(
				'amy-agent-admin-email-marketing',
				AMY_AGENT_URL . 'admin/js/admin-email-marketing.js',
				array( 'jquery' ),
				AMY_AGENT_VERSION,
				true
			);

			$from_email = $this->settings->get_marketing_from_email();
			$from_name  = $this->settings->get_marketing_from_name();

			wp_localize_script(
				'amy-agent-admin-email-marketing',
				'amyAgentEmailMarketing',
				array(
					'ajaxUrl'       => admin_url( 'admin-ajax.php' ),
					'nonce'         => wp_create_nonce( Amy_Analytics_Ajax::NONCE_ACTION ),
					'sendNonce'     => wp_create_nonce( Amy_Email_Marketing_Ajax::NONCE_ACTION ),
					'analyticsUrl'  => admin_url( 'admin.php?page=' . self::ANALYTICS_PAGE_SLUG ),
					'settingsUrl'   => admin_url( 'admin.php?page=' . Amy_Settings::PAGE_SLUG ),
					'fromEmail'     => $from_email,
					'fromName'      => $from_name,
					'i18n'          => array(
						'loadError'         => __( 'Could not load audience. Check the Amy Agent service connection.', 'amy-agent' ),
						'empty'             => __( 'No visitor emails yet. Captures appear after Submit Idea or contact form completion.', 'amy-agent' ),
						'emptyFiltered'     => __( 'No email leads match this filter or search.', 'amy-agent' ),
						'justNow'           => __( 'just now', 'amy-agent' ),
						'minutesAgo'        => __( 'm ago', 'amy-agent' ),
						'hoursAgo'          => __( 'h ago', 'amy-agent' ),
						'daysAgo'           => __( 'd ago', 'amy-agent' ),
						'statusHot'         => __( 'Hot', 'amy-agent' ),
						'statusWarm'        => __( 'Warm', 'amy-agent' ),
						'statusCold'        => __( 'Cold', 'amy-agent' ),
						'selectRecipient'   => __( 'Select at least one recipient from the audience list.', 'amy-agent' ),
						'needSubject'       => __( 'Add a subject before approving.', 'amy-agent' ),
						'needBody'          => __( 'Add a message body before approving.', 'amy-agent' ),
						'needApprove'       => __( 'Approve the draft first. Send stays disabled until you approve.', 'amy-agent' ),
						'confirmApprove'    => __( 'Approve this draft for the selected audience? Nothing is sent yet — you must click Send afterward. Personal Gmail and AgentMail are never used.', 'amy-agent' ),
						'approvedNotice'    => __( 'Draft approved. Click Send to deliver via wp_mail / FluentSMTP From the address shown above. Nothing was sent yet.', 'amy-agent' ),
						'confirmSend'       => __( 'Send this approved draft to %1$d recipient(s) From %2$s via FluentSMTP (wp_mail)? This cannot be undone.', 'amy-agent' ),
						'sending'           => __( 'Sending…', 'amy-agent' ),
						'sendError'         => sprintf(
							/* translators: %s: Marketing From email */
							__( 'Send failed. Check FluentSMTP logs and that %s is authorized on the connection.', 'amy-agent' ),
							$from_email
						),
						'cleared'           => __( 'Draft cleared.', 'amy-agent' ),
						'leadOnly'          => __( 'Lead capture', 'amy-agent' ),
						'audienceCount'     => __( '%d shown', 'amy-agent' ),
						'coverageValue'     => __( '%1$d of %2$d visitors (%3$s%%)', 'amy-agent' ),
						'coverageEmpty'     => __( 'No Analytics visitors yet.', 'amy-agent' ),
						'signalRow'         => __( '%1$s · %2$s · %3$s', 'amy-agent' ),
						'unknownSignal'     => __( 'No signal', 'amy-agent' ),
						'selectedCount'     => __( '%d selected', 'amy-agent' ),
						'selectedNone'      => __( 'No emails selected', 'amy-agent' ),
						'toMeta'            => __( '%d recipient(s) selected — approve, then click Send. From %s.', 'amy-agent' ),
						'seen24h'           => __( 'Last 24h', 'amy-agent' ),
						'seen7d'            => __( '1–7 days', 'amy-agent' ),
						'seen30d'           => __( '8–30 days', 'amy-agent' ),
						'seenOlder'         => __( 'Older', 'amy-agent' ),
						'chartEmpty'        => __( 'No data yet', 'amy-agent' ),
						'exportEmpty'       => __( 'Select at least one email to export.', 'amy-agent' ),
						'exportDone'        => __( 'Selected emails exported as CSV.', 'amy-agent' ),
						'selectionCleared'  => __( 'Selection cleared.', 'amy-agent' ),
						'draftDirty'        => __( 'Draft changed after approval — approve again before sending.', 'amy-agent' ),
						'historyTitle'      => __( 'Send & reply history', 'amy-agent' ),
						'historyEmpty'      => __( 'No sends yet. After you Send via FluentSMTP, threads appear here.', 'amy-agent' ),
						'historyError'      => __( 'Could not load history. Check the Amy Agent service connection.', 'amy-agent' ),
						'historyInboundNote'=> __( 'FluentSMTP is outbound-only. Automatic hello@ inbound is not wired (no AgentMail). Log replies with Add reply note.', 'amy-agent' ),
						'openThread'        => __( 'Open', 'amy-agent' ),
						'addNote'           => __( 'Add note', 'amy-agent' ),
						'addReplyNote'      => __( 'Add reply note', 'amy-agent' ),
						'notePlaceholder'   => __( 'Paste or summarize their reply, or leave an internal note…', 'amy-agent' ),
						'noteSaved'         => __( 'Note saved to conversation history.', 'amy-agent' ),
						'noteError'         => __( 'Could not save note.', 'amy-agent' ),
						'optOut'            => __( 'Opt out', 'amy-agent' ),
						'optOutConfirm'     => __( 'Mark this address as opted out? Future marketing sends will be blocked.', 'amy-agent' ),
						'optOutDone'        => __( 'Recipient opted out.', 'amy-agent' ),
						'optOutError'       => __( 'Could not record opt-out.', 'amy-agent' ),
						'dirOutbound'       => __( 'Sent', 'amy-agent' ),
						'dirInbound'        => __( 'Reply', 'amy-agent' ),
						'dirNote'           => __( 'Note', 'amy-agent' ),
						'dirProposed'       => __( 'Amy proposed', 'amy-agent' ),
						'statusFailed'      => __( 'Failed', 'amy-agent' ),
						'statusSuppressed'  => __( 'Opted out', 'amy-agent' ),
						'refreshHistory'    => __( 'Refresh', 'amy-agent' ),
						'backToList'        => __( 'Back to list', 'amy-agent' ),
						'saveNote'          => __( 'Save', 'amy-agent' ),
					),
				)
			);
			return;
		}

		if ( $this->hook_seo_tasks === $hook_suffix ) {
			wp_enqueue_style(
				'amy-agent-admin-seo-tasks-fonts',
				'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
				array(),
				null
			);

			wp_enqueue_style(
				'amy-agent-admin-seo-tasks',
				AMY_AGENT_URL . 'admin/css/admin-seo-tasks.css',
				array( 'amy-agent-admin-seo-tasks-fonts', 'dashicons' ),
				AMY_AGENT_VERSION
			);

			wp_enqueue_script(
				'amy-agent-admin-seo-tasks',
				AMY_AGENT_URL . 'admin/js/admin-seo-tasks.js',
				array( 'jquery' ),
				AMY_AGENT_VERSION,
				true
			);

			wp_localize_script(
				'amy-agent-admin-seo-tasks',
				'amyAgentSeoTasks',
				array(
					'ajaxUrl'  => admin_url( 'admin-ajax.php' ),
					'nonce'    => wp_create_nonce( Amy_Seo_Tasks_Ajax::NONCE_ACTION ),
					'restUrl'  => esc_url_raw( rest_url() ),
					'restNonce' => wp_create_nonce( 'wp_rest' ),
					'metaKeys' => Amy_Seo_Meta::writable_field_map(),
					'scoreMetaKeys' => Amy_Seo_Meta::readonly_field_map(),
					'aiProvider' => $this->settings->get_ai_provider(),
					'i18n'     => array(
						'error'              => __( 'Something went wrong. Please try again.', 'amy-agent' ),
						'untitled'           => __( '(untitled)', 'amy-agent' ),
						'post'               => __( 'Post', 'amy-agent' ),
						'page'               => __( 'Page', 'amy-agent' ),
						'category'           => __( 'Category', 'amy-agent' ),
						'tag'                => __( 'Tag', 'amy-agent' ),
						'media'              => __( 'Media', 'amy-agent' ),
						'checking'           => __( 'Checking…', 'amy-agent' ),
						'checkError'         => __( 'Could not run the SEO check. Check the Amy Agent service connection.', 'amy-agent' ),
						'loadPostError'      => __( 'Could not load that post from WordPress.', 'amy-agent' ),
						'loadListError'      => __( 'Could not load that content list from WordPress.', 'amy-agent' ),
						'verdictRed'         => __( 'Needs work', 'amy-agent' ),
						'verdictOrange'      => __( 'Improvements', 'amy-agent' ),
						'verdictGreen'       => __( 'Good', 'amy-agent' ),
						'notChecked'         => __( 'Not checked yet', 'amy-agent' ),
						'itemError'          => __( 'Error', 'amy-agent' ),
						'statusPending'      => __( 'Pending approval', 'amy-agent' ),
						'statusApproved'     => __( 'Approved', 'amy-agent' ),
						'statusRejected'     => __( 'Rejected', 'amy-agent' ),
						'severityMissing'    => __( 'Missing', 'amy-agent' ),
						'severityWeak'       => __( 'Weak', 'amy-agent' ),
						'noFindings'         => __( 'No issues found on the fields Amy checks in this version.', 'amy-agent' ),
						'noAiCopy'           => __( 'Amy is reporting what is missing. Click "Generate with AI" to fill these in, or type your own — review before approving.', 'amy-agent' ),
						'noImageGen'         => __( 'Image generation is only available with the Gemini provider. Switch providers in Settings, or upload an image manually.', 'amy-agent' ),
						'generateFields'     => __( 'Generate with AI', 'amy-agent' ),
						'generatingFields'   => __( 'Generating…', 'amy-agent' ),
						'generateFieldsError' => __( 'Amy could not generate suggestions. You can still fill these in yourself.', 'amy-agent' ),
						'aiSuggestedNote'    => __( 'AI suggested — review before approving.', 'amy-agent' ),
						'generateImage'      => __( 'Generate image', 'amy-agent' ),
						'generatingImage'    => __( 'Generating image…', 'amy-agent' ),
						'generateImageError' => __( 'Amy could not generate an image.', 'amy-agent' ),
						'imagePreviewAlt'    => __( 'AI-generated preview', 'amy-agent' ),
						'promptGenerating'   => __( 'Generating SEO copy for %s…', 'amy-agent' ),
						'promptGenerated'    => __( 'Got %1$s suggestion(s) for %2$s.', 'amy-agent' ),
						'promptGeneratingImage' => __( 'Generating an image for %s…', 'amy-agent' ),
						'promptGeneratedImage' => __( 'Image ready for %s.', 'amy-agent' ),
						'pageCategories'     => __( 'Pages do not use categories in WordPress. This finding is informational.', 'amy-agent' ),
						'categoriesHint'     => __( 'Assign categories below, or in the post editor.', 'amy-agent' ),
						'noCategories'       => __( 'No categories exist on this site yet.', 'amy-agent' ),
						'categoriesLoadError' => __( 'Could not load categories.', 'amy-agent' ),
						'fieldKeyphrase'     => __( 'Focus keyphrase', 'amy-agent' ),
						'fieldSeoTitle'      => __( 'SEO title', 'amy-agent' ),
						'fieldMetaDesc'      => __( 'Meta description', 'amy-agent' ),
						'fieldFeatured'      => __( 'Featured image', 'amy-agent' ),
						'fieldAlt'           => __( 'Featured image alt text', 'amy-agent' ),
						'fieldMediaAlt'      => __( 'Alt text', 'amy-agent' ),
						'fieldMediaTitle'    => __( 'Title', 'amy-agent' ),
						'fieldCaption'       => __( 'Caption', 'amy-agent' ),
						'fieldDescription'   => __( 'Description', 'amy-agent' ),
						'fieldTermDesc'      => __( 'Term description', 'amy-agent' ),
						'fieldOg'            => __( 'Facebook / Open Graph', 'amy-agent' ),
						'fieldTwitter'       => __( 'X / Twitter', 'amy-agent' ),
						'fieldCategories'    => __( 'Categories', 'amy-agent' ),
						'fieldOgTitle'       => __( 'Facebook title', 'amy-agent' ),
						'fieldOgDesc'        => __( 'Facebook description', 'amy-agent' ),
						'fieldOgImage'       => __( 'Facebook image URL', 'amy-agent' ),
						'fieldTwTitle'       => __( 'X title', 'amy-agent' ),
						'fieldTwDesc'        => __( 'X description', 'amy-agent' ),
						'fieldTwImage'       => __( 'X image URL', 'amy-agent' ),
						'approve'            => __( 'Approve & write', 'amy-agent' ),
						'reject'             => __( 'Reject', 'amy-agent' ),
						'rejectReason'       => __( 'Reject reason (optional)', 'amy-agent' ),
						'saving'             => __( 'Saving…', 'amy-agent' ),
						'approveSuccess'     => __( 'Approved. Fields were written to WordPress.', 'amy-agent' ),
						'approveError'       => __( 'WordPress was updated, but recording approval failed.', 'amy-agent' ),
						'writeError'         => __( 'Could not write fields through the WordPress REST API.', 'amy-agent' ),
						'termWriteError'     => __( 'Could not write Yoast fields for this category or tag.', 'amy-agent' ),
						'rejectSuccess'      => __( 'Check rejected. Nothing was written to WordPress.', 'amy-agent' ),
						'rejectError'        => __( 'Could not reject this check.', 'amy-agent' ),
						'historyError'       => __( 'Could not load previous checks. Check the Amy Agent service connection.', 'amy-agent' ),
						'loadCheckError'     => __( 'Could not load that check.', 'amy-agent' ),
						'emptyState'         => __( 'Choose a content type to see every published item as a card. Nothing to type.', 'amy-agent' ),
						'emptyList'          => __( 'Nothing published in this type yet.', 'amy-agent' ),
						'promptLoaded'       => __( 'Here they are. Check all, 5, or 10 — or click cards to pick exactly which ones.', 'amy-agent' ),
						'promptCount'        => __( 'Manual (one batch at a time) or automatic (everything in this run)?', 'amy-agent' ),
						'promptHand'         => __( 'Start with the cards you picked. Amy will check just those.', 'amy-agent' ),
						'promptWorking'      => __( 'Working through this batch…', 'amy-agent' ),
						'promptContinue'     => __( 'That batch is done. Continue, or stop here?', 'amy-agent' ),
						'promptStopped'      => __( 'Stopped. Already-checked cards stay as they are.', 'amy-agent' ),
						'choiceAll'          => __( 'All', 'amy-agent' ),
						'choice5'            => __( '5', 'amy-agent' ),
						'choice10'           => __( '10', 'amy-agent' ),
						'choiceManual'       => __( 'Manual', 'amy-agent' ),
						'choiceAuto'         => __( 'Automatic', 'amy-agent' ),
						'startSelected'      => __( 'Start (%s selected)', 'amy-agent' ),
						'startRun'           => __( 'Start', 'amy-agent' ),
						'continue'           => __( 'Continue', 'amy-agent' ),
						'stop'               => __( 'Stop', 'amy-agent' ),
						'selectedCount'      => __( '%s selected', 'amy-agent' ),
						'summaryLine'        => __( 'Checked %1$s of %2$s. %3$s need work, %4$s have improvements, %5$s are good.', 'amy-agent' ),
						'summaryErrors'      => __( '%s had errors.', 'amy-agent' ),
						'buildingSnapshots'  => __( 'Gathering live fields…', 'amy-agent' ),
						'close'              => __( 'Close', 'amy-agent' ),
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

		$metrics     = $this->fetch_overview_metrics();
		$coming_soon = __( '(coming soon)', 'amy-agent' );
		$unavailable = __( '(unavailable)', 'amy-agent' );

		$top_stats = array(
			array(
				'label' => __( 'Tasks in Progress', 'amy-agent' ),
				'value' => $metrics['tasks_in_progress'],
				'note'  => null,
			),
			// No due-soon aggregate exists yet — urgent open tasks is the honest best available.
			array(
				'label' => __( 'Urgent Tasks', 'amy-agent' ),
				'value' => $metrics['urgent_tasks'],
				'note'  => null,
			),
			array(
				'label' => __( 'Chats This Week', 'amy-agent' ),
				'value' => $metrics['chats_this_week'],
				'note'  => null,
			),
			// No numeric SEO score API — show pending-approval issue count instead of inventing an average.
			array(
				'label' => __( 'Open SEO Issues', 'amy-agent' ),
				'value' => $metrics['seo_open'],
				'note'  => null,
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
					array(
						'label' => __( 'Open', 'amy-agent' ),
						'value' => $metrics['open_tasks'],
					),
					array(
						'label' => __( 'Urgent', 'amy-agent' ),
						'value' => $metrics['urgent_tasks'],
					),
				),
			),
			array(
				'slug'        => self::ANALYTICS_PAGE_SLUG,
				'title'       => __( 'Analytics', 'amy-agent' ),
				'description' => __( 'Review site usage and performance insights.', 'amy-agent' ),
				'icon'        => 'chart-bar',
				'metrics'     => array(
					array(
						'label' => __( 'Visitors', 'amy-agent' ),
						'value' => $metrics['visitors'],
					),
					// No page-view summary endpoint — Hot lead count is a real field from list_leads.
					array(
						'label' => __( 'Hot leads', 'amy-agent' ),
						'value' => $metrics['hot_leads'],
					),
				),
			),
			array(
				'slug'        => self::SEO_TASKS_PAGE_SLUG,
				'title'       => __( 'SEO Tasks', 'amy-agent' ),
				'description' => __( 'Find and fix SEO issues across your content.', 'amy-agent' ),
				'icon'        => 'search',
				'metrics'     => array(
					array(
						'label' => __( 'Open issues', 'amy-agent' ),
						'value' => $metrics['seo_open'],
					),
					array(
						'label' => __( 'Fixed', 'amy-agent' ),
						'value' => $metrics['seo_fixed'],
					),
				),
			),
			array(
				'slug'        => self::EMAIL_MARKETING_PAGE_SLUG,
				'title'       => __( 'Email Marketing', 'amy-agent' ),
				'description' => __( 'Audience from Analytics visitor emails — draft and approve, no auto-send.', 'amy-agent' ),
				'icon'        => 'email',
				'metrics'     => array(
					array(
						'label' => __( 'Audience', 'amy-agent' ),
						'value' => $metrics['email_audience'],
					),
					array(
						'label' => __( 'Drafts', 'amy-agent' ),
						'value' => null,
						// Drafts live in browser localStorage only — no server draft count.
						'note'  => __( '(browser only)', 'amy-agent' ),
					),
				),
			),
			array(
				'slug'        => 'amy-chat',
				'title'       => __( 'Chat', 'amy-agent' ),
				'description' => __( 'Talk with Amy the Leader from the dashboard.', 'amy-agent' ),
				'icon'        => 'format-chat',
				'metrics'     => array(
					array(
						'label' => __( 'Active now', 'amy-agent' ),
						'value' => $metrics['chats_active'],
					),
					array(
						'label' => __( 'This week', 'amy-agent' ),
						'value' => $metrics['chats_this_week'],
					),
				),
			),
			array(
				// Admin Roles & Social is not built — keep honest stub (no fake page).
				'slug'        => '',
				'href'        => '#',
				'title'       => __( 'Admin Roles & Social', 'amy-agent' ),
				'description' => __( 'Team permissions and connected social platforms.', 'amy-agent' ),
				'icon'        => 'groups',
				'coming_soon' => true,
				'metrics'     => array(
					array(
						'label' => __( 'Team members', 'amy-agent' ),
						'value' => null,
						'note'  => $coming_soon,
					),
					array(
						'label' => __( 'Platforms', 'amy-agent' ),
						'value' => null,
						'note'  => $coming_soon,
					),
				),
			),
			array(
				'slug'        => Amy_Settings::PAGE_SLUG,
				'title'       => __( 'Settings', 'amy-agent' ),
				'description' => __( 'Connect the Python service, shared secret, and AI provider.', 'amy-agent' ),
				'icon'        => 'admin-generic',
				'metrics'     => array(
					array(
						'label' => __( 'Service URL', 'amy-agent' ),
						'value' => $metrics['service_configured']
							? __( 'Configured', 'amy-agent' )
							: __( 'Not set', 'amy-agent' ),
					),
					array(
						'label' => __( 'Health', 'amy-agent' ),
						'value' => $metrics['service_health'],
						'note'  => empty( $metrics['service_configured'] )
							? __( '(set URL + secret)', 'amy-agent' )
							: null,
					),
				),
			),
			array(
				'slug'        => self::BRAND_PAGE_SLUG,
				'title'       => __( 'Brand & Avatar', 'amy-agent' ),
				'description' => __( 'Manage Amy’s look, name, and avatar.', 'amy-agent' ),
				'icon'        => 'admin-users',
				'metrics'     => array(
					array(
						'label' => __( 'Avatar', 'amy-agent' ),
						'value' => $metrics['brand_avatar'],
					),
				),
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

			<?php if ( ! empty( $metrics['connection_hint'] ) ) : ?>
				<p class="amy-agent-overview__connection-hint" role="status">
					<?php echo esc_html( $metrics['connection_hint'] ); ?>
				</p>
			<?php endif; ?>

			<div class="amy-agent-overview__stats">
				<?php foreach ( $top_stats as $stat ) : ?>
					<?php
					$display = $this->format_overview_metric_value( $stat['value'] ?? null );
					$note    = isset( $stat['note'] ) ? $stat['note'] : null;
					if ( null === ( $stat['value'] ?? null ) && null === $note ) {
						$note = $unavailable;
					}
					?>
					<div class="amy-agent-overview__stat">
						<p class="amy-agent-overview__stat-label"><?php echo esc_html( $stat['label'] ); ?></p>
						<p class="amy-agent-overview__stat-value">
							<?php echo esc_html( $display ); ?>
							<?php if ( null !== $note && '' !== $note ) : ?>
								<span class="amy-agent-overview__coming-soon"><?php echo esc_html( $note ); ?></span>
							<?php endif; ?>
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
					if ( ! empty( $card['coming_soon'] ) ) {
						$card_classes .= ' amy-agent-overview__card--coming-soon';
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
								<?php foreach ( $card['metrics'] as $metric ) : ?>
									<?php
									$metric_value = array_key_exists( 'value', $metric ) ? $metric['value'] : null;
									$metric_note  = isset( $metric['note'] ) ? $metric['note'] : null;
									if ( null === $metric_value && null === $metric_note ) {
										$metric_note = $unavailable;
									}
									?>
									<div class="amy-agent-overview__card-metric">
										<p class="amy-agent-overview__card-metric-label"><?php echo esc_html( $metric['label'] ); ?></p>
										<p class="amy-agent-overview__card-metric-value">
											<?php echo esc_html( $this->format_overview_metric_value( $metric_value ) ); ?>
											<?php if ( null !== $metric_note && '' !== $metric_note ) : ?>
												<span class="amy-agent-overview__coming-soon"><?php echo esc_html( $metric_note ); ?></span>
											<?php endif; ?>
										</p>
									</div>
								<?php endforeach; ?>
							</div>
						<?php endif; ?>

						<?php if ( ! empty( $card['coming_soon'] ) ) : ?>
							<span class="amy-agent-overview__card-link amy-agent-overview__card-link--disabled">
								<?php echo esc_html( $coming_soon ); ?>
							</span>
						<?php else : ?>
							<a
								class="amy-agent-overview__card-link"
								href="<?php echo esc_url( $card_url ); ?>"
							>
								<?php echo esc_html__( 'See more →', 'amy-agent' ); ?>
							</a>
						<?php endif; ?>
					</article>
				<?php endforeach; ?>
			</div>
		</div>
		<?php
	}

	/**
	 * Task Service — board/list surface backed by the Python tasks API.
	 */
	public function render_task_service() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$stats_body = $this->fetch_task_stats_for_page();
		$stats      = array(
			array(
				'key'   => 'open_tasks',
				'label' => __( 'Open Tasks', 'amy-agent' ),
				'icon'  => 'clipboard',
				'value' => isset( $stats_body['open_tasks'] ) ? (string) (int) $stats_body['open_tasks'] : '0',
			),
			array(
				'key'   => 'urgent_tasks',
				'label' => __( 'Urgent Tasks', 'amy-agent' ),
				'icon'  => 'warning',
				'value' => isset( $stats_body['urgent_tasks'] ) ? (string) (int) $stats_body['urgent_tasks'] : '0',
			),
			array(
				'key'   => 'completed_this_week',
				'label' => __( 'Completed This Week', 'amy-agent' ),
				'icon'  => 'yes-alt',
				'value' => isset( $stats_body['completed_this_week'] ) ? (string) (int) $stats_body['completed_this_week'] : '0',
			),
			array(
				'key'   => 'team_completion_rate',
				'label' => __( 'Team Completion Rate', 'amy-agent' ),
				'icon'  => 'chart-bar',
				'value' => ( isset( $stats_body['team_completion_rate'] ) ? (string) (int) $stats_body['team_completion_rate'] : '0' ) . '%',
			),
		);

		$columns = array(
			'todo'              => __( 'To Do', 'amy-agent' ),
			'running'           => __( 'Amy Running', 'amy-agent' ),
			'in_progress'       => __( 'In Progress', 'amy-agent' ),
			'waiting_extension' => __( 'Waiting on Extension', 'amy-agent' ),
			'failed'            => __( 'Failed', 'amy-agent' ),
			'done'              => __( 'Done', 'amy-agent' ),
		);

		$assignees = $this->get_task_assignees_for_js();
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
					<?php $this->render_notifications_panel(); ?>
					<button
						type="button"
						class="amy-agent-task-service__btn amy-agent-task-service__btn--accent"
						id="amy-agent-task-new"
					>
						<?php echo esc_html__( '+ New Task', 'amy-agent' ); ?>
					</button>
				</div>
			</header>

			<p class="amy-agent-task-service__notice" id="amy-agent-task-notice" hidden role="status"></p>

			<div class="amy-agent-task-service__help" id="amy-agent-task-help" hidden>
				<p class="amy-agent-task-service__help-text" id="amy-agent-task-help-text"></p>
				<p class="amy-agent-task-service__help-links">
					<a id="amy-agent-task-help-connection" href="<?php echo esc_url( $this->settings->settings_deep_link( 'connection', 'connection' ) ); ?>">
						<?php echo esc_html__( 'Settings → Connection', 'amy-agent' ); ?>
					</a>
					<span aria-hidden="true">·</span>
					<a id="amy-agent-task-help-telegram" href="<?php echo esc_url( $this->settings->settings_deep_link( 'telegram', 'telegram' ) ); ?>">
						<?php echo esc_html__( 'Settings → Telegram', 'amy-agent' ); ?>
					</a>
					<span aria-hidden="true">·</span>
					<a id="amy-agent-task-help-profile" href="<?php echo esc_url( admin_url( 'admin.php?page=' . self::MY_PROFILE_PAGE_SLUG ) ); ?>">
						<?php echo esc_html__( 'My Profile → Telegram', 'amy-agent' ); ?>
					</a>
				</p>
			</div>

			<div class="amy-agent-task-service__stats">
				<?php foreach ( $stats as $stat ) : ?>
					<div class="amy-agent-task-service__stat" data-stat="<?php echo esc_attr( $stat['key'] ); ?>">
						<span class="amy-agent-task-service__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-<?php echo esc_attr( $stat['icon'] ); ?>"></span>
						</span>
						<div class="amy-agent-task-service__stat-body">
							<p class="amy-agent-task-service__stat-label"><?php echo esc_html( $stat['label'] ); ?></p>
							<p class="amy-agent-task-service__stat-value" data-stat-value="<?php echo esc_attr( $stat['key'] ); ?>">
								<?php echo esc_html( $stat['value'] ); ?>
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
								data-amy-quick-add="<?php echo esc_attr( $status_key ); ?>"
								aria-label="<?php echo esc_attr__( 'Quick add task', 'amy-agent' ); ?>"
							>
								<span class="dashicons dashicons-plus-alt2" aria-hidden="true"></span>
								<span class="screen-reader-text"><?php echo esc_html__( 'Quick add', 'amy-agent' ); ?></span>
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
						<input type="hidden" id="amy-agent-task-id" name="id" value="" />

						<label class="amy-agent-task-service__field" for="amy-agent-task-title">
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Title', 'amy-agent' ); ?></span>
							<input type="text" id="amy-agent-task-title" name="title" required placeholder="<?php echo esc_attr__( 'What needs to be done?', 'amy-agent' ); ?>" />
						</label>

						<fieldset class="amy-agent-task-service__field amy-agent-task-service__field--mode">
							<legend class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Who does this?', 'amy-agent' ); ?></legend>
							<label class="amy-agent-task-service__radio">
								<input type="radio" name="assignee_mode" value="amy" id="amy-agent-task-mode-amy" />
								<span><?php echo esc_html__( 'Amy does this', 'amy-agent' ); ?></span>
							</label>
							<label class="amy-agent-task-service__radio">
								<input type="radio" name="assignee_mode" value="human" id="amy-agent-task-mode-human" checked />
								<span><?php echo esc_html__( 'Someone does this', 'amy-agent' ); ?></span>
							</label>
							<p class="amy-agent-task-service__field-hint" id="amy-agent-task-amy-mode-hint" hidden>
								<?php echo esc_html__( 'Amy is assigned only — automatic execution comes later. Status stays honest (no fake complete).', 'amy-agent' ); ?>
							</p>
						</fieldset>

						<label class="amy-agent-task-service__field" for="amy-agent-task-assignee" id="amy-agent-task-human-assignee-field">
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Assignee', 'amy-agent' ); ?></span>
							<select id="amy-agent-task-assignee" name="assignee">
								<option value=""><?php echo esc_html__( 'Select someone…', 'amy-agent' ); ?></option>
								<?php foreach ( $assignees as $assignee ) : ?>
									<?php if ( 'amy' === ( $assignee['type'] ?? '' ) ) : ?>
										<?php continue; ?>
									<?php endif; ?>
									<option value="<?php echo esc_attr( $assignee['key'] ); ?>">
										<?php echo esc_html( $assignee['label'] ); ?>
									</option>
								<?php endforeach; ?>
							</select>
						</label>

						<label class="amy-agent-task-service__check" for="amy-agent-task-amy-capable">
							<input type="checkbox" id="amy-agent-task-amy-capable" name="amy_capable" value="1" />
							<span><?php echo esc_html__( 'Amy can do this work (digital / in-system)', 'amy-agent' ); ?></span>
						</label>
						<p class="amy-agent-task-service__field-hint">
							<?php echo esc_html__( 'On timeout, Amy runs capable digital/in-system work automatically. You can also use “Let Amy take it”. Otherwise reassign a human.', 'amy-agent' ); ?>
						</p>

						<label class="amy-agent-task-service__field" for="amy-agent-task-status" id="amy-agent-task-status-field" hidden>
							<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Status', 'amy-agent' ); ?></span>
							<select id="amy-agent-task-status" name="status">
								<?php foreach ( $columns as $status_key => $status_label ) : ?>
									<option value="<?php echo esc_attr( $status_key ); ?>"><?php echo esc_html( $status_label ); ?></option>
								<?php endforeach; ?>
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

						<div class="amy-agent-task-service__extension" id="amy-agent-task-extension" hidden>
							<label class="amy-agent-task-service__field" for="amy-agent-task-extension-hours">
								<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Request extension (hours)', 'amy-agent' ); ?></span>
								<input type="number" id="amy-agent-task-extension-hours" min="0.5" step="0.5" placeholder="2" />
							</label>
							<button type="button" class="amy-agent-task-service__btn amy-agent-task-service__btn--ghost" id="amy-agent-task-extension-submit">
								<?php echo esc_html__( 'Request Extension', 'amy-agent' ); ?>
							</button>
							<p class="amy-agent-task-service__extension-result" id="amy-agent-task-extension-result" hidden role="status"></p>
						</div>

						<div class="amy-agent-task-service__expiry" id="amy-agent-task-expiry" hidden>
							<p class="amy-agent-task-service__expiry-title"><?php echo esc_html__( 'Past due — owner actions', 'amy-agent' ); ?></p>
							<p class="amy-agent-task-service__field-hint" id="amy-agent-task-expiry-hint">
								<?php echo esc_html__( 'Reassign a human, or if this task is Amy-capable, let Amy take the digital/in-system work.', 'amy-agent' ); ?>
							</p>
							<label class="amy-agent-task-service__field" for="amy-agent-task-expiry-assignee">
								<span class="amy-agent-task-service__field-label"><?php echo esc_html__( 'Reassign to', 'amy-agent' ); ?></span>
								<select id="amy-agent-task-expiry-assignee">
									<option value=""><?php echo esc_html__( 'Select someone…', 'amy-agent' ); ?></option>
									<?php foreach ( $assignees as $assignee ) : ?>
										<?php if ( 'amy' === ( $assignee['type'] ?? '' ) ) : ?>
											<?php continue; ?>
										<?php endif; ?>
										<option value="<?php echo esc_attr( (string) (int) ( $assignee['wpUserId'] ?? 0 ) ); ?>">
											<?php echo esc_html( $assignee['label'] ); ?>
										</option>
									<?php endforeach; ?>
								</select>
							</label>
							<div class="amy-agent-task-service__expiry-actions">
								<button type="button" class="amy-agent-task-service__btn amy-agent-task-service__btn--accent" id="amy-agent-task-expiry-reassign-other">
									<?php echo esc_html__( 'Reassign', 'amy-agent' ); ?>
								</button>
								<button type="button" class="amy-agent-task-service__btn amy-agent-task-service__btn--ghost" id="amy-agent-task-expiry-reassign-same">
									<?php echo esc_html__( 'Reassign same person', 'amy-agent' ); ?>
								</button>
								<button type="button" class="amy-agent-task-service__btn amy-agent-task-service__btn--ghost" id="amy-agent-task-expiry-ack">
									<?php echo esc_html__( 'Acknowledge manually', 'amy-agent' ); ?>
								</button>
								<button
									type="button"
									class="amy-agent-task-service__btn amy-agent-task-service__btn--ghost"
									id="amy-agent-task-expiry-amy-take"
									disabled
									title="<?php echo esc_attr__( 'Available when this task is marked Amy-capable (digital / in-system).', 'amy-agent' ); ?>"
								>
									<?php echo esc_html__( 'Let Amy take it', 'amy-agent' ); ?>
								</button>
							</div>
							<p class="amy-agent-task-service__expiry-result" id="amy-agent-task-expiry-result" hidden role="status"></p>
						</div>

						<p class="amy-agent-task-service__form-error" id="amy-agent-task-form-error" hidden role="alert"></p>

						<div class="amy-agent-task-service__modal-actions">
							<button
								type="button"
								class="amy-agent-task-service__btn amy-agent-task-service__btn--danger"
								id="amy-agent-task-delete"
								hidden
							>
								<?php echo esc_html__( 'Delete', 'amy-agent' ); ?>
							</button>
							<button type="button" class="amy-agent-task-service__btn amy-agent-task-service__btn--ghost" data-amy-modal-close>
								<?php echo esc_html__( 'Cancel', 'amy-agent' ); ?>
							</button>
							<button
								type="submit"
								class="amy-agent-task-service__btn amy-agent-task-service__btn--accent"
								id="amy-agent-task-submit"
							>
								<?php echo esc_html__( 'Create Task', 'amy-agent' ); ?>
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
		<?php
	}

	/**
	 * Assignable humans + Amy for Task Service selects.
	 *
	 * Pool is currently users with manage_options (same gate as this page).
	 * TODO: switch to the Amy Agent role/permission system once
	 * docs/05-admin-roles-and-social-publishing-plan.md is implemented.
	 *
	 * @return array<int, array{key: string, label: string, type: string, wpUserId: int|null, initials: string, color: string}>
	 */
	private function get_task_assignees_for_js() {
		$palette = array( '#3D8BFF', '#22C55E', '#A855F7', '#EF4444', '#14B8A6', '#F59E0B', '#EC4899' );
		$list    = array(
			array(
				'key'      => 'amy',
				'label'    => __( 'Amy', 'amy-agent' ),
				'type'     => 'amy',
				'wpUserId' => null,
				'initials' => 'A',
				'color'    => '#FF7A18',
			),
		);

		$users = get_users(
			array(
				'capability' => 'manage_options',
				'orderby'    => 'display_name',
				'order'      => 'ASC',
			)
		);

		foreach ( $users as $index => $user ) {
			$name     = $user->display_name ? $user->display_name : $user->user_login;
			$initials = $this->initials_from_name( $name );
			$list[]   = array(
				'key'      => 'user:' . (int) $user->ID,
				'label'    => $name,
				'type'     => 'human',
				'wpUserId' => (int) $user->ID,
				'initials' => $initials,
				'color'    => $palette[ $index % count( $palette ) ],
			);
		}

		return $list;
	}

	/**
	 * Two-letter initials from a display name.
	 *
	 * @param string $name Display name.
	 * @return string
	 */
	private function initials_from_name( $name ) {
		$parts = preg_split( '/\s+/', trim( (string) $name ) );
		if ( ! $parts || ! isset( $parts[0][0] ) ) {
			return '?';
		}
		$first = strtoupper( substr( $parts[0], 0, 1 ) );
		if ( count( $parts ) > 1 && isset( $parts[ count( $parts ) - 1 ][0] ) ) {
			return $first . strtoupper( substr( $parts[ count( $parts ) - 1 ], 0, 1 ) );
		}
		return $first;
	}

	/**
	 * Shared notification bell assets (Task Service + My Profile).
	 */
	private function enqueue_notifications_assets() {
		wp_enqueue_style(
			'amy-agent-admin-notifications',
			AMY_AGENT_URL . 'admin/css/admin-notifications.css',
			array( 'dashicons' ),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-agent-admin-notifications',
			AMY_AGENT_URL . 'admin/js/admin-notifications.js',
			array( 'jquery' ),
			AMY_AGENT_VERSION,
			true
		);

		$assignees = $this->get_task_assignees_for_js();
		$humans    = array();
		foreach ( $assignees as $row ) {
			if ( 'human' === ( $row['type'] ?? '' ) && ! empty( $row['wpUserId'] ) ) {
				$humans[] = array(
					'id'    => (int) $row['wpUserId'],
					'label' => (string) $row['label'],
				);
			}
		}

		wp_localize_script(
			'amy-agent-admin-notifications',
			'amyAgentNotifications',
			array(
				'ajaxUrl'        => admin_url( 'admin-ajax.php' ),
				'nonce'          => wp_create_nonce( Amy_Tasks_Ajax::NONCE_ACTION ),
				'currentUserId'  => get_current_user_id(),
				'taskServiceUrl' => admin_url( 'admin.php?page=' . self::TASK_SERVICE_PAGE_SLUG ),
				'assignees'      => $humans,
				'i18n'           => array(
					'approve'          => __( 'Approve', 'amy-agent' ),
					'deny'             => __( 'Deny', 'amy-agent' ),
					'openTask'         => __( 'Open task', 'amy-agent' ),
					'acknowledge'      => __( 'Acknowledge', 'amy-agent' ),
					'reassignSame'     => __( 'Reassign same', 'amy-agent' ),
					'reassignOther'    => __( 'Reassign…', 'amy-agent' ),
					'confirmReassign'  => __( 'Confirm reassign', 'amy-agent' ),
					'selectAssignee'   => __( 'Select someone…', 'amy-agent' ),
					'amyTake'          => __( 'Let Amy take it', 'amy-agent' ),
					'amyTakeDisabled'  => __( 'Only Amy-capable (digital / in-system) tasks can be handed to Amy.', 'amy-agent' ),
					'dismiss'          => __( 'Dismiss', 'amy-agent' ),
					'empty'            => __( 'No unread notifications.', 'amy-agent' ),
					'reassignError'    => __( 'Could not reassign. Please try again.', 'amy-agent' ),
				),
			)
		);
	}

	/**
	 * Push manage_options users to the Python service for urgent reassignment + P3 owner resolve.
	 */
	private function sync_dashboard_users_to_service() {
		if ( ! function_exists( 'amy_agent' ) ) {
			return;
		}

		$users = get_users(
			array(
				'capability' => 'manage_options',
				'orderby'    => 'ID',
				'order'      => 'ASC',
			)
		);
		$payload = array();
		foreach ( $users as $user ) {
			$uid      = (int) $user->ID;
			$chat_id  = (int) get_user_meta( $uid, Amy_Task_Notify::USER_META_CHAT_ID, true );
			$backup   = (int) get_user_meta( $uid, self::USER_TASK_BACKUP_META, true );
			$payload[] = array(
				'wp_user_id'         => $uid,
				'display_name'       => $user->display_name ? $user->display_name : $user->user_login,
				'telegram_linked'    => $chat_id > 0,
				'backup_wp_user_id'  => $backup > 0 ? $backup : null,
			);
		}
		$site_default = (int) $this->settings->get_task_default_owner_wp_user_id();
		amy_agent()->api_client->sync_dashboard_users( $payload, $site_default );
	}

	/**
	 * Shared notification bell markup for Task Service + My Profile headers.
	 */
	private function render_notifications_panel() {
		?>
		<div class="amy-agent-notifications" id="amy-agent-notifications">
			<button
				type="button"
				class="amy-agent-notifications__toggle"
				aria-expanded="false"
				aria-controls="amy-agent-notifications-panel"
				aria-label="<?php echo esc_attr__( 'Notifications', 'amy-agent' ); ?>"
			>
				<span class="dashicons dashicons-bell" aria-hidden="true"></span>
				<span class="amy-agent-notifications__badge" hidden>0</span>
			</button>
			<div class="amy-agent-notifications__panel" id="amy-agent-notifications-panel" hidden>
				<p class="amy-agent-notifications__title"><?php echo esc_html__( 'Notifications', 'amy-agent' ); ?></p>
				<ul class="amy-agent-notifications__list"></ul>
				<p class="amy-agent-notifications__empty"><?php echo esc_html__( 'No unread notifications.', 'amy-agent' ); ?></p>
			</div>
		</div>
		<?php
	}

	/**
	 * Format an Overview metric for display.
	 *
	 * null → em dash (unavailable / not applicable). Integers and strings pass through.
	 *
	 * @param int|string|null $value Metric value.
	 * @return string
	 */
	private function format_overview_metric_value( $value ) {
		if ( null === $value ) {
			return '—';
		}
		if ( is_int( $value ) ) {
			return (string) $value;
		}
		return (string) $value;
	}

	/**
	 * Server-side Overview metrics from existing Amy_Api_Client methods.
	 *
	 * Fail soft: API/connection failures yield null (rendered as —), not fake zeros.
	 * Successful empty responses yield real 0. When /v1/health fails, skip further
	 * tool fetches to avoid stacking request timeouts on Overview.
	 *
	 * @return array{
	 *   tasks_in_progress: int|null,
	 *   open_tasks: int|null,
	 *   urgent_tasks: int|null,
	 *   chats_active: int|null,
	 *   chats_this_week: int|null,
	 *   seo_open: int|null,
	 *   seo_fixed: int|null,
	 *   visitors: int|null,
	 *   hot_leads: int|null,
	 *   email_audience: int|null,
	 *   service_configured: bool,
	 *   service_health: string|null,
	 *   brand_avatar: string,
	 *   connection_hint: string|null
	 * }
	 */
	private function fetch_overview_metrics() {
		$out = array(
			'tasks_in_progress'  => null,
			'open_tasks'         => null,
			'urgent_tasks'       => null,
			'chats_active'       => null,
			'chats_this_week'    => null,
			'seo_open'           => null,
			'seo_fixed'          => null,
			'visitors'           => null,
			'hot_leads'          => null,
			'email_audience'     => null,
			'service_configured' => $this->settings->is_service_configured(),
			'service_health'     => null,
			'brand_avatar'       => '' !== $this->settings->get_custom_avatar_url()
				? __( 'Custom', 'amy-agent' )
				: __( 'Default', 'amy-agent' ),
			'connection_hint'    => null,
		);

		if ( ! $out['service_configured'] ) {
			$out['connection_hint'] = __(
				'Amy service URL or shared secret is not set — tool counts show as unavailable until Settings is configured.',
				'amy-agent'
			);
			$out['service_health'] = __( 'n/a', 'amy-agent' );
			return $out;
		}

		if ( ! function_exists( 'amy_agent' ) ) {
			$out['connection_hint'] = __(
				'Amy Agent bootstrap is unavailable — tool counts cannot be loaded.',
				'amy-agent'
			);
			$out['service_health'] = __( 'n/a', 'amy-agent' );
			return $out;
		}

		$client = amy_agent()->api_client;

		$health = $client->health();
		if ( empty( $health['ok'] ) ) {
			$out['service_health']  = __( 'Down', 'amy-agent' );
			$out['connection_hint'] = __(
				'Could not reach the Amy Python service — Overview shows — instead of inventing zeros. Check Settings → Service URL.',
				'amy-agent'
			);
			return $out;
		}

		$out['service_health'] = __( 'OK', 'amy-agent' );

		$task_stats = $client->get_task_stats();
		if ( ! empty( $task_stats['ok'] ) && is_array( $task_stats['body'] ) ) {
			$body                = $task_stats['body'];
			$out['open_tasks']   = isset( $body['open_tasks'] ) ? (int) $body['open_tasks'] : 0;
			$out['urgent_tasks'] = isset( $body['urgent_tasks'] ) ? (int) $body['urgent_tasks'] : 0;
		}

		$in_progress = $client->list_tasks( array( 'status' => 'in_progress' ) );
		if ( ! empty( $in_progress['ok'] ) && is_array( $in_progress['body'] ) ) {
			$tasks = isset( $in_progress['body']['tasks'] ) && is_array( $in_progress['body']['tasks'] )
				? $in_progress['body']['tasks']
				: array();
			$out['tasks_in_progress'] = count( $tasks );
		}

		$leads = $client->list_leads();
		if ( ! empty( $leads['ok'] ) && is_array( $leads['body'] ) ) {
			$lead_rows = isset( $leads['body']['leads'] ) && is_array( $leads['body']['leads'] )
				? $leads['body']['leads']
				: array();
			$out['visitors'] = count( $lead_rows );
			$hot             = 0;
			$email_audience  = 0;
			foreach ( $lead_rows as $lead ) {
				if ( ! is_array( $lead ) ) {
					continue;
				}
				if ( 'hot' === ( $lead['lead_status'] ?? '' ) ) {
					++$hot;
				}
				if ( ! empty( $lead['lead_email'] ) ) {
					++$email_audience;
				}
			}
			$out['hot_leads']      = $hot;
			$out['email_audience'] = $email_audience;
		}

		$seo = $client->list_seo_checks();
		if ( ! empty( $seo['ok'] ) && is_array( $seo['body'] ) ) {
			$checks = isset( $seo['body']['checks'] ) && is_array( $seo['body']['checks'] )
				? $seo['body']['checks']
				: array();
			$open  = 0;
			$fixed = 0;
			foreach ( $checks as $check ) {
				if ( ! is_array( $check ) ) {
					continue;
				}
				$status = (string) ( $check['status'] ?? '' );
				if ( 'pending_approval' === $status ) {
					++$open;
				} elseif ( 'approved' === $status ) {
					++$fixed;
				}
			}
			$out['seo_open']  = $open;
			$out['seo_fixed'] = $fixed;
		}

		$user_id = get_current_user_id();
		$chats   = $client->list_conversations( $user_id, true, 'admin', false );
		if ( ! empty( $chats['ok'] ) && is_array( $chats['body'] ) ) {
			$conversations = isset( $chats['body']['conversations'] ) && is_array( $chats['body']['conversations'] )
				? $chats['body']['conversations']
				: array();
			$week_ago = time() - ( 7 * DAY_IN_SECONDS );
			$active   = 0;
			$week     = 0;
			foreach ( $conversations as $conv ) {
				if ( ! is_array( $conv ) ) {
					continue;
				}
				// list_conversations(include_archived=false) already excludes archived/deleted.
				++$active;
				$updated = isset( $conv['updated_at'] ) ? (float) $conv['updated_at'] : 0.0;
				if ( $updated >= $week_ago ) {
					++$week;
				}
			}
			$out['chats_active']    = $active;
			$out['chats_this_week'] = $week;
		}

		return $out;
	}

	/**
	 * Fetch task stats from the Python service for initial page render.
	 *
	 * @return array<string, int>
	 */
	private function fetch_task_stats_for_page() {
		$defaults = array(
			'open_tasks'            => 0,
			'urgent_tasks'          => 0,
			'completed_this_week'   => 0,
			'team_completion_rate'  => 0,
		);

		if ( ! function_exists( 'amy_agent' ) ) {
			return $defaults;
		}

		$result = amy_agent()->api_client->get_task_stats();
		if ( ! $result['ok'] || ! is_array( $result['body'] ) ) {
			return $defaults;
		}

		return array_merge( $defaults, $result['body'] );
	}

	/**
	 * Per-user task counts for My Profile stat cards.
	 *
	 * Uses GET /v1/tasks?assignee_wp_user_id=… (same list filter as Task Service)
	 * and aggregates client-side-equivalent counts in PHP so My Profile's
	 * edit-only JS does not need a parallel task-fetch path.
	 *
	 * @param int $user_id Current WordPress user ID.
	 * @return array{open_tasks: int, completed_tasks: int, completed_this_week: int}
	 */
	private function fetch_my_profile_task_stats( $user_id ) {
		$defaults = array(
			'open_tasks'          => 0,
			'completed_tasks'     => 0,
			'completed_this_week' => 0,
		);

		$user_id = (int) $user_id;
		if ( $user_id < 1 || ! function_exists( 'amy_agent' ) ) {
			return $defaults;
		}

		$result = amy_agent()->api_client->list_tasks(
			array( 'assignee_wp_user_id' => $user_id )
		);
		if ( ! $result['ok'] || ! is_array( $result['body'] ) ) {
			return $defaults;
		}

		$tasks = isset( $result['body']['tasks'] ) && is_array( $result['body']['tasks'] )
			? $result['body']['tasks']
			: array();

		$week_ago = time() - ( 7 * DAY_IN_SECONDS );
		$open     = 0;
		$done     = 0;
		$week     = 0;

		foreach ( $tasks as $task ) {
			if ( ! is_array( $task ) ) {
				continue;
			}
			// List is already filtered by assignee_wp_user_id; still require human assignee.
			if ( ( $task['assignee_type'] ?? '' ) !== 'human' ) {
				continue;
			}
			if ( (int) ( $task['assignee_wp_user_id'] ?? 0 ) !== $user_id ) {
				continue;
			}

			$status = (string) ( $task['status'] ?? '' );
			if ( 'done' !== $status ) {
				++$open;
				continue;
			}

			++$done;
			$updated = isset( $task['updated_at'] ) ? (float) $task['updated_at'] : 0.0;
			if ( $updated >= $week_ago ) {
				++$week;
			}
		}

		return array(
			'open_tasks'          => $open,
			'completed_tasks'     => $done,
			'completed_this_week' => $week,
		);
	}

	/**
	 * My Profile — personal task activity for the logged-in user.
	 */
	public function render_my_profile() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$user          = wp_get_current_user();
		$avatar_url    = $this->get_user_avatar_url( $user->ID );
		$role_label    = $this->get_primary_role_label( $user );
		$joined        = $this->format_joined_date( $user->user_registered );
		$custom_avatar = trim( (string) get_user_meta( $user->ID, self::USER_AVATAR_META, true ) );
		$user_stats    = $this->fetch_my_profile_task_stats( (int) $user->ID );

		$top_stats = array(
			array(
				'label' => __( 'Open Tasks', 'amy-agent' ),
				'icon'  => 'clipboard',
				'value' => (string) (int) $user_stats['open_tasks'],
			),
			array(
				'label' => __( 'Completed Tasks', 'amy-agent' ),
				'icon'  => 'yes-alt',
				'value' => (string) (int) $user_stats['completed_tasks'],
			),
			array(
				'label' => __( 'This Week', 'amy-agent' ),
				'icon'  => 'calendar-alt',
				'value' => (string) (int) $user_stats['completed_this_week'],
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
					<?php $this->render_notifications_panel(); ?>
					<a
						class="amy-agent-my-profile__btn amy-agent-my-profile__btn--accent"
						href="<?php echo esc_url( admin_url( 'admin.php?page=' . self::TASK_SERVICE_PAGE_SLUG . '&amy_new_task=1' ) ); ?>"
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
								<?php echo esc_html( $stat['value'] ); ?>
							</p>
						</div>
					</div>
				<?php endforeach; ?>
			</div>

			<?php
			$tg_chat_id      = (int) get_user_meta( (int) $user->ID, Amy_Task_Notify::USER_META_CHAT_ID, true );
			$tg_bot_username = (string) get_option( Amy_Telegram::OPTION_BOT_USERNAME, '' );
			$tg_enabled      = $this->settings->is_telegram_enabled();
			$tg_has_token    = '' !== $this->settings->get_telegram_token();
			$tg_webhook_ok   = Amy_Telegram::is_webhook_connected();
			$tg_settings_url = $this->settings->settings_deep_link( 'telegram', 'telegram' );
			?>
			<?php
			$backup_id    = (int) get_user_meta( (int) $user->ID, self::USER_TASK_BACKUP_META, true );
			$backup_users = get_users(
				array(
					'capability' => 'manage_options',
					'orderby'    => 'display_name',
					'order'      => 'ASC',
					'exclude'    => array( (int) $user->ID ),
				)
			);
			?>
			<section class="amy-agent-my-profile__panel amy-agent-my-profile__panel--backup" aria-label="<?php echo esc_attr__( 'Task backup', 'amy-agent' ); ?>">
				<h2 class="amy-agent-my-profile__panel-title">
					<span class="amy-agent-my-profile__panel-title-icon" aria-hidden="true">
						<span class="dashicons dashicons-groups"></span>
					</span>
					<?php echo esc_html__( 'Task backup', 'amy-agent' ); ?>
				</h2>
				<p class="amy-agent-my-profile__telegram-copy">
					<?php echo esc_html__( 'If you create tasks and become unreachable on timeout (no Telegram / gone), escalation uses the site default owner, then this backup. Designate who should cover for you.', 'amy-agent' ); ?>
				</p>
				<label class="amy-agent-my-profile__field" for="amy-my-profile-task-backup">
					<span class="amy-agent-my-profile__field-label"><?php echo esc_html__( 'My backup person', 'amy-agent' ); ?></span>
					<select id="amy-my-profile-task-backup" name="backup_wp_user_id">
						<option value="0"><?php echo esc_html__( '— None —', 'amy-agent' ); ?></option>
						<?php foreach ( $backup_users as $backup_user ) : ?>
							<option value="<?php echo esc_attr( (string) (int) $backup_user->ID ); ?>" <?php selected( $backup_id, (int) $backup_user->ID ); ?>>
								<?php echo esc_html( $backup_user->display_name ? $backup_user->display_name : $backup_user->user_login ); ?>
							</option>
						<?php endforeach; ?>
					</select>
				</label>
				<button type="button" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--outline" id="amy-my-profile-backup-save">
					<?php echo esc_html__( 'Save backup', 'amy-agent' ); ?>
				</button>
				<p class="amy-agent-my-profile__telegram-status" id="amy-my-profile-backup-status" role="status" hidden></p>
			</section>

			<section class="amy-agent-my-profile__panel amy-agent-my-profile__panel--telegram" aria-label="<?php echo esc_attr__( 'Telegram task alerts', 'amy-agent' ); ?>">
				<h2 class="amy-agent-my-profile__panel-title">
					<span class="amy-agent-my-profile__panel-title-icon" aria-hidden="true">
						<span class="dashicons dashicons-format-chat"></span>
					</span>
					<?php echo esc_html__( 'Telegram task alerts', 'amy-agent' ); ?>
				</h2>
				<p class="amy-agent-my-profile__telegram-copy">
					<?php
					echo esc_html__(
						'Link your Telegram account to receive assign, progress-check, and expiry alerts from the same Admin Bot configured in Amy → Settings → Telegram (no second bot). Email still uses FluentSMTP From the Marketing From address in Settings → General.',
						'amy-agent'
					);
					?>
				</p>
				<ol class="amy-agent-my-profile__bot-status" aria-label="<?php echo esc_attr__( 'Telegram bot setup status', 'amy-agent' ); ?>">
					<li class="<?php echo $tg_has_token ? 'is-done' : 'is-todo'; ?>">
						<?php
						echo $tg_has_token
							? esc_html__( '1. Bot token saved', 'amy-agent' )
							: esc_html__( '1. Paste BotFather token in Settings → Telegram → Save', 'amy-agent' );
						?>
					</li>
					<li class="<?php echo $tg_enabled ? 'is-done' : 'is-todo'; ?>">
						<?php
						echo $tg_enabled
							? esc_html__( '2. Telegram Admin Bot enabled', 'amy-agent' )
							: esc_html__( '2. Enable Telegram Admin Bot in Settings → Telegram', 'amy-agent' );
						?>
					</li>
					<li class="<?php echo $tg_webhook_ok ? 'is-done' : 'is-todo'; ?>">
						<?php
						echo $tg_webhook_ok
							? esc_html__( '3. Webhook connected', 'amy-agent' )
							: esc_html__( '3. Click Connect in Settings → Telegram (HTTPS required)', 'amy-agent' );
						?>
					</li>
				</ol>
				<p class="amy-agent-my-profile__telegram-settings-path">
					<a href="<?php echo esc_url( $tg_settings_url ); ?>">
						<?php echo esc_html__( 'Amy → Settings → Telegram', 'amy-agent' ); ?>
					</a>
					<?php echo esc_html__( '— token, Enable, and Connect live here.', 'amy-agent' ); ?>
				</p>
				<?php if ( ! $tg_enabled || ! $tg_has_token || ! $tg_webhook_ok ) : ?>
					<p class="amy-agent-my-profile__telegram-status" role="status">
						<?php
						if ( ! $tg_has_token ) {
							echo esc_html__( 'Bot token is missing. Finish step 1 in Settings → Telegram, then return here to link your chat.', 'amy-agent' );
						} elseif ( ! $tg_enabled ) {
							echo esc_html__( 'Telegram bot is disabled. Finish step 2 (Enable), then Connect.', 'amy-agent' );
						} else {
							echo esc_html__( 'Webhook is not connected. Finish step 3 (Connect, HTTPS required), then return here.', 'amy-agent' );
						}
						?>
						<a href="<?php echo esc_url( $tg_settings_url ); ?>">
							<?php echo esc_html__( 'Open Settings → Telegram', 'amy-agent' ); ?>
						</a>
					</p>
				<?php elseif ( $tg_chat_id > 0 ) : ?>
					<p class="amy-agent-my-profile__telegram-status is-linked" id="amy-my-profile-tg-status" role="status">
						<?php
						echo esc_html(
							sprintf(
								/* translators: %d: Telegram chat id */
								__( 'Linked (chat id %d). Task alerts will use this chat when the bot is connected.', 'amy-agent' ),
								$tg_chat_id
							)
						);
						?>
					</p>
					<button type="button" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--outline" id="amy-my-profile-tg-unlink">
						<?php echo esc_html__( 'Unlink Telegram', 'amy-agent' ); ?>
					</button>
				<?php else : ?>
					<p class="amy-agent-my-profile__telegram-status" id="amy-my-profile-tg-status" role="status">
						<?php
						if ( $tg_bot_username ) {
							echo esc_html(
								sprintf(
									/* translators: %s: bot username */
									__( 'Not linked yet. Connect to @%s with a one-time link.', 'amy-agent' ),
									$tg_bot_username
								)
							);
						} else {
							echo esc_html__( 'Bot is connected but username is still syncing. Generate a connect link below, or reopen Settings → Telegram.', 'amy-agent' );
						}
						?>
					</p>
					<div class="amy-agent-my-profile__telegram-actions">
						<button type="button" class="amy-agent-my-profile__btn amy-agent-my-profile__btn--accent" id="amy-my-profile-tg-link">
							<?php echo esc_html__( 'Connect Telegram', 'amy-agent' ); ?>
						</button>
						<a
							class="amy-agent-my-profile__btn amy-agent-my-profile__btn--outline"
							href="<?php echo esc_url( $tg_settings_url ); ?>"
						>
							<?php echo esc_html__( 'Open Settings → Telegram', 'amy-agent' ); ?>
						</a>
					</div>
					<p class="amy-agent-my-profile__telegram-deep" id="amy-my-profile-tg-deep" hidden></p>
				<?php endif; ?>
			</section>

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
	 * AJAX: save the current user's Task Service backup person (P3).
	 */
	public function ajax_save_task_backup() {
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

		$backup = isset( $_POST['backup_wp_user_id'] ) ? absint( $_POST['backup_wp_user_id'] ) : 0;
		if ( $backup > 0 ) {
			if ( (int) $backup === (int) $user_id ) {
				wp_send_json_error(
					array( 'message' => __( 'Choose someone else as your backup.', 'amy-agent' ) ),
					400
				);
			}
			$backup_user = get_userdata( $backup );
			if ( ! $backup_user || ! user_can( $backup_user, 'manage_options' ) ) {
				wp_send_json_error(
					array( 'message' => __( 'Backup must be a dashboard user.', 'amy-agent' ) ),
					400
				);
			}
			update_user_meta( $user_id, self::USER_TASK_BACKUP_META, $backup );
		} else {
			delete_user_meta( $user_id, self::USER_TASK_BACKUP_META );
		}

		$this->sync_dashboard_users_to_service();

		wp_send_json_success(
			array(
				'backup_wp_user_id' => $backup > 0 ? $backup : null,
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
	 * Analytics — ranked visitor / lead list backed by the Python analytics API.
	 */
	public function render_analytics_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap amy-agent-analytics" id="amy-agent-analytics">
			<header class="amy-agent-analytics__header">
				<h1 class="amy-agent-analytics__title"><?php echo esc_html__( 'Analytics', 'amy-agent' ); ?></h1>
				<p class="amy-agent-analytics__intro">
					<?php echo esc_html__( 'Who visited, what they did, and who almost became a client.', 'amy-agent' ); ?>
				</p>
				<span class="amy-agent-analytics__underline" aria-hidden="true"></span>
			</header>

			<p class="amy-agent-analytics__error" id="amy-agent-analytics-error" hidden role="alert"></p>

			<div class="amy-agent-analytics__toolbar">
				<div class="amy-agent-analytics__filters" role="tablist" aria-label="<?php echo esc_attr__( 'Filter by lead status', 'amy-agent' ); ?>">
					<button
						type="button"
						class="amy-agent-analytics__filter is-active"
						role="tab"
						aria-selected="true"
						data-amy-analytics-status=""
					>
						<?php echo esc_html__( 'All', 'amy-agent' ); ?>
					</button>
					<button type="button" class="amy-agent-analytics__filter" role="tab" aria-selected="false" data-amy-analytics-status="hot">
						<?php echo esc_html__( 'Hot', 'amy-agent' ); ?>
					</button>
					<button type="button" class="amy-agent-analytics__filter" role="tab" aria-selected="false" data-amy-analytics-status="warm">
						<?php echo esc_html__( 'Warm', 'amy-agent' ); ?>
					</button>
					<button type="button" class="amy-agent-analytics__filter" role="tab" aria-selected="false" data-amy-analytics-status="cold">
						<?php echo esc_html__( 'Cold', 'amy-agent' ); ?>
					</button>
				</div>
				<div class="amy-agent-analytics__filters" role="tablist" aria-label="<?php echo esc_attr__( 'Filter by email', 'amy-agent' ); ?>">
					<button
						type="button"
						class="amy-agent-analytics__filter is-active"
						role="tab"
						aria-selected="true"
						data-amy-analytics-has-email=""
					>
						<?php echo esc_html__( 'Any email', 'amy-agent' ); ?>
					</button>
					<button type="button" class="amy-agent-analytics__filter" role="tab" aria-selected="false" data-amy-analytics-has-email="1">
						<?php echo esc_html__( 'With email', 'amy-agent' ); ?>
					</button>
				</div>
			</div>

			<div class="amy-agent-analytics__list">
				<table class="amy-agent-analytics__table">
					<thead>
						<tr>
							<th><?php echo esc_html__( 'Visitor', 'amy-agent' ); ?></th>
							<th><?php echo esc_html__( 'Email', 'amy-agent' ); ?></th>
							<th><?php echo esc_html__( 'Phone', 'amy-agent' ); ?></th>
							<th><?php echo esc_html__( 'Location', 'amy-agent' ); ?></th>
							<th><?php echo esc_html__( 'Last seen', 'amy-agent' ); ?></th>
							<th><?php echo esc_html__( 'Signal', 'amy-agent' ); ?></th>
							<th><?php echo esc_html__( 'Status', 'amy-agent' ); ?></th>
						</tr>
					</thead>
					<tbody id="amy-agent-analytics-body"></tbody>
				</table>
				<p class="amy-agent-analytics__empty" id="amy-agent-analytics-empty" hidden>
					<?php echo esc_html__( 'No visitors yet.', 'amy-agent' ); ?>
				</p>
			</div>
		</div>
		<?php
	}

	/**
	 * SEO Tasks — type buttons, card grid, chat-style batch flow.
	 */
	public function render_seo_tasks_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$types = array(
			'page'     => array(
				'label' => __( 'Pages', 'amy-agent' ),
				'icon'  => 'dashicons-admin-page',
			),
			'post'     => array(
				'label' => __( 'Posts', 'amy-agent' ),
				'icon'  => 'dashicons-admin-post',
			),
			'category' => array(
				'label' => __( 'Categories', 'amy-agent' ),
				'icon'  => 'dashicons-category',
			),
			'tag'      => array(
				'label' => __( 'Tags', 'amy-agent' ),
				'icon'  => 'dashicons-tag',
			),
			'media'    => array(
				'label' => __( 'Media', 'amy-agent' ),
				'icon'  => 'dashicons-format-image',
			),
		);
		?>
		<div class="wrap amy-agent-seo" id="amy-agent-seo">
			<header class="amy-agent-seo__header">
				<h1 class="amy-agent-seo__title"><?php echo esc_html__( 'SEO Tasks', 'amy-agent' ); ?></h1>
				<p class="amy-agent-seo__intro">
					<?php echo esc_html__( 'Pick a content type. Amy shows every published item as a card. Nothing is written until you approve.', 'amy-agent' ); ?>
				</p>
				<span class="amy-agent-seo__underline" aria-hidden="true"></span>
			</header>

			<p class="amy-agent-seo__error" id="amy-agent-seo-error" hidden role="alert"></p>
			<p class="amy-agent-seo__notice" id="amy-agent-seo-notice" hidden></p>

			<nav class="amy-agent-seo__types" aria-label="<?php echo esc_attr__( 'Content type', 'amy-agent' ); ?>">
				<?php foreach ( $types as $type_key => $type ) : ?>
					<button
						type="button"
						class="amy-agent-seo__type"
						data-amy-seo-type="<?php echo esc_attr( $type_key ); ?>"
					>
						<span class="dashicons <?php echo esc_attr( $type['icon'] ); ?>" aria-hidden="true"></span>
						<span class="amy-agent-seo__type-label"><?php echo esc_html( $type['label'] ); ?></span>
						<span class="amy-agent-seo__type-count" data-amy-seo-type-count="<?php echo esc_attr( $type_key ); ?>">—</span>
					</button>
				<?php endforeach; ?>
			</nav>

			<p class="amy-agent-seo__empty-state" id="amy-agent-seo-empty">
				<?php echo esc_html__( 'Choose a content type to see every published item as a card. Nothing to type.', 'amy-agent' ); ?>
			</p>

			<section class="amy-agent-seo__workspace" id="amy-agent-seo-workspace" hidden>
				<div class="amy-agent-seo__prompt" id="amy-agent-seo-prompt">
					<div class="amy-agent-seo__log" id="amy-agent-seo-log" aria-live="polite"></div>
				</div>
				<p class="amy-agent-seo__selection" id="amy-agent-seo-selection" hidden></p>
				<div class="amy-agent-seo__grid" id="amy-agent-seo-grid"></div>
			</section>

			<section class="amy-agent-seo__panel" aria-labelledby="amy-agent-seo-history-title">
				<h2 class="amy-agent-seo__panel-title" id="amy-agent-seo-history-title"><?php echo esc_html__( 'Previous checks', 'amy-agent' ); ?></h2>
				<div class="amy-agent-seo__toolbar">
					<div class="amy-agent-seo__filters" role="tablist" aria-label="<?php echo esc_attr__( 'Filter by status', 'amy-agent' ); ?>">
						<button type="button" class="amy-agent-seo__filter is-active" role="tab" aria-selected="true" data-amy-seo-history-status=""><?php echo esc_html__( 'All statuses', 'amy-agent' ); ?></button>
						<button type="button" class="amy-agent-seo__filter" role="tab" aria-selected="false" data-amy-seo-history-status="pending_approval"><?php echo esc_html__( 'Pending', 'amy-agent' ); ?></button>
						<button type="button" class="amy-agent-seo__filter" role="tab" aria-selected="false" data-amy-seo-history-status="approved"><?php echo esc_html__( 'Approved', 'amy-agent' ); ?></button>
						<button type="button" class="amy-agent-seo__filter" role="tab" aria-selected="false" data-amy-seo-history-status="rejected"><?php echo esc_html__( 'Rejected', 'amy-agent' ); ?></button>
					</div>
					<div class="amy-agent-seo__filters" role="tablist" aria-label="<?php echo esc_attr__( 'Filter by verdict', 'amy-agent' ); ?>">
						<button type="button" class="amy-agent-seo__filter is-active" role="tab" aria-selected="true" data-amy-seo-history-verdict=""><?php echo esc_html__( 'All verdicts', 'amy-agent' ); ?></button>
						<button type="button" class="amy-agent-seo__filter" role="tab" aria-selected="false" data-amy-seo-history-verdict="red"><?php echo esc_html__( 'Needs work', 'amy-agent' ); ?></button>
						<button type="button" class="amy-agent-seo__filter" role="tab" aria-selected="false" data-amy-seo-history-verdict="orange"><?php echo esc_html__( 'Improvements', 'amy-agent' ); ?></button>
						<button type="button" class="amy-agent-seo__filter" role="tab" aria-selected="false" data-amy-seo-history-verdict="green"><?php echo esc_html__( 'Good', 'amy-agent' ); ?></button>
					</div>
				</div>
				<p class="amy-agent-seo__error" id="amy-agent-seo-history-error" hidden role="alert"></p>
				<div class="amy-agent-seo__list">
					<table class="amy-agent-seo__table">
						<thead>
							<tr>
								<th><?php echo esc_html__( 'Title', 'amy-agent' ); ?></th>
								<th><?php echo esc_html__( 'Target', 'amy-agent' ); ?></th>
								<th><?php echo esc_html__( 'Verdict', 'amy-agent' ); ?></th>
								<th><?php echo esc_html__( 'Status', 'amy-agent' ); ?></th>
								<th><?php echo esc_html__( 'Checked', 'amy-agent' ); ?></th>
							</tr>
						</thead>
						<tbody id="amy-agent-seo-history-body"></tbody>
					</table>
					<p class="amy-agent-seo__empty" id="amy-agent-seo-history-empty" hidden>
						<?php echo esc_html__( 'No checks yet. Pick a content type and run a check.', 'amy-agent' ); ?>
					</p>
				</div>
			</section>

			<div
				class="amy-agent-seo__modal"
				id="amy-agent-seo-modal"
				hidden
				role="dialog"
				aria-modal="true"
				aria-labelledby="amy-agent-seo-modal-title"
			>
				<div class="amy-agent-seo__modal-backdrop" data-amy-modal-close></div>
				<div class="amy-agent-seo__modal-dialog">
					<header class="amy-agent-seo__modal-header">
						<h2 id="amy-agent-seo-modal-title" class="amy-agent-seo__modal-title"></h2>
						<button
							type="button"
							class="amy-agent-seo__modal-close"
							data-amy-modal-close
							aria-label="<?php echo esc_attr__( 'Close', 'amy-agent' ); ?>"
						>
							<span class="dashicons dashicons-no-alt" aria-hidden="true"></span>
						</button>
					</header>
					<div class="amy-agent-seo__modal-body" id="amy-agent-seo-modal-body"></div>
				</div>
			</div>
		</div>
		<?php
	}

	/**
	 * Dashboard Chat — conversation list + thread shell (UI built in JS).
	 */
	public function render_chat_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap amy-agent-chat" id="amy-agent-chat-root">
			<h1 class="amy-agent-chat__title"><?php echo esc_html__( 'Chat', 'amy-agent' ); ?></h1>
		</div>
		<?php
	}

	/**
	 * Email Marketing — audience from Analytics; approve then explicit Send via wp_mail.
	 */
	public function render_email_marketing_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$from_email = $this->settings->get_marketing_from_email();
		$from_name  = $this->settings->get_marketing_from_name();
		?>
		<div class="wrap amy-agent-email" id="amy-agent-email-marketing">
			<header class="amy-agent-email__header">
				<h1 class="amy-agent-email__title"><?php echo esc_html__( 'Email Marketing', 'amy-agent' ); ?></h1>
				<p class="amy-agent-email__intro">
					<?php echo esc_html__( 'Audience from Amy Analytics visitor emails. Approve the draft, then click Send — nothing auto-sends.', 'amy-agent' ); ?>
				</p>
				<span class="amy-agent-email__underline" aria-hidden="true"></span>
			</header>

			<div class="amy-agent-email__from-banner" role="status">
				<p class="amy-agent-email__from-label"><?php echo esc_html__( 'From', 'amy-agent' ); ?></p>
				<p class="amy-agent-email__from-value" id="amy-agent-email-from-display">
					<?php
					echo esc_html(
						sprintf(
							/* translators: 1: display name, 2: email */
							__( '%1$s <%2$s>', 'amy-agent' ),
							$from_name,
							$from_email
						)
					);
					?>
				</p>
				<p class="amy-agent-email__from-note">
					<?php
					echo esc_html(
						sprintf(
							/* translators: %s: Marketing From email */
							__( '%s must be authorized in FluentSMTP on a verified domain. Each site sets Marketing From in Settings (own domain mailbox). Never personal Gmail or AgentMail.', 'amy-agent' ),
							$from_email
						)
					);
					?>
					<a href="<?php echo esc_url( $this->settings->settings_deep_link( 'general', 'general-from' ) ); ?>">
						<?php echo esc_html__( 'Change in Settings', 'amy-agent' ); ?>
					</a>
					·
					<?php if ( Amy_Settings::is_fluentsmtp_active() ) : ?>
						<a href="<?php echo esc_url( Amy_Settings::get_fluentsmtp_connections_url() ); ?>">
							<?php echo esc_html__( 'FluentSMTP → Connections', 'amy-agent' ); ?>
						</a>
					<?php else : ?>
						<a href="<?php echo esc_url( Amy_Settings::get_fluentsmtp_install_url() ); ?>">
							<?php echo esc_html__( 'Install FluentSMTP', 'amy-agent' ); ?>
						</a>
					<?php endif; ?>
				</p>
				<details class="amy-agent-email__from-playbook">
					<summary class="amy-agent-email__from-playbook-summary">
						<?php echo esc_html( Amy_Settings::get_fluentsmtp_playbook_title() ); ?>
					</summary>
					<div class="amy-agent-email__from-playbook-body">
						<p class="amy-agent-email__from-playbook-intro">
							<?php echo esc_html( Amy_Settings::get_fluentsmtp_playbook_intro() ); ?>
						</p>
						<?php Amy_Settings::render_fluentsmtp_buyer_playbook( Amy_Settings::DEFAULT_MARKETING_FROM_EMAIL ); ?>
					</div>
				</details>
			</div>

			<div class="amy-agent-email__notice" role="note">
				<p>
					<?php
					echo esc_html__(
						'Emails here are lead captures (Submit Idea / contact), not proven marketing opt-ins. Treat as lead-only until consent is confirmed. Sends never use personal Gmail or AgentMail.',
						'amy-agent'
					);
					?>
				</p>
				<p>
					<a href="<?php echo esc_url( admin_url( 'admin.php?page=' . self::ANALYTICS_PAGE_SLUG ) ); ?>">
						<?php echo esc_html__( 'Open Analytics', 'amy-agent' ); ?>
					</a>
				</p>
			</div>

			<p class="amy-agent-email__error" id="amy-agent-email-error" hidden role="alert"></p>
			<p class="amy-agent-email__status" id="amy-agent-email-status" hidden role="status"></p>

			<section class="amy-agent-email__analysis" aria-label="<?php echo esc_attr__( 'Audience analysis', 'amy-agent' ); ?>">
				<div class="amy-agent-email__stats">
					<button type="button" class="amy-agent-email__stat is-active" data-amy-email-stat="">
						<span class="amy-agent-email__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-email-alt"></span>
						</span>
						<span class="amy-agent-email__stat-copy">
							<span class="amy-agent-email__stat-label"><?php echo esc_html__( 'With email', 'amy-agent' ); ?></span>
							<span class="amy-agent-email__stat-value" id="amy-agent-email-stat-total">—</span>
						</span>
					</button>
					<button type="button" class="amy-agent-email__stat amy-agent-email__stat--hot" data-amy-email-stat="hot">
						<span class="amy-agent-email__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-warning"></span>
						</span>
						<span class="amy-agent-email__stat-copy">
							<span class="amy-agent-email__stat-label"><?php echo esc_html__( 'Hot', 'amy-agent' ); ?></span>
							<span class="amy-agent-email__stat-value" id="amy-agent-email-stat-hot">—</span>
						</span>
					</button>
					<button type="button" class="amy-agent-email__stat amy-agent-email__stat--warm" data-amy-email-stat="warm">
						<span class="amy-agent-email__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-visibility"></span>
						</span>
						<span class="amy-agent-email__stat-copy">
							<span class="amy-agent-email__stat-label"><?php echo esc_html__( 'Warm', 'amy-agent' ); ?></span>
							<span class="amy-agent-email__stat-value" id="amy-agent-email-stat-warm">—</span>
						</span>
					</button>
					<button type="button" class="amy-agent-email__stat amy-agent-email__stat--cold" data-amy-email-stat="cold">
						<span class="amy-agent-email__stat-icon" aria-hidden="true">
							<span class="dashicons dashicons-minus"></span>
						</span>
						<span class="amy-agent-email__stat-copy">
							<span class="amy-agent-email__stat-label"><?php echo esc_html__( 'Cold', 'amy-agent' ); ?></span>
							<span class="amy-agent-email__stat-value" id="amy-agent-email-stat-cold">—</span>
						</span>
					</button>
				</div>

				<div class="amy-agent-email__insight-row">
					<article class="amy-agent-email__panel" aria-labelledby="amy-agent-email-coverage-title">
						<h2 class="amy-agent-email__panel-title" id="amy-agent-email-coverage-title">
							<?php echo esc_html__( 'Email coverage', 'amy-agent' ); ?>
						</h2>
						<p class="amy-agent-email__coverage-value" id="amy-agent-email-coverage-value">—</p>
						<p class="amy-agent-email__panel-note" id="amy-agent-email-coverage-note">
							<?php echo esc_html__( 'Share of Analytics visitors with a captured email.', 'amy-agent' ); ?>
						</p>
						<div class="amy-agent-email__meter" aria-hidden="true">
							<span class="amy-agent-email__meter-fill" id="amy-agent-email-coverage-meter"></span>
						</div>
						<div class="amy-agent-email__chart amy-agent-email__chart--donut" id="amy-agent-email-chart-status" aria-hidden="true"></div>
						<p class="amy-agent-email__chart-caption" id="amy-agent-email-chart-status-caption">
							<?php echo esc_html__( 'Hot / Warm / Cold mix among email leads.', 'amy-agent' ); ?>
						</p>
					</article>

					<article class="amy-agent-email__panel" aria-labelledby="amy-agent-email-signals-title">
						<h2 class="amy-agent-email__panel-title" id="amy-agent-email-signals-title">
							<?php echo esc_html__( 'Recent signals', 'amy-agent' ); ?>
						</h2>
						<ul class="amy-agent-email__signals" id="amy-agent-email-signals"></ul>
						<p class="amy-agent-email__panel-note amy-agent-email__signals-empty" id="amy-agent-email-signals-empty" hidden>
							<?php echo esc_html__( 'No email captures yet — signals appear after Submit Idea or contact completion.', 'amy-agent' ); ?>
						</p>
					</article>
				</div>

				<div class="amy-agent-email__charts" aria-label="<?php echo esc_attr__( 'Audience charts', 'amy-agent' ); ?>">
					<article class="amy-agent-email__panel" aria-labelledby="amy-agent-email-chart-seen-title">
						<h2 class="amy-agent-email__panel-title" id="amy-agent-email-chart-seen-title">
							<?php echo esc_html__( 'Last seen', 'amy-agent' ); ?>
						</h2>
						<div class="amy-agent-email__bars" id="amy-agent-email-chart-seen" role="img" aria-label="<?php echo esc_attr__( 'Email leads by last-seen bucket', 'amy-agent' ); ?>"></div>
						<p class="amy-agent-email__panel-note">
							<?php echo esc_html__( 'How recently email leads were active.', 'amy-agent' ); ?>
						</p>
					</article>
					<article class="amy-agent-email__panel" aria-labelledby="amy-agent-email-chart-signal-title">
						<h2 class="amy-agent-email__panel-title" id="amy-agent-email-chart-signal-title">
							<?php echo esc_html__( 'Signal mix', 'amy-agent' ); ?>
						</h2>
						<div class="amy-agent-email__bars" id="amy-agent-email-chart-signal" role="img" aria-label="<?php echo esc_attr__( 'Top signals among email leads', 'amy-agent' ); ?>"></div>
						<p class="amy-agent-email__panel-note">
							<?php echo esc_html__( 'Top capture signals among email leads.', 'amy-agent' ); ?>
						</p>
					</article>
				</div>
			</section>

			<div class="amy-agent-email__selected-bar" id="amy-agent-email-selected-bar" hidden>
				<p class="amy-agent-email__selected-count" id="amy-agent-email-selected-count"></p>
				<div class="amy-agent-email__selected-actions">
					<button type="button" class="button" id="amy-agent-email-export">
						<?php echo esc_html__( 'Export selected CSV', 'amy-agent' ); ?>
					</button>
					<button type="button" class="button" id="amy-agent-email-clear-selection">
						<?php echo esc_html__( 'Clear selection', 'amy-agent' ); ?>
					</button>
				</div>
			</div>

			<div class="amy-agent-email__layout">
				<section class="amy-agent-email__audience" aria-labelledby="amy-agent-email-audience-title">
					<div class="amy-agent-email__audience-head">
						<h2 class="amy-agent-email__section-title" id="amy-agent-email-audience-title">
							<?php echo esc_html__( 'Audience', 'amy-agent' ); ?>
						</h2>
						<p class="amy-agent-email__count" id="amy-agent-email-count"></p>
					</div>

					<div class="amy-agent-email__toolbar">
						<label class="amy-agent-email__search">
							<span class="screen-reader-text"><?php echo esc_html__( 'Search emails', 'amy-agent' ); ?></span>
							<input type="search" id="amy-agent-email-search" placeholder="<?php echo esc_attr__( 'Search emails or visitors…', 'amy-agent' ); ?>" autocomplete="off" />
						</label>
						<button type="button" class="amy-agent-email__filter amy-agent-email__filter--followup" id="amy-agent-email-needs-followup" aria-pressed="false">
							<?php echo esc_html__( 'Needs follow-up', 'amy-agent' ); ?>
						</button>
					</div>

					<div class="amy-agent-email__filters" role="tablist" aria-label="<?php echo esc_attr__( 'Filter audience by status', 'amy-agent' ); ?>">
						<button type="button" class="amy-agent-email__filter is-active" role="tab" aria-selected="true" data-amy-email-status="">
							<?php echo esc_html__( 'All', 'amy-agent' ); ?>
						</button>
						<button type="button" class="amy-agent-email__filter" role="tab" aria-selected="false" data-amy-email-status="hot">
							<?php echo esc_html__( 'Hot', 'amy-agent' ); ?>
						</button>
						<button type="button" class="amy-agent-email__filter" role="tab" aria-selected="false" data-amy-email-status="warm">
							<?php echo esc_html__( 'Warm', 'amy-agent' ); ?>
						</button>
						<button type="button" class="amy-agent-email__filter" role="tab" aria-selected="false" data-amy-email-status="cold">
							<?php echo esc_html__( 'Cold', 'amy-agent' ); ?>
						</button>
					</div>

					<div class="amy-agent-email__list">
						<table class="amy-agent-email__table">
							<thead>
								<tr>
									<th scope="col" class="amy-agent-email__col-check">
										<label class="amy-agent-email__select-all">
											<input type="checkbox" id="amy-agent-email-select-all" />
											<span class="screen-reader-text"><?php echo esc_html__( 'Select all filtered', 'amy-agent' ); ?></span>
										</label>
									</th>
									<th scope="col"><?php echo esc_html__( 'Email', 'amy-agent' ); ?></th>
									<th scope="col"><?php echo esc_html__( 'Visitor', 'amy-agent' ); ?></th>
									<th scope="col"><?php echo esc_html__( 'Status', 'amy-agent' ); ?></th>
									<th scope="col"><?php echo esc_html__( 'Signal', 'amy-agent' ); ?></th>
									<th scope="col"><?php echo esc_html__( 'Last seen', 'amy-agent' ); ?></th>
								</tr>
							</thead>
							<tbody id="amy-agent-email-body"></tbody>
						</table>
						<p class="amy-agent-email__empty" id="amy-agent-email-empty" hidden>
							<?php echo esc_html__( 'No visitor emails yet. Captures appear after Submit Idea or contact form completion.', 'amy-agent' ); ?>
						</p>
					</div>
				</section>

				<section class="amy-agent-email__draft" aria-labelledby="amy-agent-email-draft-title">
					<h2 class="amy-agent-email__section-title" id="amy-agent-email-draft-title">
						<?php echo esc_html__( 'Draft follow-up', 'amy-agent' ); ?>
					</h2>
					<p class="amy-agent-email__draft-hint">
						<?php echo esc_html__( 'Select audience → write draft → Approve → then click Send. Send is never automatic.', 'amy-agent' ); ?>
					</p>

					<label class="amy-agent-email__field">
						<span><?php echo esc_html__( 'From', 'amy-agent' ); ?></span>
						<input type="text" id="amy-agent-email-from" readonly value="<?php echo esc_attr( $from_name . ' <' . $from_email . '>' ); ?>" />
					</label>
					<label class="amy-agent-email__field">
						<span id="amy-agent-email-to-label"><?php echo esc_html__( 'To (selected audience)', 'amy-agent' ); ?></span>
						<textarea id="amy-agent-email-to" rows="4" readonly placeholder="<?php echo esc_attr__( 'Select audience rows', 'amy-agent' ); ?>"></textarea>
					</label>
					<p class="amy-agent-email__to-meta" id="amy-agent-email-to-meta"></p>
					<label class="amy-agent-email__field">
						<span><?php echo esc_html__( 'Subject', 'amy-agent' ); ?></span>
						<input type="text" id="amy-agent-email-subject" maxlength="200" placeholder="<?php echo esc_attr__( 'Follow-up on your idea', 'amy-agent' ); ?>" />
					</label>
					<label class="amy-agent-email__field">
						<span><?php echo esc_html__( 'Message', 'amy-agent' ); ?></span>
						<textarea id="amy-agent-email-message" rows="10" placeholder="<?php echo esc_attr__( 'Write a personalized follow-up…', 'amy-agent' ); ?>"></textarea>
					</label>

					<div class="amy-agent-email__actions">
						<button type="button" class="button" id="amy-agent-email-clear">
							<?php echo esc_html__( 'Clear draft', 'amy-agent' ); ?>
						</button>
						<button type="button" class="button" id="amy-agent-email-approve">
							<?php echo esc_html__( 'Approve draft', 'amy-agent' ); ?>
						</button>
						<button type="button" class="button button-primary" id="amy-agent-email-send" disabled>
							<?php echo esc_html__( 'Send now', 'amy-agent' ); ?>
						</button>
					</div>
					<p class="amy-agent-email__send-hint" id="amy-agent-email-send-hint">
						<?php echo esc_html__( 'Send stays disabled until you approve the current draft.', 'amy-agent' ); ?>
					</p>
				</section>
			</div>

			<section class="amy-agent-email__history" aria-labelledby="amy-agent-email-history-title">
				<div class="amy-agent-email__history-head">
					<h2 class="amy-agent-email__section-title" id="amy-agent-email-history-title">
						<?php echo esc_html__( 'Send & reply history', 'amy-agent' ); ?>
					</h2>
					<button type="button" class="button" id="amy-agent-email-history-refresh">
						<?php echo esc_html__( 'Refresh', 'amy-agent' ); ?>
					</button>
				</div>
				<p class="amy-agent-email__history-note" id="amy-agent-email-history-note">
					<?php echo esc_html__( 'Durable log in the Amy service (same store as Chat). FluentSMTP is outbound-only — no AgentMail. Log inbound replies manually, or forward to the optional email-inbound webhook.', 'amy-agent' ); ?>
				</p>
				<p class="amy-agent-email__history-error" id="amy-agent-email-history-error" hidden role="alert"></p>
				<div class="amy-agent-email__history-layout">
					<div class="amy-agent-email__history-list" id="amy-agent-email-history-list" aria-live="polite"></div>
					<div class="amy-agent-email__history-thread" id="amy-agent-email-history-thread" hidden>
						<button type="button" class="button-link amy-agent-email__history-back" id="amy-agent-email-history-back">
							<?php echo esc_html__( 'Back to list', 'amy-agent' ); ?>
						</button>
						<div id="amy-agent-email-history-thread-meta"></div>
						<ol class="amy-agent-email__history-messages" id="amy-agent-email-history-messages"></ol>
						<div class="amy-agent-email__history-compose">
							<label class="amy-agent-email__field">
								<span><?php echo esc_html__( 'Add reply note', 'amy-agent' ); ?></span>
								<textarea id="amy-agent-email-history-note-body" rows="4" placeholder="<?php echo esc_attr__( 'Paste or summarize their reply, or leave an internal note…', 'amy-agent' ); ?>"></textarea>
							</label>
							<label class="amy-agent-email__history-inbound-flag">
								<input type="checkbox" id="amy-agent-email-history-as-inbound" value="1" />
								<?php echo esc_html__( 'Treat as inbound reply (not internal note)', 'amy-agent' ); ?>
							</label>
							<div class="amy-agent-email__history-compose-actions">
								<button type="button" class="button button-primary" id="amy-agent-email-history-save-note">
									<?php echo esc_html__( 'Save', 'amy-agent' ); ?>
								</button>
								<button type="button" class="button" id="amy-agent-email-history-optout">
									<?php echo esc_html__( 'Opt out', 'amy-agent' ); ?>
								</button>
							</div>
						</div>
					</div>
				</div>
				<p class="amy-agent-email__history-empty" id="amy-agent-email-history-empty" hidden>
					<?php echo esc_html__( 'No sends yet. After you Send via FluentSMTP, threads appear here.', 'amy-agent' ); ?>
				</p>
			</section>
		</div>
		<?php
	}
}
