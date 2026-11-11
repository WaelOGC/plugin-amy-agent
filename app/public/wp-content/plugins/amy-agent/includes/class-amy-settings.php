<?php
/**
 * Amy Agent admin settings page.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers Settings API options and renders Amy → Settings.
 */
class Amy_Settings {

	const PAGE_SLUG = 'amy-settings';

	const OPTION_ENABLED              = 'amy_agent_enabled';
	const OPTION_SERVICE_URL          = 'amy_agent_service_url';
	const OPTION_SHARED_SECRET        = 'amy_agent_shared_secret';
	const OPTION_AI_PROVIDER          = 'amy_agent_ai_provider';
	const OPTION_AI_API_KEY           = 'amy_agent_ai_api_key';
	const OPTION_AI_MODEL             = 'amy_agent_ai_model';
	const OPTION_AVATAR_URL           = 'amy_agent_avatar_url';
	const OPTION_MARKETING_FROM_EMAIL = 'amy_agent_marketing_from_email';
	const OPTION_MARKETING_FROM_NAME  = 'amy_agent_marketing_from_name';

	const OPTION_TELEGRAM_ENABLED = 'amy_agent_telegram_enabled';
	const OPTION_TELEGRAM_TOKEN   = 'amy_agent_telegram_bot_token';
	const OPTION_TELEGRAM_ADMINS  = 'amy_agent_telegram_admins';

	/** Site default task owner when creator has no Telegram or is gone (P3). */
	const OPTION_TASK_DEFAULT_OWNER = 'amy_agent_task_default_owner_wp_user_id';

	/**
	 * Plugin / OGC NewFinity site default when Settings From is empty.
	 * Each install may override with its own domain mailbox in Settings.
	 */
	const DEFAULT_MARKETING_FROM_EMAIL = 'hello@ogcnewfinity.com';

	/**
	 * Default marketing From display name (overridable per site in Settings).
	 */
	const DEFAULT_MARKETING_FROM_NAME = 'OGC NewFinity';

	/**
	 * FluentSMTP plugin basename (wp-admin → Plugins).
	 */
	const FLUENTSMTP_PLUGIN_FILE = 'fluent-smtp/fluent-smtp.php';

	/**
	 * FluentSMTP wp-admin page slug (Connections SPA).
	 */
	const FLUENTSMTP_PAGE_SLUG = 'fluent-mail';

	/**
	 * Hook suffix returned by add_submenu_page() for Settings.
	 *
	 * @var string|false|null
	 */
	private $page_hook;

	/**
	 * Allowed AI provider slugs (must match Python registry).
	 *
	 * @return array<string, string> slug => label
	 */
	public static function providers() {
		return array(
			'gemini'    => 'Google Gemini',
			'openai'    => 'OpenAI',
			'anthropic' => 'Anthropic Claude',
			'deepseek'  => 'DeepSeek',
		);
	}

	/**
	 * Free-webmail / AgentMail hosts rejected for marketing From.
	 *
	 * @return string[]
	 */
	public static function blocked_marketing_from_hosts() {
		return array(
			'gmail.com',
			'googlemail.com',
			'agentmail.to',
			'yahoo.com',
			'outlook.com',
			'hotmail.com',
			'live.com',
			'icloud.com',
		);
	}

	/**
	 * Store the real Settings screen hook (from add_submenu_page return value).
	 *
	 * @param string|false $hook Hook suffix from WordPress.
	 */
	public function set_page_hook( $hook ) {
		$this->page_hook = $hook;
	}

	/**
	 * Wire admin hooks.
	 */
	public function register() {
		add_action( 'admin_init', array( $this, 'register_settings' ) );
		add_action( 'admin_init', array( $this, 'normalize_enabled_checkbox_post' ), 0 );
		add_action( 'admin_init', array( $this, 'normalize_telegram_enabled_checkbox_post' ), 0 );
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_assets' ) );
		add_filter( 'plugin_action_links_' . plugin_basename( AMY_AGENT_FILE ), array( $this, 'add_settings_link' ) );
	}

	/**
	 * Ensure Enable Amy posts as plain "0" or "1" (Settings API + checkbox).
	 *
	 * Duplicate hidden+checkbox fields can arrive as an array and get sanitized to "0".
	 */
	public function normalize_enabled_checkbox_post() {
		if ( ! isset( $_POST['option_page'] ) || 'amy_agent_settings' !== $_POST['option_page'] ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing
			return;
		}
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$raw = isset( $_POST[ self::OPTION_ENABLED ] ) ? wp_unslash( $_POST[ self::OPTION_ENABLED ] ) : null; // phpcs:ignore WordPress.Security.NonceVerification.Missing

		if ( is_array( $raw ) ) {
			$_POST[ self::OPTION_ENABLED ] = in_array( '1', array_map( 'strval', $raw ), true ) ? '1' : '0';
			return;
		}

		// Checkbox-only: missing from POST means unchecked.
		if ( null === $raw ) {
			$_POST[ self::OPTION_ENABLED ] = '0';
			return;
		}

		$_POST[ self::OPTION_ENABLED ] = ( '1' === (string) $raw ) ? '1' : '0';
	}

	/**
	 * Ensure Telegram enable checkbox posts as "0" or "1".
	 */
	public function normalize_telegram_enabled_checkbox_post() {
		if ( ! isset( $_POST['option_page'] ) || 'amy_agent_settings' !== $_POST['option_page'] ) { // phpcs:ignore WordPress.Security.NonceVerification.Missing
			return;
		}
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$raw = isset( $_POST[ self::OPTION_TELEGRAM_ENABLED ] ) ? wp_unslash( $_POST[ self::OPTION_TELEGRAM_ENABLED ] ) : null; // phpcs:ignore WordPress.Security.NonceVerification.Missing

		if ( is_array( $raw ) ) {
			$_POST[ self::OPTION_TELEGRAM_ENABLED ] = in_array( '1', array_map( 'strval', $raw ), true ) ? '1' : '0';
			return;
		}

		if ( null === $raw ) {
			$_POST[ self::OPTION_TELEGRAM_ENABLED ] = '0';
			return;
		}

		$_POST[ self::OPTION_TELEGRAM_ENABLED ] = ( '1' === (string) $raw ) ? '1' : '0';
	}

	/**
	 * Add a Settings link on the Plugins list row.
	 *
	 * @param array $links Existing action links.
	 * @return array
	 */
	public function add_settings_link( $links ) {
		$url = admin_url( 'admin.php?page=' . self::PAGE_SLUG );
		array_unshift(
			$links,
			sprintf(
				'<a href="%s">%s</a>',
				esc_url( $url ),
				esc_html__( 'Settings', 'amy-agent' )
			)
		);
		return $links;
	}

	/**
	 * Register Settings API fields.
	 */
	public function register_settings() {
		register_setting(
			'amy_agent_settings',
			self::OPTION_ENABLED,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_checkbox' ),
				'default'           => '0',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_SERVICE_URL,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_service_url' ),
				'default'           => 'http://127.0.0.1:8765',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_SHARED_SECRET,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_shared_secret' ),
				'default'           => '',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_AI_PROVIDER,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_provider' ),
				'default'           => 'gemini',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_AI_API_KEY,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_api_key' ),
				'default'           => '',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_AI_MODEL,
			array(
				'type'              => 'string',
				'sanitize_callback' => 'sanitize_text_field',
				'default'           => '',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_AVATAR_URL,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_avatar_url' ),
				'default'           => '',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_MARKETING_FROM_EMAIL,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_marketing_from_email' ),
				'default'           => self::DEFAULT_MARKETING_FROM_EMAIL,
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_MARKETING_FROM_NAME,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_marketing_from_name' ),
				'default'           => self::DEFAULT_MARKETING_FROM_NAME,
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_TELEGRAM_ENABLED,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_checkbox' ),
				'default'           => '0',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_TELEGRAM_TOKEN,
			array(
				'type'              => 'string',
				'sanitize_callback' => array( $this, 'sanitize_telegram_token' ),
				'default'           => '',
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_TELEGRAM_ADMINS,
			array(
				'type'              => 'array',
				'sanitize_callback' => array( $this, 'sanitize_telegram_admins' ),
				'default'           => array(),
			)
		);

		register_setting(
			'amy_agent_settings',
			self::OPTION_TASK_DEFAULT_OWNER,
			array(
				'type'              => 'integer',
				'sanitize_callback' => array( $this, 'sanitize_task_default_owner' ),
				'default'           => 0,
			)
		);
	}

	/**
	 * Enqueue admin assets on the settings page only.
	 *
	 * @param string $hook_suffix Current admin page hook.
	 */
	public function enqueue_assets( $hook_suffix ) {
		if ( ! $this->page_hook || $this->page_hook !== $hook_suffix ) {
			return;
		}

		wp_enqueue_style(
			'amy-agent-admin-settings-fonts',
			'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap',
			array(),
			null
		);

		wp_enqueue_style(
			'amy-agent-admin-settings',
			AMY_AGENT_URL . 'admin/css/admin-settings.css',
			array( 'amy-agent-admin-settings-fonts', 'dashicons' ),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-agent-admin-settings',
			AMY_AGENT_URL . 'admin/js/admin-settings.js',
			array(),
			AMY_AGENT_VERSION,
			true
		);

		wp_localize_script(
			'amy-agent-admin-settings',
			'amyAgentSettings',
			array(
				'healthUrl'         => esc_url_raw( rest_url( 'amy-agent/v1/health' ) ),
				'restNonce'         => wp_create_nonce( 'wp_rest' ),
				'ajaxUrl'           => admin_url( 'admin-ajax.php' ),
				'telegramNonce'     => wp_create_nonce( Amy_Telegram::NONCE_ACTION ),
				'isHttps'           => is_ssl(),
				'blockedFromHosts'  => self::blocked_marketing_from_hosts(),
				'defaultFromEmail'  => self::DEFAULT_MARKETING_FROM_EMAIL,
				'i18n'              => array(
					'fromBlocked'       => __( 'Marketing From cannot be personal Gmail, AgentMail, or free webmail. Use your own domain mailbox authorized in FluentSMTP.', 'amy-agent' ),
					'healthChecking'    => __( 'Checking connection…', 'amy-agent' ),
					'healthOk'          => __( 'Python service reachable.', 'amy-agent' ),
					'healthUnreachable' => __( 'Python service unreachable (check URL, secret, and Dokploy).', 'amy-agent' ),
					'healthFail'        => __( 'Health check failed. Could not reach WordPress REST.', 'amy-agent' ),
					'needUrlSecret'     => __( 'Set service URL and shared secret first.', 'amy-agent' ),
					'enabledOn'         => __( 'Enable Amy is on.', 'amy-agent' ),
					'enabledOff'        => __( 'Enable Amy is off — widget and Submit Idea stay hidden.', 'amy-agent' ),
					'providerLabel'     => __( 'Provider:', 'amy-agent' ),
					'keySaved'          => __( 'key saved', 'amy-agent' ),
					'noApiKey'          => __( 'AI API key not set.', 'amy-agent' ),
					'pluginVersion'     => __( 'Plugin', 'amy-agent' ),
					'tgSaveFirst'       => __( 'Bot token is missing. Amy → Settings → Telegram → paste token from BotFather → Save settings.', 'amy-agent' ),
					'tgConnecting'      => __( 'Connecting…', 'amy-agent' ),
					'tgDisconnecting'   => __( 'Disconnecting…', 'amy-agent' ),
					'tgTesting'         => __( 'Sending test messages…', 'amy-agent' ),
					'tgStatusLoading'   => __( 'Loading Telegram status…', 'amy-agent' ),
					'tgConnected'       => __( 'Connected', 'amy-agent' ),
					'tgNotConnected'    => __( 'Not connected', 'amy-agent' ),
					'tgError'           => __( 'Error', 'amy-agent' ),
					'tgHttpsRequired'   => __( 'Telegram webhooks require HTTPS. Ask your host for HTTPS, then reload Amy → Settings → Telegram.', 'amy-agent' ),
					'tgConnectFailed'   => __( 'Connect failed. Check token, Enable Telegram Admin Bot, HTTPS, then Connect again under Settings → Telegram.', 'amy-agent' ),
					'tgTestFailed'      => __( 'Test failed. Enable the bot, save a BotFather token, add at least one numeric admin ID, then Send test message under Settings → Telegram.', 'amy-agent' ),
					'tgStatusFailed'    => __( 'Status request failed. Save settings, then reload Amy → Settings → Telegram.', 'amy-agent' ),
					'tgMaxAdmins'       => __( 'Maximum 10 admins.', 'amy-agent' ),
				),
			)
		);
	}

	/**
	 * @param mixed $value Raw checkbox value.
	 * @return string '1' or '0'
	 */
	public function sanitize_checkbox( $value ) {
		if ( is_array( $value ) ) {
			return in_array( '1', array_map( 'strval', $value ), true ) ? '1' : '0';
		}
		return ( '1' === (string) $value || true === $value || 1 === $value ) ? '1' : '0';
	}

	/**
	 * @param mixed $value Raw URL.
	 * @return string
	 */
	public function sanitize_service_url( $value ) {
		$url = esc_url_raw( trim( (string) $value ) );
		return $url ? untrailingslashit( $url ) : '';
	}

	/**
	 * @param mixed $value Provider slug.
	 * @return string
	 */
	public function sanitize_provider( $value ) {
		$slug = sanitize_key( (string) $value );
		$allowed = array_keys( self::providers() );
		return in_array( $slug, $allowed, true ) ? $slug : 'gemini';
	}

	/**
	 * Keep existing secret if the password field is submitted empty.
	 *
	 * @param mixed $value Submitted secret.
	 * @return string
	 */
	public function sanitize_shared_secret( $value ) {
		$value = is_string( $value ) ? trim( $value ) : '';
		if ( '' === $value ) {
			$existing = get_option( self::OPTION_SHARED_SECRET, '' );
			return is_string( $existing ) ? $existing : '';
		}
		return sanitize_text_field( $value );
	}

	/**
	 * Keep existing key if the password field is submitted empty (browser UX).
	 *
	 * @param mixed $value Submitted key.
	 * @return string
	 */
	public function sanitize_api_key( $value ) {
		$value = is_string( $value ) ? trim( $value ) : '';
		if ( '' === $value ) {
			$existing = get_option( self::OPTION_AI_API_KEY, '' );
			return is_string( $existing ) ? $existing : '';
		}
		return sanitize_text_field( $value );
	}

	/**
	 * @param mixed $value Raw avatar URL.
	 * @return string Empty string clears custom avatar (plugin default is used).
	 */
	public function sanitize_avatar_url( $value ) {
		$url = esc_url_raw( trim( (string) $value ) );
		return $url ? $url : '';
	}

	/**
	 * Whether an address is allowed as marketing From (domain mailbox only).
	 *
	 * @param string $email Candidate address.
	 * @return bool
	 */
	public static function is_allowed_marketing_from_email( $email ) {
		$email = strtolower( trim( (string) $email ) );
		if ( '' === $email || ! is_email( $email ) ) {
			return false;
		}
		$host = (string) substr( strrchr( $email, '@' ), 1 );
		return ! in_array( $host, self::blocked_marketing_from_hosts(), true );
	}

	/**
	 * Marketing From email — per-site override; empty falls back to plugin default
	 * (hello@ogcnewfinity.com). Rejects personal Gmail / AgentMail / free webmail.
	 *
	 * @param mixed $value Submitted email.
	 * @return string
	 */
	public function sanitize_marketing_from_email( $value ) {
		$email = sanitize_email( trim( (string) $value ) );
		if ( '' === $email || ! is_email( $email ) ) {
			return self::DEFAULT_MARKETING_FROM_EMAIL;
		}
		if ( ! self::is_allowed_marketing_from_email( $email ) ) {
			$previous = sanitize_email( trim( (string) get_option( self::OPTION_MARKETING_FROM_EMAIL, '' ) ) );
			$kept     = self::is_allowed_marketing_from_email( $previous )
				? strtolower( $previous )
				: self::DEFAULT_MARKETING_FROM_EMAIL;
			add_settings_error(
				'amy_agent_settings',
				'amy_marketing_from_blocked',
				sprintf(
					/* translators: %s: email kept after rejecting blocked From */
					__( 'Marketing From cannot be personal Gmail, AgentMail, or free webmail. Kept %s. Set your own domain mailbox and authorize it in FluentSMTP.', 'amy-agent' ),
					$kept
				),
				'error'
			);
			return $kept;
		}
		return strtolower( $email );
	}

	/**
	 * @param mixed $value Display name.
	 * @return string
	 */
	public function sanitize_marketing_from_name( $value ) {
		$name = sanitize_text_field( trim( (string) $value ) );
		$name = str_replace( array( '<', '>' ), '', $name );
		return '' !== $name ? $name : self::DEFAULT_MARKETING_FROM_NAME;
	}

	/**
	 * Telegram bot token — blank keeps existing; invalid format keeps old value.
	 *
	 * @param mixed $value Submitted token.
	 * @return string
	 */
	public function sanitize_telegram_token( $value ) {
		$value = is_string( $value ) ? trim( $value ) : '';
		if ( '' === $value ) {
			$existing = get_option( self::OPTION_TELEGRAM_TOKEN, '' );
			return is_string( $existing ) ? $existing : '';
		}
		if ( ! preg_match( '/^\d{6,12}:[A-Za-z0-9_-]{30,}$/', $value ) ) {
			add_settings_error(
				'amy_agent_settings',
				'amy_telegram_token_invalid',
				__( 'Telegram bot token format is invalid. The previous saved token was kept.', 'amy-agent' ),
				'error'
			);
			$existing = get_option( self::OPTION_TELEGRAM_TOKEN, '' );
			return is_string( $existing ) ? $existing : '';
		}
		return sanitize_text_field( $value );
	}

	/**
	 * Sanitize Telegram admin whitelist (max 10 unique rows).
	 *
	 * @param mixed $value Raw rows from POST.
	 * @return array<int, array{telegram_id:int,label:string,wp_user_id:int}>
	 */
	public function sanitize_telegram_admins( $value ) {
		if ( ! is_array( $value ) ) {
			return array();
		}

		$clean   = array();
		$seen_ids = array();

		foreach ( $value as $row ) {
			if ( ! is_array( $row ) ) {
				continue;
			}

			$telegram_raw = isset( $row['telegram_id'] ) ? $row['telegram_id'] : '';
			if ( ! is_numeric( $telegram_raw ) ) {
				continue;
			}
			$telegram_id = (int) $telegram_raw;
			if ( $telegram_id <= 0 ) {
				continue;
			}
			if ( isset( $seen_ids[ $telegram_id ] ) ) {
				continue;
			}

			$wp_user_id = isset( $row['wp_user_id'] ) ? (int) $row['wp_user_id'] : 0;
			if ( $wp_user_id <= 0 || ! user_can( $wp_user_id, 'manage_options' ) ) {
				continue;
			}

			$label = isset( $row['label'] ) ? sanitize_text_field( (string) $row['label'] ) : '';
			if ( strlen( $label ) > 60 ) {
				$label = substr( $label, 0, 60 );
			}

			$seen_ids[ $telegram_id ] = true;
			$clean[] = array(
				'telegram_id' => $telegram_id,
				'label'       => $label,
				'wp_user_id'  => $wp_user_id,
			);

			if ( count( $clean ) >= 10 ) {
				break;
			}
		}

		return $clean;
	}

	/**
	 * @return bool
	 */
	public function is_telegram_enabled() {
		return '1' === (string) get_option( self::OPTION_TELEGRAM_ENABLED, '0' );
	}

	/**
	 * @return string
	 */
	public function get_telegram_token() {
		return (string) get_option( self::OPTION_TELEGRAM_TOKEN, '' );
	}

	/**
	 * @return array<int, array{telegram_id:int,label:string,wp_user_id:int}>
	 */
	public function get_telegram_admins() {
		$rows = get_option( self::OPTION_TELEGRAM_ADMINS, array() );
		return is_array( $rows ) ? $rows : array();
	}

	/**
	 * Resolved marketing From email (always a usable address).
	 * Prefers the site’s Settings value; empty/blocked → plugin default hello@.
	 *
	 * @return string
	 */
	public function get_marketing_from_email() {
		$email = sanitize_email( trim( (string) get_option( self::OPTION_MARKETING_FROM_EMAIL, '' ) ) );
		if ( self::is_allowed_marketing_from_email( $email ) ) {
			return strtolower( $email );
		}
		return self::DEFAULT_MARKETING_FROM_EMAIL;
	}

	/**
	 * Resolved marketing From display name.
	 *
	 * @return string
	 */
	public function get_marketing_from_name() {
		$name = sanitize_text_field( trim( (string) get_option( self::OPTION_MARKETING_FROM_NAME, '' ) ) );
		$name = str_replace( array( '<', '>' ), '', $name );
		return '' !== $name ? $name : self::DEFAULT_MARKETING_FROM_NAME;
	}

	/**
	 * Whether FluentSMTP is active (required transport for Marketing From).
	 *
	 * @return bool
	 */
	public static function is_fluentsmtp_active() {
		if ( defined( 'FLUENTMAIL' ) || class_exists( '\FluentMail\App\App', false ) ) {
			return true;
		}
		if ( ! function_exists( 'is_plugin_active' ) ) {
			require_once ABSPATH . 'wp-admin/includes/plugin.php';
		}
		return function_exists( 'is_plugin_active' ) && is_plugin_active( self::FLUENTSMTP_PLUGIN_FILE );
	}

	/**
	 * FluentSMTP → Connections admin URL (SPA hash).
	 *
	 * @return string
	 */
	public static function get_fluentsmtp_connections_url() {
		return admin_url( 'admin.php?page=' . self::FLUENTSMTP_PAGE_SLUG . '#/connections' );
	}

	/**
	 * Plugin install search URL for FluentSMTP when inactive.
	 *
	 * @return string
	 */
	public static function get_fluentsmtp_install_url() {
		return admin_url( 'plugin-install.php?s=FluentSMTP&tab=search&type=term' );
	}

	/**
	 * Compact buyer playbook: mailbox → FluentSMTP → SPF/DKIM → Amy From → test.
	 * hello@ is only an example default for this site — never AgentMail.
	 *
	 * @param string $example_email Example From shown in step 1 (usually plugin default).
	 */
	public static function render_fluentsmtp_buyer_playbook( $example_email = '' ) {
		$example_email = sanitize_email( (string) $example_email );
		if ( '' === $example_email ) {
			$example_email = self::DEFAULT_MARKETING_FROM_EMAIL;
		}
		$active = self::is_fluentsmtp_active();
		?>
		<ol class="amy-agent-settings__steps">
			<li>
				<?php
				echo esc_html(
					sprintf(
						/* translators: %s: example domain mailbox (e.g. hello@ogcnewfinity.com) */
						__( 'Mailbox: create a mailbox on your domain (example on this site: %s).', 'amy-agent' ),
						$example_email
					)
				);
				?>
			</li>
			<li>
				<?php echo esc_html__( 'FluentSMTP: authorize send as that mailbox under FluentSMTP → Connections (SMTP or provider OAuth).', 'amy-agent' ); ?>
			</li>
			<li>
				<?php echo esc_html__( 'DNS: ensure SPF and DKIM for the domain (and DMARC when ready). Use Force From Email only if you understand it overrides other plugins.', 'amy-agent' ); ?>
			</li>
			<li>
				<?php echo esc_html__( 'Amy: Settings → General → Marketing From email / name = that mailbox → Save settings.', 'amy-agent' ); ?>
			</li>
			<li>
				<?php echo esc_html__( 'Prove it: send FluentSMTP’s own test email From your mailbox, then optionally Amy Email Marketing → Approve → Send to a personal test address only.', 'amy-agent' ); ?>
			</li>
		</ol>
		<p class="amy-agent-settings__hint">
			<?php if ( $active ) : ?>
				<?php echo esc_html__( 'Where:', 'amy-agent' ); ?>
				<a href="<?php echo esc_url( self::get_fluentsmtp_connections_url() ); ?>">
					<?php echo esc_html__( 'FluentSMTP → Connections', 'amy-agent' ); ?>
				</a>
				<?php echo esc_html__( '— authorize this mailbox, then use FluentSMTP’s test email (do not reinvent a separate Amy test).', 'amy-agent' ); ?>
			<?php else : ?>
				<strong><?php echo esc_html__( 'FluentSMTP is not active.', 'amy-agent' ); ?></strong>
				<?php echo esc_html__( 'Install and activate FluentSMTP, then open FluentSMTP → Connections.', 'amy-agent' ); ?>
				<a href="<?php echo esc_url( self::get_fluentsmtp_install_url() ); ?>">
					<?php echo esc_html__( 'Install FluentSMTP', 'amy-agent' ); ?>
				</a>
				·
				<a href="<?php echo esc_url( admin_url( 'plugins.php' ) ); ?>">
					<?php echo esc_html__( 'Plugins', 'amy-agent' ); ?>
				</a>
			<?php endif; ?>
		</p>
		<?php
	}

	/**
	 * Sanitize site default task owner WP user id.
	 *
	 * @param mixed $value Raw option.
	 * @return int
	 */
	public function sanitize_task_default_owner( $value ) {
		$uid = absint( $value );
		if ( $uid < 1 ) {
			return 0;
		}
		$user = get_userdata( $uid );
		if ( ! $user || ! user_can( $user, 'manage_options' ) ) {
			return 0;
		}
		return $uid;
	}

	/**
	 * Site default owner for Task Service expiry when creator is unreachable.
	 *
	 * @return int 0 when unset.
	 */
	public function get_task_default_owner_wp_user_id() {
		return absint( get_option( self::OPTION_TASK_DEFAULT_OWNER, 0 ) );
	}

	/**
	 * Bundled default avatar (plugin file).
	 *
	 * @return string
	 */
	public function get_default_avatar_url() {
		return AMY_AGENT_URL . 'public/images/amy-avatar-v1.jpg';
	}

	/**
	 * Active avatar URL for the front-end widget (custom option or default).
	 *
	 * @return string
	 */
	public function get_avatar_url() {
		$custom = trim( (string) get_option( self::OPTION_AVATAR_URL, '' ) );
		if ( '' !== $custom ) {
			return esc_url_raw( $custom );
		}
		return esc_url_raw( $this->get_default_avatar_url() );
	}

	/**
	 * Stored custom avatar URL only (empty means “use default”).
	 *
	 * @return string
	 */
	public function get_custom_avatar_url() {
		return trim( (string) get_option( self::OPTION_AVATAR_URL, '' ) );
	}

	/**
	 * Whether Amy is enabled in settings (raw flag only).
	 *
	 * @return bool
	 */
	public function is_enabled() {
		return '1' === (string) get_option( self::OPTION_ENABLED, '0' );
	}

	/**
	 * Service URL + shared secret look configured enough for theme activation.
	 *
	 * @return bool
	 */
	public function is_service_configured() {
		$url    = $this->get_service_url();
		$secret = $this->get_shared_secret();
		return '' !== $url && '' !== $secret;
	}

	/**
	 * Enable flag AND service URL/secret present — used by theme bridge.
	 *
	 * @return bool
	 */
	public function is_ready() {
		return $this->is_enabled() && $this->is_service_configured();
	}

	/**
	 * @return string
	 */
	public function get_service_url() {
		return (string) get_option( self::OPTION_SERVICE_URL, '' );
	}

	/**
	 * @return string
	 */
	public function get_shared_secret() {
		return (string) get_option( self::OPTION_SHARED_SECRET, '' );
	}

	/**
	 * @return string
	 */
	public function get_ai_provider() {
		return $this->sanitize_provider( get_option( self::OPTION_AI_PROVIDER, 'gemini' ) );
	}

	/**
	 * @return string
	 */
	public function get_ai_api_key() {
		return (string) get_option( self::OPTION_AI_API_KEY, '' );
	}

	/**
	 * @return string|null Empty model returns null for the API payload.
	 */
	public function get_ai_model() {
		$model = trim( (string) get_option( self::OPTION_AI_MODEL, '' ) );
		// Retired Gemini model IDs — fall back to Python provider default.
		if ( 'gemini-2.0-flash' === $model ) {
			$model = '';
		}
		return '' === $model ? null : $model;
	}

	/**
	 * AI config fragment for Python requests (provider + key from WP Options).
	 *
	 * @return array{provider: string, api_key: string, model: string|null}
	 */
	public function get_ai_config() {
		return array(
			'provider' => $this->get_ai_provider(),
			'api_key'  => $this->get_ai_api_key(),
			'model'    => $this->get_ai_model(),
		);
	}

	/**
	 * Mask a secret for admin display (keep last 4 chars).
	 *
	 * @param string $value Raw secret.
	 * @return string
	 */
	private function mask_secret( $value ) {
		$value  = (string) $value;
		$length = strlen( $value );
		if ( $length <= 4 ) {
			return str_repeat( '•', max( 4, $length ) );
		}
		return str_repeat( '•', min( 12, $length - 4 ) ) . substr( $value, -4 );
	}

	/**
	 * Admin URL into a Settings tab + optional fragment (deep-link targets).
	 *
	 * @param string $tab      general|connection|telegram.
	 * @param string $fragment Hash without leading # (e.g. general-from).
	 * @return string
	 */
	public function settings_deep_link( $tab = 'general', $fragment = '' ) {
		$tab = sanitize_key( (string) $tab );
		if ( ! in_array( $tab, array( 'general', 'connection', 'telegram' ), true ) ) {
			$tab = 'general';
		}
		$url = admin_url( 'admin.php?page=' . self::PAGE_SLUG . '&tab=' . $tab );
		$fragment = sanitize_title( (string) $fragment );
		if ( '' !== $fragment ) {
			$url .= '#' . $fragment;
		}
		return $url;
	}

	/**
	 * Readiness summary for the Settings header banner.
	 *
	 * Core Ready still means Enable Amy + service URL + shared secret (widget/Submit Idea).
	 * Missing list also covers Telegram (alerts), optional Marketing From, and optional AI key.
	 *
	 * @return array{state:string,badge:string,title:string,text:string,missing:array<int,array{label:string,href:string}>}
	 */
	private function get_readiness_summary() {
		$enabled    = $this->is_enabled();
		$configured = $this->is_service_configured();
		$ready      = $this->is_ready();
		$missing    = array();

		if ( ! $enabled ) {
			$missing[] = array(
				'label'    => __( 'Enable Amy is off', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'general', 'enable-amy' ),
				'optional' => false,
			);
		}
		if ( '' === $this->get_service_url() ) {
			$missing[] = array(
				'label'    => __( 'Python service URL is empty', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'connection', 'connection' ),
				'optional' => false,
			);
		}
		if ( '' === $this->get_shared_secret() ) {
			$missing[] = array(
				'label'    => __( 'Shared secret is empty', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'connection', 'connection' ),
				'optional' => false,
			);
		}

		$tg_enabled  = $this->is_telegram_enabled();
		$tg_token    = '' !== $this->get_telegram_token();
		$tg_webhook  = Amy_Telegram::is_webhook_connected();
		$tg_complete = $tg_enabled && $tg_token && $tg_webhook;

		if ( ! $tg_enabled ) {
			$missing[] = array(
				'label'    => __( 'Telegram Admin Bot is disabled', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'telegram', 'telegram' ),
				'optional' => false,
			);
		}
		if ( ! $tg_token ) {
			$missing[] = array(
				'label'    => __( 'Telegram bot token is missing', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'telegram', 'telegram' ),
				'optional' => false,
			);
		}
		if ( $tg_token && ! $tg_webhook ) {
			$missing[] = array(
				'label'    => __( 'Telegram webhook is not connected', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'telegram', 'telegram' ),
				'optional' => false,
			);
		}

		$from_raw = sanitize_email( trim( (string) get_option( self::OPTION_MARKETING_FROM_EMAIL, '' ) ) );
		if ( '' === $from_raw ) {
			$missing[] = array(
				'label'    => __( 'Marketing From not set (optional — using plugin default)', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'general', 'general-from' ),
				'optional' => true,
			);
		}

		if ( '' === $this->get_ai_api_key() ) {
			$missing[] = array(
				'label'    => __( 'AI API key not set (optional — needed for Chat)', 'amy-agent' ),
				'href'     => $this->settings_deep_link( 'connection', 'ai-key' ),
				'optional' => true,
			);
		}

		if ( $ready && $tg_complete ) {
			$optional_only = array();
			foreach ( $missing as $item ) {
				if ( ! empty( $item['optional'] ) ) {
					$optional_only[] = $item;
				}
			}
			return array(
				'state'   => 'ready',
				'badge'   => __( 'Ready', 'amy-agent' ),
				'title'   => __( 'Amy is ready on the site', 'amy-agent' ),
				'text'    => __( 'Enable Amy, service connection, and Telegram bot are set. Optional items below still help Email Marketing and Chat.', 'amy-agent' ),
				'missing' => $optional_only,
			);
		}

		if ( $ready && ! $tg_complete ) {
			return array(
				'state'   => 'warn',
				'badge'   => __( 'Ready · Alerts incomplete', 'amy-agent' ),
				'title'   => __( 'Widget can load — Telegram alerts need setup', 'amy-agent' ),
				'text'    => __( 'Enable Amy and the Python service are set. Finish Telegram (token → Enable → Connect) for Task Service alerts, then link chat id under My Profile.', 'amy-agent' ),
				'missing' => $missing,
			);
		}

		if ( $configured && ! $enabled ) {
			return array(
				'state'   => 'warn',
				'badge'   => __( 'Configured · Off', 'amy-agent' ),
				'title'   => __( 'Service is configured, Amy is disabled', 'amy-agent' ),
				'text'    => __( 'Turn on Enable Amy (General tab) and save to show the floating widget and Submit Idea.', 'amy-agent' ),
				'missing' => $missing,
			);
		}

		return array(
			'state'   => 'off',
			'badge'   => __( 'Not ready', 'amy-agent' ),
			'title'   => __( 'Amy is not ready yet', 'amy-agent' ),
			'text'    => __( 'Enable Amy plus a service URL and shared secret are required. Fix each item below — links jump to the right Settings card.', 'amy-agent' ),
			'missing' => $missing,
		);
	}

	/**
	 * Settings page markup (tabbed dark Amy admin theme).
	 */
	public function render_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$readiness  = $this->get_readiness_summary();
		$has_secret       = '' !== $this->get_shared_secret();
		$has_key          = '' !== $this->get_ai_api_key();
		$has_tg_token     = '' !== $this->get_telegram_token();
		$model            = (string) get_option( self::OPTION_AI_MODEL, '' );
		$telegram_admins  = $this->get_telegram_admins();
		$wp_admin_users   = get_users(
			array(
				'capability' => 'manage_options',
				'orderby'    => 'display_name',
				'order'      => 'ASC',
			)
		);
		$active_tab = isset( $_GET['tab'] ) ? sanitize_key( wp_unslash( $_GET['tab'] ) ) : 'general'; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		if ( ! in_array( $active_tab, array( 'general', 'connection', 'telegram' ), true ) ) {
			$active_tab = 'general';
		}
		?>
		<div class="wrap amy-agent-settings" id="amy-agent-settings">
			<header class="amy-agent-settings__header">
				<h1 class="amy-agent-settings__title"><?php echo esc_html__( 'Settings', 'amy-agent' ); ?></h1>
				<p class="amy-agent-settings__intro">
					<?php echo esc_html__( 'Site-wide Amy switches and connection plumbing. Tool-specific options stay on their own pages (Email Marketing, SEO Tasks, etc.). Avatar lives on Brand & Avatar.', 'amy-agent' ); ?>
				</p>
				<span class="amy-agent-settings__underline" aria-hidden="true"></span>
			</header>

			<?php settings_errors( 'amy_agent_settings' ); ?>

			<div
				class="amy-agent-settings__readiness amy-agent-settings__readiness--<?php echo esc_attr( $readiness['state'] ); ?>"
				role="status"
			>
				<span class="amy-agent-settings__readiness-badge"><?php echo esc_html( $readiness['badge'] ); ?></span>
				<div class="amy-agent-settings__readiness-copy">
					<p class="amy-agent-settings__readiness-title"><?php echo esc_html( $readiness['title'] ); ?></p>
					<p class="amy-agent-settings__readiness-text"><?php echo esc_html( $readiness['text'] ); ?></p>
					<?php if ( ! empty( $readiness['missing'] ) ) : ?>
						<ul class="amy-agent-settings__readiness-list">
							<?php foreach ( $readiness['missing'] as $item ) : ?>
								<?php
								$label = is_array( $item ) ? (string) ( $item['label'] ?? '' ) : (string) $item;
								$href  = is_array( $item ) ? (string) ( $item['href'] ?? '' ) : '';
								if ( '' === $label ) {
									continue;
								}
								?>
								<li>
									<?php if ( '' !== $href ) : ?>
										<a class="amy-agent-settings__readiness-link" href="<?php echo esc_url( $href ); ?>">
											<?php echo esc_html( $label ); ?>
										</a>
									<?php else : ?>
										<?php echo esc_html( $label ); ?>
									<?php endif; ?>
								</li>
							<?php endforeach; ?>
						</ul>
					<?php endif; ?>
				</div>
			</div>

			<p class="amy-agent-settings__controls-note">
				<strong><?php echo esc_html__( 'What Enable Amy controls:', 'amy-agent' ); ?></strong>
				<?php echo esc_html__( ' the floating site chat widget and Amy Submit Idea. Analytics tracking can still run when the service URL + secret are set. Brand avatar is edited under Brand & Avatar — not here.', 'amy-agent' ); ?>
			</p>

			<div class="amy-agent-settings__tabs" role="tablist" aria-label="<?php echo esc_attr__( 'Settings tabs', 'amy-agent' ); ?>">
				<button
					type="button"
					class="amy-agent-settings__tab<?php echo 'general' === $active_tab ? ' is-active' : ''; ?>"
					role="tab"
					id="amy-settings-tab-general"
					data-amy-settings-tab="general"
					aria-controls="amy-settings-panel-general"
					aria-selected="<?php echo 'general' === $active_tab ? 'true' : 'false'; ?>"
				>
					<?php echo esc_html__( 'General', 'amy-agent' ); ?>
				</button>
				<button
					type="button"
					class="amy-agent-settings__tab<?php echo 'connection' === $active_tab ? ' is-active' : ''; ?>"
					role="tab"
					id="amy-settings-tab-connection"
					data-amy-settings-tab="connection"
					aria-controls="amy-settings-panel-connection"
					aria-selected="<?php echo 'connection' === $active_tab ? 'true' : 'false'; ?>"
				>
					<?php echo esc_html__( 'Connection', 'amy-agent' ); ?>
				</button>
				<button
					type="button"
					class="amy-agent-settings__tab<?php echo 'telegram' === $active_tab ? ' is-active' : ''; ?>"
					role="tab"
					id="amy-settings-tab-telegram"
					data-amy-settings-tab="telegram"
					aria-controls="amy-settings-panel-telegram"
					aria-selected="<?php echo 'telegram' === $active_tab ? 'true' : 'false'; ?>"
				>
					<?php echo esc_html__( 'Telegram', 'amy-agent' ); ?>
				</button>
			</div>

			<form method="post" action="options.php" class="amy-agent-settings__form">
				<?php settings_fields( 'amy_agent_settings' ); ?>

				<div
					class="amy-agent-settings__panel"
					id="amy-settings-panel-general"
					role="tabpanel"
					aria-labelledby="amy-settings-tab-general"
					<?php echo 'general' === $active_tab ? '' : 'hidden'; ?>
				>
					<h2 class="amy-agent-settings__panel-title"><?php echo esc_html__( 'General', 'amy-agent' ); ?></h2>
					<p class="amy-agent-settings__panel-intro">
						<?php echo esc_html__( 'Rarely touched site switches and the marketing From identity used by Email Marketing sends.', 'amy-agent' ); ?>
					</p>

					<div class="amy-agent-settings__card" id="enable-amy">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Site presence', 'amy-agent' ); ?></h3>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__toggle" for="amy_agent_enabled">
								<input
									type="checkbox"
									id="amy_agent_enabled"
									name="<?php echo esc_attr( self::OPTION_ENABLED ); ?>"
									value="1"
									<?php checked( $this->is_enabled(), true ); ?>
								/>
								<span class="amy-agent-settings__toggle-copy">
									<strong><?php echo esc_html__( 'Enable Amy', 'amy-agent' ); ?></strong>
									<span><?php echo esc_html__( 'Show the floating chat widget and Amy Submit Idea when the service URL + shared secret are also set.', 'amy-agent' ); ?></span>
								</span>
							</label>
							<p class="amy-agent-settings__hint">
								<?php echo esc_html__( 'Uncheck and save to hide Amy on the site again. Connection settings stay saved.', 'amy-agent' ); ?>
							</p>
						</div>
					</div>

					<div class="amy-agent-settings__card" id="general-from">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Email Marketing From', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
							<?php echo esc_html__( 'Each WordPress site configures its own Marketing From. Buyers: use a mailbox on your domain and authorize that address in FluentSMTP (SPF/DKIM). Sends go through wp_mail → FluentSMTP — never personal Gmail, AgentMail (@agentmail.to), or free webmail.', 'amy-agent' ); ?>
						</p>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_marketing_from_email">
								<?php echo esc_html__( 'Marketing From email', 'amy-agent' ); ?>
							</label>
							<input
								type="email"
								id="amy_agent_marketing_from_email"
								name="<?php echo esc_attr( self::OPTION_MARKETING_FROM_EMAIL ); ?>"
								value="<?php echo esc_attr( $this->get_marketing_from_email() ); ?>"
								placeholder="<?php echo esc_attr( self::DEFAULT_MARKETING_FROM_EMAIL ); ?>"
								autocomplete="off"
							/>
							<p class="amy-agent-settings__field-error" id="amy-settings-from-error" hidden></p>
							<p class="amy-agent-settings__hint">
								<?php
								echo esc_html(
									sprintf(
										/* translators: %s: plugin default From email */
										__( 'Leave empty to use the plugin default (%s) for this OGC NewFinity install. Other sites should set their own domain mailbox here and authorize it in FluentSMTP (SPF/DKIM).', 'amy-agent' ),
										self::DEFAULT_MARKETING_FROM_EMAIL
									)
								);
								?>
							</p>
						</div>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_marketing_from_name">
								<?php echo esc_html__( 'Marketing From name', 'amy-agent' ); ?>
							</label>
							<input
								type="text"
								id="amy_agent_marketing_from_name"
								name="<?php echo esc_attr( self::OPTION_MARKETING_FROM_NAME ); ?>"
								value="<?php echo esc_attr( $this->get_marketing_from_name() ); ?>"
								placeholder="<?php echo esc_attr( self::DEFAULT_MARKETING_FROM_NAME ); ?>"
								autocomplete="organization"
							/>
							<p class="amy-agent-settings__hint">
								<?php
								echo esc_html(
									sprintf(
										/* translators: %s: example display name */
										__( 'Display name recipients see (example: %s).', 'amy-agent' ),
										self::DEFAULT_MARKETING_FROM_NAME
									)
								);
								?>
							</p>
						</div>
					</div>

					<div class="amy-agent-settings__card amy-agent-settings__card--help amy-agent-settings__card--fluentsmtp" id="general-from-playbook">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Instructions — set your Marketing From', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
							<?php echo esc_html__( 'Per-site From via FluentSMTP. hello@ is only an example default for this install — use your own domain mailbox. Never personal Gmail or AgentMail.', 'amy-agent' ); ?>
						</p>
						<?php self::render_fluentsmtp_buyer_playbook( self::DEFAULT_MARKETING_FROM_EMAIL ); ?>
					</div>

					<?php
					$default_owner = $this->get_task_default_owner_wp_user_id();
					$owner_users   = get_users(
						array(
							'capability' => 'manage_options',
							'orderby'    => 'display_name',
							'order'      => 'ASC',
						)
					);
					?>
					<div class="amy-agent-settings__card">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Task Service owner', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
							<?php echo esc_html__( 'On timeout, Amy notifies the task creator first. If that creator has no Telegram link or is gone, escalate to this site default owner (then their designated backup).', 'amy-agent' ); ?>
						</p>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_task_default_owner">
								<?php echo esc_html__( 'Site default owner', 'amy-agent' ); ?>
							</label>
							<select
								id="amy_agent_task_default_owner"
								name="<?php echo esc_attr( self::OPTION_TASK_DEFAULT_OWNER ); ?>"
							>
								<option value="0"><?php echo esc_html__( '— Not set —', 'amy-agent' ); ?></option>
								<?php foreach ( $owner_users as $owner_user ) : ?>
									<option value="<?php echo esc_attr( (string) (int) $owner_user->ID ); ?>" <?php selected( $default_owner, (int) $owner_user->ID ); ?>>
										<?php echo esc_html( $owner_user->display_name ? $owner_user->display_name : $owner_user->user_login ); ?>
									</option>
								<?php endforeach; ?>
							</select>
							<p class="amy-agent-settings__hint">
								<?php echo esc_html__( 'Typically Abdulla / the business owner. Each person can also designate a personal backup under Amy → My Profile.', 'amy-agent' ); ?>
							</p>
						</div>
					</div>
				</div>

				<div
					class="amy-agent-settings__panel"
					id="amy-settings-panel-connection"
					role="tabpanel"
					aria-labelledby="amy-settings-tab-connection"
					<?php echo 'connection' === $active_tab ? '' : 'hidden'; ?>
				>
					<h2 class="amy-agent-settings__panel-title"><?php echo esc_html__( 'Connection', 'amy-agent' ); ?></h2>
					<p class="amy-agent-settings__panel-intro">
						<?php echo esc_html__( 'Python service URL, shared secret, and the AI provider used for chat and tools. Keys stay in the WordPress database and are never printed back into the page.', 'amy-agent' ); ?>
					</p>

					<div class="amy-agent-settings__card" id="connection">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Python service', 'amy-agent' ); ?></h3>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_service_url">
								<?php echo esc_html__( 'Python service URL', 'amy-agent' ); ?>
							</label>
							<input
								type="url"
								id="amy_agent_service_url"
								name="<?php echo esc_attr( self::OPTION_SERVICE_URL ); ?>"
								value="<?php echo esc_attr( $this->get_service_url() ); ?>"
								placeholder="http://127.0.0.1:8765"
								autocomplete="off"
							/>
							<p class="amy-agent-settings__hint">
								<?php echo esc_html__( 'Base URL of amy-agent-service (no trailing slash). On Local, try 127.0.0.1 or host.docker.internal.', 'amy-agent' ); ?>
							</p>
						</div>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_shared_secret">
								<?php echo esc_html__( 'Shared secret', 'amy-agent' ); ?>
							</label>
							<input
								type="password"
								id="amy_agent_shared_secret"
								name="<?php echo esc_attr( self::OPTION_SHARED_SECRET ); ?>"
								value=""
								autocomplete="new-password"
								placeholder="<?php echo $has_secret ? esc_attr__( 'Enter a new secret to replace the saved one', 'amy-agent' ) : esc_attr__( 'Enter a shared secret', 'amy-agent' ); ?>"
							/>
							<?php if ( $has_secret ) : ?>
								<p class="amy-agent-settings__saved">
									<?php
									echo esc_html(
										sprintf(
											/* translators: %s: masked secret ending */
											__( 'Shared secret is stored in the database (%s). Leave blank when saving to keep it.', 'amy-agent' ),
											$this->mask_secret( $this->get_shared_secret() )
										)
									);
									?>
								</p>
							<?php else : ?>
								<p class="amy-agent-settings__hint">
									<?php echo esc_html__( 'Must match AMY_SHARED_SECRET in the Python service .env.', 'amy-agent' ); ?>
								</p>
							<?php endif; ?>
						</div>

						<div class="amy-agent-settings__health">
							<button type="button" class="amy-agent-settings__btn amy-agent-settings__btn--ghost" id="amy-settings-health-check">
								<?php echo esc_html__( 'Check connection', 'amy-agent' ); ?>
							</button>
							<p class="amy-agent-settings__health-status" id="amy-settings-health-status" hidden role="status"></p>
						</div>
						<p class="amy-agent-settings__hint">
							<?php echo esc_html__( 'Calls WordPress /wp-json/amy-agent/v1/health, which probes the Python service /v1/health with the saved secret.', 'amy-agent' ); ?>
						</p>
					</div>

					<div class="amy-agent-settings__card" id="ai-key">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'AI provider', 'amy-agent' ); ?></h3>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_ai_provider">
								<?php echo esc_html__( 'Provider', 'amy-agent' ); ?>
							</label>
							<select id="amy_agent_ai_provider" name="<?php echo esc_attr( self::OPTION_AI_PROVIDER ); ?>">
								<?php foreach ( self::providers() as $slug => $label ) : ?>
									<option value="<?php echo esc_attr( $slug ); ?>" <?php selected( $this->get_ai_provider(), $slug ); ?>>
										<?php echo esc_html( $label ); ?>
									</option>
								<?php endforeach; ?>
							</select>
						</div>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_ai_api_key">
								<?php echo esc_html__( 'API key', 'amy-agent' ); ?>
							</label>
							<input
								type="password"
								id="amy_agent_ai_api_key"
								name="<?php echo esc_attr( self::OPTION_AI_API_KEY ); ?>"
								value=""
								autocomplete="new-password"
								placeholder="<?php echo $has_key ? esc_attr__( 'Enter a new key to replace the saved one', 'amy-agent' ) : esc_attr__( 'Paste your API key', 'amy-agent' ); ?>"
							/>
							<?php if ( $has_key ) : ?>
								<p class="amy-agent-settings__saved">
									<?php
									echo esc_html(
										sprintf(
											/* translators: %s: masked API key ending */
											__( 'API key is stored in the database (%s). Leave blank when saving to keep it.', 'amy-agent' ),
											$this->mask_secret( $this->get_ai_api_key() )
										)
									);
									?>
								</p>
							<?php else : ?>
								<p class="amy-agent-settings__hint">
									<?php echo esc_html__( 'Stored via the Options API. The field stays empty after save on purpose so the key is never shown in the page HTML.', 'amy-agent' ); ?>
								</p>
							<?php endif; ?>
						</div>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_ai_model">
								<?php echo esc_html__( 'Model (optional)', 'amy-agent' ); ?>
							</label>
							<input
								type="text"
								id="amy_agent_ai_model"
								name="<?php echo esc_attr( self::OPTION_AI_MODEL ); ?>"
								value="<?php echo esc_attr( $model ); ?>"
								placeholder="<?php echo esc_attr__( 'Provider default if empty', 'amy-agent' ); ?>"
								autocomplete="off"
							/>
						</div>
					</div>
				</div>

				<div
					class="amy-agent-settings__panel"
					id="amy-settings-panel-telegram"
					role="tabpanel"
					aria-labelledby="amy-settings-tab-telegram"
					<?php echo 'telegram' === $active_tab ? '' : 'hidden'; ?>
				>
					<h2 class="amy-agent-settings__panel-title"><?php echo esc_html__( 'Telegram', 'amy-agent' ); ?></h2>
					<p class="amy-agent-settings__panel-intro">
						<?php echo esc_html__( 'Private Admin Bot (one bot for Dashboard Chat and Task Service alerts). Paste a BotFather token, whitelist admins for Amy chat, then Connect the HTTPS webhook. Assignees link their chat id from Amy → My Profile → Telegram task alerts. Token and webhook secret stay in WordPress only — Task Service outbound reuses this bot (no second stack).', 'amy-agent' ); ?>
					</p>

					<?php if ( ! is_ssl() ) : ?>
						<div class="amy-agent-settings__notice amy-agent-settings__notice--warn" role="status">
							<?php echo esc_html__( 'This site is not using HTTPS. Telegram only accepts HTTPS webhooks — ask your host for HTTPS, then reload Amy → Settings → Telegram.', 'amy-agent' ); ?>
						</div>
					<?php endif; ?>

					<div class="amy-agent-settings__card amy-agent-settings__card--botfather">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Create your Telegram bot', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
							<?php echo esc_html__( 'Telegram does not allow minting bot tokens via API. Each buyer or team creates their own bot in BotFather, then pastes the token here.', 'amy-agent' ); ?>
						</p>
						<p class="amy-agent-settings__botfather-cta">
							<a
								class="amy-agent-settings__btn amy-agent-settings__btn--accent amy-agent-settings__external-link"
								href="https://t.me/BotFather"
								target="_blank"
								rel="noopener noreferrer"
							>
								<?php echo esc_html__( 'Open BotFather', 'amy-agent' ); ?>
								<span class="dashicons dashicons-external" aria-hidden="true"></span>
								<span class="screen-reader-text"><?php echo esc_html__( '(opens in a new tab)', 'amy-agent' ); ?></span>
							</a>
						</p>
						<ol class="amy-agent-settings__steps">
							<li><?php echo esc_html__( 'Open BotFather in Telegram (link above).', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'Send /newbot and follow the prompts.', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'Choose a display name, then a username ending in bot.', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'Copy the bot token BotFather sends you.', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'Paste the token into Bot token below, then Save settings.', 'amy-agent' ); ?></li>
						</ol>
						<p class="amy-agent-settings__hint">
							<?php echo esc_html__( 'Official guide:', 'amy-agent' ); ?>
							<a
								class="amy-agent-settings__external-link"
								href="https://core.telegram.org/bots/tutorial"
								target="_blank"
								rel="noopener noreferrer"
							>
								<?php echo esc_html__( 'Telegram Bots tutorial (BotFather + token)', 'amy-agent' ); ?>
								<span class="dashicons dashicons-external" aria-hidden="true"></span>
								<span class="screen-reader-text"><?php echo esc_html__( '(opens in a new tab)', 'amy-agent' ); ?></span>
							</a>
						</p>
					</div>

					<div class="amy-agent-settings__card" id="telegram">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Bot connection', 'amy-agent' ); ?></h3>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__toggle" for="amy_agent_telegram_enabled">
								<input
									type="checkbox"
									id="amy_agent_telegram_enabled"
									name="<?php echo esc_attr( self::OPTION_TELEGRAM_ENABLED ); ?>"
									value="1"
									<?php checked( $this->is_telegram_enabled(), true ); ?>
								/>
								<span class="amy-agent-settings__toggle-copy">
									<strong><?php echo esc_html__( 'Enable Telegram Admin Bot', 'amy-agent' ); ?></strong>
									<span><?php echo esc_html__( 'When off, the webhook acknowledges updates but does not reply.', 'amy-agent' ); ?></span>
								</span>
							</label>
						</div>
						<div class="amy-agent-settings__field">
							<label class="amy-agent-settings__field-label" for="amy_agent_telegram_bot_token">
								<?php echo esc_html__( 'Bot token', 'amy-agent' ); ?>
							</label>
							<input
								type="password"
								id="amy_agent_telegram_bot_token"
								name="<?php echo esc_attr( self::OPTION_TELEGRAM_TOKEN ); ?>"
								value=""
								autocomplete="new-password"
								data-amy-tg-token-input
								placeholder="<?php echo $has_tg_token ? esc_attr__( 'Enter a new token to replace the saved one', 'amy-agent' ) : esc_attr__( 'Paste token from @BotFather', 'amy-agent' ); ?>"
							/>
							<?php if ( $has_tg_token ) : ?>
								<p class="amy-agent-settings__saved">
									<?php
									echo esc_html(
										sprintf(
											/* translators: %s: masked token ending */
											__( 'Token is stored in the database (%s). Leave blank when saving to keep it.', 'amy-agent' ),
											$this->mask_secret( $this->get_telegram_token() )
										)
									);
									?>
								</p>
							<?php else : ?>
								<p class="amy-agent-settings__hint">
									<?php echo esc_html__( 'Paste the token from BotFather (steps above). Never share this token.', 'amy-agent' ); ?>
								</p>
							<?php endif; ?>
						</div>

						<p class="amy-agent-settings__telegram-status" id="amy-settings-telegram-status" role="status" aria-live="polite"></p>

						<div
							class="amy-agent-settings__tg-next-steps"
							id="amy-settings-telegram-next-steps"
							hidden
						>
							<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
								<?php echo esc_html__( 'Not connected — next steps:', 'amy-agent' ); ?>
							</p>
							<ol class="amy-agent-settings__steps">
								<li><?php echo esc_html__( 'Paste BotFather token → Save settings.', 'amy-agent' ); ?></li>
								<li><?php echo esc_html__( 'Enable Telegram Admin Bot.', 'amy-agent' ); ?></li>
								<li><?php echo esc_html__( 'Site must be HTTPS.', 'amy-agent' ); ?></li>
								<li><?php echo esc_html__( 'Click Connect.', 'amy-agent' ); ?></li>
								<li><?php echo esc_html__( 'Add at least one numeric admin ID → Save → Send test message.', 'amy-agent' ); ?></li>
							</ol>
						</div>

						<div class="amy-agent-settings__telegram-actions">
							<button
								type="button"
								class="amy-agent-settings__btn amy-agent-settings__btn--primary"
								id="amy-settings-telegram-connect"
								<?php disabled( ! is_ssl() ); ?>
							>
								<?php echo esc_html__( 'Connect', 'amy-agent' ); ?>
							</button>
							<button type="button" class="amy-agent-settings__btn amy-agent-settings__btn--ghost" id="amy-settings-telegram-disconnect">
								<?php echo esc_html__( 'Disconnect', 'amy-agent' ); ?>
							</button>
							<button type="button" class="amy-agent-settings__btn amy-agent-settings__btn--ghost" id="amy-settings-telegram-test">
								<?php echo esc_html__( 'Send test message', 'amy-agent' ); ?>
							</button>
						</div>
						<p class="amy-agent-settings__telegram-feedback" id="amy-settings-telegram-feedback" hidden role="status"></p>
					</div>

					<div class="amy-agent-settings__card">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Allowed admins (whitelist)', 'amy-agent' ); ?></h3>
						<div class="amy-agent-settings__table-wrap">
							<table class="amy-agent-settings__table" id="amy-telegram-admins-table">
								<thead>
									<tr>
										<th scope="col"><?php echo esc_html__( 'Telegram user ID', 'amy-agent' ); ?></th>
										<th scope="col"><?php echo esc_html__( 'Label', 'amy-agent' ); ?></th>
										<th scope="col"><?php echo esc_html__( 'Linked WordPress user', 'amy-agent' ); ?></th>
										<th scope="col"><span class="screen-reader-text"><?php echo esc_html__( 'Remove', 'amy-agent' ); ?></span></th>
									</tr>
								</thead>
								<tbody id="amy-telegram-admins-body">
									<?php
									$index = 0;
									foreach ( $telegram_admins as $row ) :
										if ( ! is_array( $row ) ) {
											continue;
										}
										?>
										<tr class="amy-agent-settings__admin-row" data-amy-admin-row>
											<td>
												<input
													type="number"
													min="1"
													step="1"
													name="<?php echo esc_attr( 'amy_agent_telegram_admins[' . $index . '][telegram_id]' ); ?>"
													value="<?php echo esc_attr( (string) ( $row['telegram_id'] ?? '' ) ); ?>"
													class="amy-agent-settings__table-input"
												/>
											</td>
											<td>
												<input
													type="text"
													maxlength="60"
													name="<?php echo esc_attr( 'amy_agent_telegram_admins[' . $index . '][label]' ); ?>"
													value="<?php echo esc_attr( (string) ( $row['label'] ?? '' ) ); ?>"
													class="amy-agent-settings__table-input"
												/>
											</td>
											<td>
												<select name="<?php echo esc_attr( 'amy_agent_telegram_admins[' . $index . '][wp_user_id]' ); ?>" class="amy-agent-settings__table-select">
													<option value=""><?php echo esc_html__( '— Select —', 'amy-agent' ); ?></option>
													<?php foreach ( $wp_admin_users as $user ) : ?>
														<option value="<?php echo esc_attr( (string) $user->ID ); ?>" <?php selected( (int) ( $row['wp_user_id'] ?? 0 ), (int) $user->ID ); ?>>
															<?php echo esc_html( $user->display_name . ' (' . $user->user_email . ')' ); ?>
														</option>
													<?php endforeach; ?>
												</select>
											</td>
											<td>
												<button type="button" class="amy-agent-settings__btn amy-agent-settings__btn--ghost amy-agent-settings__btn--small" data-amy-remove-admin>
													<?php echo esc_html__( 'Remove', 'amy-agent' ); ?>
												</button>
											</td>
										</tr>
										<?php
										++$index;
									endforeach;
									?>
								</tbody>
							</table>
						</div>
						<p>
							<button type="button" class="amy-agent-settings__btn amy-agent-settings__btn--ghost" id="amy-telegram-add-admin">
								<?php echo esc_html__( 'Add admin', 'amy-agent' ); ?>
							</button>
						</p>
						<template id="amy-telegram-admin-row-template">
							<tr class="amy-agent-settings__admin-row" data-amy-admin-row>
								<td>
									<input type="number" min="1" step="1" data-field="telegram_id" class="amy-agent-settings__table-input" />
								</td>
								<td>
									<input type="text" maxlength="60" data-field="label" class="amy-agent-settings__table-input" />
								</td>
								<td>
									<select data-field="wp_user_id" class="amy-agent-settings__table-select">
										<option value=""><?php echo esc_html__( '— Select —', 'amy-agent' ); ?></option>
										<?php foreach ( $wp_admin_users as $user ) : ?>
											<option value="<?php echo esc_attr( (string) $user->ID ); ?>">
												<?php echo esc_html( $user->display_name . ' (' . $user->user_email . ')' ); ?>
											</option>
										<?php endforeach; ?>
									</select>
								</td>
								<td>
									<button type="button" class="amy-agent-settings__btn amy-agent-settings__btn--ghost amy-agent-settings__btn--small" data-amy-remove-admin>
										<?php echo esc_html__( 'Remove', 'amy-agent' ); ?>
									</button>
								</td>
							</tr>
						</template>
					</div>

					<div class="amy-agent-settings__card amy-agent-settings__card--help">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'How to find your Telegram user ID', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
							<?php echo esc_html__( 'Whitelist uses a numeric Telegram user ID (digits only). For private 1:1 chats, chat id equals user id.', 'amy-agent' ); ?>
						</p>
						<ol class="amy-agent-settings__steps">
							<li><?php echo esc_html__( 'Message your Amy bot in Telegram (open it from the bot username after Connect, or search the username BotFather gave you).', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'If you are not on the whitelist yet, the bot replies with your numeric Telegram ID — copy those digits into Allowed admins.', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'If you are already whitelisted, send /whoami — the bot replies with your Telegram ID.', 'amy-agent' ); ?></li>
							<li><?php echo esc_html__( 'Paste the number into Telegram user ID, choose the linked WordPress admin, Save settings, then press Connect (HTTPS required).', 'amy-agent' ); ?></li>
							<li>
								<?php echo esc_html__( 'Fallback: message', 'amy-agent' ); ?>
								<a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">@userinfobot</a>
								<?php echo esc_html__( 'or', 'amy-agent' ); ?>
								<a href="https://t.me/RawDataBot" target="_blank" rel="noopener noreferrer">@RawDataBot</a>
								<?php echo esc_html__( 'and copy the numeric Id — only if steps 2–3 are unavailable.', 'amy-agent' ); ?>
							</li>
						</ol>
					</div>
				</div>

				<div class="amy-agent-settings__actions">
					<?php
					submit_button(
						__( 'Save settings', 'amy-agent' ),
						'primary amy-agent-settings__btn--save',
						'submit',
						false
					);
					?>
				</div>
			</form>
		</div>
		<?php
	}
}
