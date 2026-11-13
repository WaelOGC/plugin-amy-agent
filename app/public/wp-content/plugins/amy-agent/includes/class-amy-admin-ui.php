<?php
/**
 * Shared Amy admin UI helpers (cards, switches, help popovers).
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Markup helpers for the card / toggle / (?) popover admin pattern.
 */
class Amy_Admin_UI {

	/**
	 * Whether shared admin-ui assets were enqueued this request.
	 *
	 * @var bool
	 */
	private static $assets_enqueued = false;

	/**
	 * Enqueue shared admin-ui CSS + JS (safe to call from multiple pages).
	 */
	public static function enqueue_assets() {
		if ( self::$assets_enqueued ) {
			return;
		}
		self::$assets_enqueued = true;

		wp_enqueue_style(
			'amy-agent-admin-ui',
			AMY_AGENT_URL . 'admin/css/admin-ui.css',
			array( 'dashicons' ),
			AMY_AGENT_VERSION
		);

		wp_enqueue_script(
			'amy-agent-admin-ui',
			AMY_AGENT_URL . 'admin/js/admin-ui.js',
			array(),
			AMY_AGENT_VERSION,
			true
		);
	}

	/**
	 * Render a circular (?) help control with popover text.
	 *
	 * @param string $id      Unique DOM id stem.
	 * @param string $text    Help body (plain text; escaped).
	 * @param string $label   Accessible name (defaults to “More information”).
	 * @param string $align   'start' or 'end' for popover alignment.
	 */
	public static function render_help( $id, $text, $label = '', $align = 'start' ) {
		$id    = sanitize_html_class( (string) $id );
		$text  = (string) $text;
		$label = '' !== $label ? (string) $label : __( 'More information', 'amy-agent' );
		$align = 'end' === $align ? 'end' : 'start';

		if ( '' === $id || '' === $text ) {
			return;
		}

		$panel_id = 'amy-admin-help-' . $id;
		$classes  = 'amy-admin-help';
		if ( 'end' === $align ) {
			$classes .= ' amy-admin-help--end';
		}
		?>
		<span class="<?php echo esc_attr( $classes ); ?>" data-amy-admin-help>
			<button
				type="button"
				class="amy-admin-help__btn"
				data-amy-admin-help-btn
				aria-label="<?php echo esc_attr( $label ); ?>"
				aria-expanded="false"
				aria-controls="<?php echo esc_attr( $panel_id ); ?>"
				aria-haspopup="dialog"
			>?</button>
			<span
				class="amy-admin-help__popover"
				id="<?php echo esc_attr( $panel_id ); ?>"
				data-amy-admin-help-panel
				role="tooltip"
				hidden
			><?php echo esc_html( $text ); ?></span>
		</span>
		<?php
	}

	/**
	 * Render a pill toggle switch bound to a checkbox option.
	 *
	 * @param string $id      Input id.
	 * @param string $name    Input name (option key).
	 * @param bool   $checked Whether checked.
	 * @param string $aria    Optional aria-label (defaults to nearby visible label).
	 */
	public static function render_switch( $id, $name, $checked, $aria = '' ) {
		$id   = (string) $id;
		$name = (string) $name;
		?>
		<label class="amy-admin-switch" for="<?php echo esc_attr( $id ); ?>">
			<input
				class="amy-admin-switch__input"
				type="checkbox"
				id="<?php echo esc_attr( $id ); ?>"
				name="<?php echo esc_attr( $name ); ?>"
				value="1"
				<?php checked( (bool) $checked, true ); ?>
				<?php echo '' !== $aria ? 'aria-label="' . esc_attr( $aria ) . '"' : ''; ?>
			/>
			<span class="amy-admin-switch__track" aria-hidden="true"></span>
		</label>
		<?php
	}

	/**
	 * Read-only switch (Overview status mirror).
	 *
	 * @param bool   $checked Current state.
	 * @param string $aria    Accessible label.
	 */
	public static function render_switch_readonly( $checked, $aria = '' ) {
		?>
		<span class="amy-admin-switch is-readonly" <?php echo '' !== $aria ? 'aria-label="' . esc_attr( $aria ) . '"' : ''; ?>>
			<input
				class="amy-admin-switch__input"
				type="checkbox"
				tabindex="-1"
				disabled
				<?php checked( (bool) $checked, true ); ?>
			/>
			<span class="amy-admin-switch__track" aria-hidden="true"></span>
		</span>
		<?php
	}
}
