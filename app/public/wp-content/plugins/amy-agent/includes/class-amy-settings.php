<?php
/**
 * Amy Agent admin settings page.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Registers and renders Settings → Amy Agent.
 */
class Amy_Settings {

	const OPTION_ENABLED       = 'amy_agent_enabled';
	const OPTION_SERVICE_URL   = 'amy_agent_service_url';
	const OPTION_SHARED_SECRET = 'amy_agent_shared_secret';
	const OPTION_AI_PROVIDER   = 'amy_agent_ai_provider';
	const OPTION_AI_API_KEY    = 'amy_agent_ai_api_key';
	const OPTION_AI_MODEL      = 'amy_agent_ai_model';

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
	 * Wire admin hooks.
	 */
	public function register() {
		add_action( 'admin_menu', array( $this, 'add_menu' ) );
		add_action( 'admin_init', array( $this, 'register_settings' ) );
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_assets' ) );
		add_filter( 'plugin_action_links_' . plugin_basename( AMY_AGENT_FILE ), array( $this, 'add_settings_link' ) );
	}

	/**
	 * Add a Settings link on the Plugins list row.
	 *
	 * @param array $links Existing action links.
	 * @return array
	 */
	public function add_settings_link( $links ) {
		$url = admin_url( 'options-general.php?page=amy-agent' );
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
	 * Add Settings submenu.
	 */
	public function add_menu() {
		add_options_page(
			__( 'Amy Agent', 'amy-agent' ),
			__( 'Amy Agent', 'amy-agent' ),
			'manage_options',
			'amy-agent',
			array( $this, 'render_page' )
		);
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

		add_settings_section(
			'amy_agent_section_general',
			__( 'General', 'amy-agent' ),
			array( $this, 'render_section_general' ),
			'amy-agent'
		);

		add_settings_field(
			self::OPTION_ENABLED,
			__( 'Enable Amy', 'amy-agent' ),
			array( $this, 'render_field_enabled' ),
			'amy-agent',
			'amy_agent_section_general'
		);

		add_settings_field(
			self::OPTION_SERVICE_URL,
			__( 'Python service URL', 'amy-agent' ),
			array( $this, 'render_field_service_url' ),
			'amy-agent',
			'amy_agent_section_general'
		);

		add_settings_field(
			self::OPTION_SHARED_SECRET,
			__( 'Shared secret', 'amy-agent' ),
			array( $this, 'render_field_shared_secret' ),
			'amy-agent',
			'amy_agent_section_general'
		);

		add_settings_section(
			'amy_agent_section_ai',
			__( 'AI provider', 'amy-agent' ),
			array( $this, 'render_section_ai' ),
			'amy-agent'
		);

		add_settings_field(
			self::OPTION_AI_PROVIDER,
			__( 'Provider', 'amy-agent' ),
			array( $this, 'render_field_provider' ),
			'amy-agent',
			'amy_agent_section_ai'
		);

		add_settings_field(
			self::OPTION_AI_API_KEY,
			__( 'API key', 'amy-agent' ),
			array( $this, 'render_field_api_key' ),
			'amy-agent',
			'amy_agent_section_ai'
		);

		add_settings_field(
			self::OPTION_AI_MODEL,
			__( 'Model (optional)', 'amy-agent' ),
			array( $this, 'render_field_model' ),
			'amy-agent',
			'amy_agent_section_ai'
		);
	}

	/**
	 * Enqueue admin assets on the settings page only.
	 *
	 * @param string $hook_suffix Current admin page hook.
	 */
	public function enqueue_assets( $hook_suffix ) {
		if ( 'settings_page_amy-agent' !== $hook_suffix ) {
			return;
		}

		wp_enqueue_style(
			'amy-agent-admin-settings',
			AMY_AGENT_URL . 'admin/css/admin-settings.css',
			array(),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-agent-admin-settings',
			AMY_AGENT_URL . 'admin/js/admin-settings.js',
			array(),
			AMY_AGENT_VERSION,
			true
		);
	}

	/**
	 * @param mixed $value Raw checkbox value.
	 * @return string '1' or '0'
	 */
	public function sanitize_checkbox( $value ) {
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
	 * Section intro: general.
	 */
	public function render_section_general() {
		echo '<p>' . esc_html__( 'Connect WordPress to the Amy Python service. Amy stays inactive until Enable is on and the service URL + shared secret are set.', 'amy-agent' ) . '</p>';
	}

	/**
	 * Section intro: AI.
	 */
	public function render_section_ai() {
		echo '<p>' . esc_html__( 'Choose which AI provider powers Amy. The key is stored in the WordPress database and sent to the Python service at request time — never hardcoded.', 'amy-agent' ) . '</p>';
	}

	/**
	 * Enable checkbox.
	 */
	public function render_field_enabled() {
		$checked = $this->is_enabled();
		// Hidden 0 so unchecking still persists via Settings API.
		printf(
			'<input type="hidden" name="%1$s" value="0" />',
			esc_attr( self::OPTION_ENABLED )
		);
		printf(
			'<label><input type="checkbox" name="%1$s" value="1" %2$s /> %3$s</label>',
			esc_attr( self::OPTION_ENABLED ),
			checked( $checked, true, false ),
			esc_html__( 'Replace Submit Your Idea manual form when ready (requires service URL + secret).', 'amy-agent' )
		);
	}

	/**
	 * Service URL field.
	 */
	public function render_field_service_url() {
		printf(
			'<input type="url" class="regular-text" name="%1$s" value="%2$s" placeholder="http://127.0.0.1:8765" />',
			esc_attr( self::OPTION_SERVICE_URL ),
			esc_attr( $this->get_service_url() )
		);
		echo '<p class="description">' . esc_html__( 'Base URL of amy-agent-service (no trailing slash). On Local, try 127.0.0.1 or host.docker.internal.', 'amy-agent' ) . '</p>';
	}

	/**
	 * Shared secret field.
	 */
	public function render_field_shared_secret() {
		$secret     = $this->get_shared_secret();
		$has_secret = '' !== $secret;
		printf(
			'<input type="password" class="regular-text" name="%1$s" value="" autocomplete="new-password" placeholder="%2$s" />',
			esc_attr( self::OPTION_SHARED_SECRET ),
			$has_secret ? esc_attr__( 'Enter a new secret to replace the saved one', 'amy-agent' ) : esc_attr__( 'Enter a shared secret', 'amy-agent' )
		);
		if ( $has_secret ) {
			echo '<p class="amy-agent-saved-status"><strong>' . esc_html__( 'Saved:', 'amy-agent' ) . '</strong> ';
			echo esc_html(
				sprintf(
					/* translators: %s: masked secret ending */
					__( 'Shared secret is stored in the database (%s). Leave the field blank when saving to keep it.', 'amy-agent' ),
					$this->mask_secret( $secret )
				)
			);
			echo '</p>';
		} else {
			echo '<p class="description">' . esc_html__( 'Must match AMY_SHARED_SECRET in the Python service .env.', 'amy-agent' ) . '</p>';
		}
	}

	/**
	 * Provider select.
	 */
	public function render_field_provider() {
		$current = $this->get_ai_provider();
		printf( '<select name="%s" id="amy_agent_ai_provider">', esc_attr( self::OPTION_AI_PROVIDER ) );
		foreach ( self::providers() as $slug => $label ) {
			printf(
				'<option value="%1$s" %2$s>%3$s</option>',
				esc_attr( $slug ),
				selected( $current, $slug, false ),
				esc_html( $label )
			);
		}
		echo '</select>';
	}

	/**
	 * API key — password field never re-prints the raw key into HTML.
	 */
	public function render_field_api_key() {
		$key     = $this->get_ai_api_key();
		$has_key = '' !== $key;
		printf(
			'<input type="password" class="regular-text" name="%1$s" value="" autocomplete="new-password" placeholder="%2$s" />',
			esc_attr( self::OPTION_AI_API_KEY ),
			$has_key ? esc_attr__( 'Enter a new key to replace the saved one', 'amy-agent' ) : esc_attr__( 'Paste your API key', 'amy-agent' )
		);
		if ( $has_key ) {
			echo '<p class="amy-agent-saved-status"><strong>' . esc_html__( 'Saved:', 'amy-agent' ) . '</strong> ';
			echo esc_html(
				sprintf(
					/* translators: %s: masked API key ending */
					__( 'API key is stored in the database (%s). Leave the field blank when saving to keep it.', 'amy-agent' ),
					$this->mask_secret( $key )
				)
			);
			echo '</p>';
		} else {
			echo '<p class="description">' . esc_html__( 'Stored via the Options API. The field stays empty after save on purpose so the key is never shown in the page HTML.', 'amy-agent' ) . '</p>';
		}
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
	 * Optional model override.
	 */
	public function render_field_model() {
		$model = (string) get_option( self::OPTION_AI_MODEL, '' );
		printf(
			'<input type="text" class="regular-text" name="%1$s" value="%2$s" placeholder="%3$s" />',
			esc_attr( self::OPTION_AI_MODEL ),
			esc_attr( $model ),
			esc_attr__( 'Provider default if empty', 'amy-agent' )
		);
	}

	/**
	 * Settings page markup.
	 */
	public function render_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap amy-agent-settings">
			<h1><?php echo esc_html( get_admin_page_title() ); ?></h1>
			<form method="post" action="options.php">
				<?php
				settings_fields( 'amy_agent_settings' );
				do_settings_sections( 'amy-agent' );
				submit_button( __( 'Save settings', 'amy-agent' ) );
				?>
			</form>
		</div>
		<?php
	}
}
