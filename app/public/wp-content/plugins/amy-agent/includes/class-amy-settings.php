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

	/**
	 * Default marketing From when Settings field is empty.
	 */
	const DEFAULT_MARKETING_FROM_EMAIL = 'hello@ogcnewfinity.com';

	/**
	 * Default marketing From display name.
	 */
	const DEFAULT_MARKETING_FROM_NAME = 'OGC NewFinity';

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
				'i18n'              => array(
					'fromBlocked'       => __( 'Marketing From cannot be personal Gmail, AgentMail, or free webmail. Use a domain mailbox such as hello@ogcnewfinity.com.', 'amy-agent' ),
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
					'tgSaveFirst'       => __( 'Save settings first so the bot token is stored.', 'amy-agent' ),
					'tgConnecting'      => __( 'Connecting…', 'amy-agent' ),
					'tgDisconnecting'   => __( 'Disconnecting…', 'amy-agent' ),
					'tgTesting'         => __( 'Sending test messages…', 'amy-agent' ),
					'tgStatusLoading'   => __( 'Loading Telegram status…', 'amy-agent' ),
					'tgConnected'       => __( 'Connected', 'amy-agent' ),
					'tgNotConnected'    => __( 'Not connected', 'amy-agent' ),
					'tgError'           => __( 'Error', 'amy-agent' ),
					'tgHttpsRequired'   => __( 'Telegram webhooks require HTTPS. Connect is disabled until the site uses HTTPS.', 'amy-agent' ),
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
	 * Marketing From email — empty falls back to hello@ogcnewfinity.com.
	 * Rejects personal Gmail / AgentMail / free webmail.
	 *
	 * @param mixed $value Submitted email.
	 * @return string
	 */
	public function sanitize_marketing_from_email( $value ) {
		$email = sanitize_email( trim( (string) $value ) );
		if ( '' === $email || ! is_email( $email ) ) {
			return self::DEFAULT_MARKETING_FROM_EMAIL;
		}
		$host = strtolower( (string) substr( strrchr( $email, '@' ), 1 ) );
		if ( in_array( $host, self::blocked_marketing_from_hosts(), true ) ) {
			add_settings_error(
				'amy_agent_settings',
				'amy_marketing_from_blocked',
				__( 'Marketing From cannot be personal Gmail, AgentMail, or free webmail. Kept hello@ogcnewfinity.com.', 'amy-agent' ),
				'error'
			);
			return self::DEFAULT_MARKETING_FROM_EMAIL;
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
	 *
	 * @return string
	 */
	public function get_marketing_from_email() {
		$email = sanitize_email( trim( (string) get_option( self::OPTION_MARKETING_FROM_EMAIL, '' ) ) );
		if ( '' === $email || ! is_email( $email ) ) {
			return self::DEFAULT_MARKETING_FROM_EMAIL;
		}
		$host = strtolower( (string) substr( strrchr( $email, '@' ), 1 ) );
		if ( in_array( $host, self::blocked_marketing_from_hosts(), true ) ) {
			return self::DEFAULT_MARKETING_FROM_EMAIL;
		}
		return strtolower( $email );
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
	 * Readiness summary for the Settings header banner.
	 *
	 * @return array{state:string,badge:string,title:string,text:string,missing:string[]}
	 */
	private function get_readiness_summary() {
		$enabled    = $this->is_enabled();
		$configured = $this->is_service_configured();
		$ready      = $this->is_ready();
		$missing    = array();

		if ( ! $enabled ) {
			$missing[] = __( 'Enable Amy is off', 'amy-agent' );
		}
		if ( '' === $this->get_service_url() ) {
			$missing[] = __( 'Python service URL is empty', 'amy-agent' );
		}
		if ( '' === $this->get_shared_secret() ) {
			$missing[] = __( 'Shared secret is empty', 'amy-agent' );
		}

		if ( $ready ) {
			return array(
				'state'   => 'ready',
				'badge'   => __( 'Ready', 'amy-agent' ),
				'title'   => __( 'Amy is ready on the site', 'amy-agent' ),
				'text'    => __( 'Enable Amy is on and the service URL + shared secret are set. The floating widget and Amy Submit Idea can load.', 'amy-agent' ),
				'missing' => array(),
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
			'text'    => __( 'Enable Amy plus a service URL and shared secret are required. Widget and Submit Idea stay hidden until then.', 'amy-agent' ),
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
								<li><?php echo esc_html( $item ); ?></li>
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

					<div class="amy-agent-settings__card">
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

					<div class="amy-agent-settings__card">
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'Email Marketing From', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint amy-agent-settings__hint--card">
							<?php echo esc_html__( 'Sends go through wp_mail / FluentSMTP. From must be a verified domain mailbox — never personal Gmail, AgentMail, or free webmail.', 'amy-agent' ); ?>
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
								<?php echo esc_html__( 'Default: hello@ogcnewfinity.com. Must match a mailbox FluentSMTP is authorized to send as (SPF/DKIM on the domain).', 'amy-agent' ); ?>
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

					<div class="amy-agent-settings__card">
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

					<div class="amy-agent-settings__card">
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
						<?php echo esc_html__( 'Private admin bot — same Amy and conversations as Dashboard Chat. Token and webhook secret stay in WordPress only.', 'amy-agent' ); ?>
					</p>

					<?php if ( ! is_ssl() ) : ?>
						<div class="amy-agent-settings__notice amy-agent-settings__notice--warn" role="status">
							<?php echo esc_html__( 'This site is not using HTTPS. Telegram only accepts HTTPS webhooks — Connect is disabled until the site is served over HTTPS.', 'amy-agent' ); ?>
						</div>
					<?php endif; ?>

					<div class="amy-agent-settings__card">
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
									<?php echo esc_html__( 'Create the bot with @BotFather. Never share this token.', 'amy-agent' ); ?>
								</p>
							<?php endif; ?>
						</div>

						<p class="amy-agent-settings__telegram-status" id="amy-settings-telegram-status" role="status" aria-live="polite"></p>

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
						<h3 class="amy-agent-settings__card-title"><?php echo esc_html__( 'How to find your Telegram ID', 'amy-agent' ); ?></h3>
						<p class="amy-agent-settings__hint">
							<?php echo esc_html__( 'Open your bot in Telegram and send /start — it replies with your ID. Paste it above, save, then press Connect.', 'amy-agent' ); ?>
						</p>
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
