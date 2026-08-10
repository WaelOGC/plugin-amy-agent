<?php
/**
 * Plugin Name:       Amy Agent
 * Plugin URI:        https://ogcnewfinity.com
 * Description:       Digital employee for OGC NewFinity — conversational UI, intelligence via a Python service, admin-configurable AI providers.
 * Version:           0.2.12
 * Requires at least: 6.0
 * Requires PHP:      8.0
 * Author:            OGC NewFinity
 * Author URI:        https://ogcnewfinity.com
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       amy-agent
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

define( 'AMY_AGENT_VERSION', '0.2.12' );
define( 'AMY_AGENT_FILE', __FILE__ );
define( 'AMY_AGENT_PATH', plugin_dir_path( __FILE__ ) );
define( 'AMY_AGENT_URL', plugin_dir_url( __FILE__ ) );

require_once AMY_AGENT_PATH . 'includes/class-amy-settings.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-admin-menu.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-api-client.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-rest.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-theme-bridge.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-assets.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-submit-idea.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-submit-idea-mail.php';
require_once AMY_AGENT_PATH . 'includes/class-amy-plugin.php';

/**
 * Returns the main plugin instance.
 *
 * @return Amy_Plugin
 */
function amy_agent() {
	return Amy_Plugin::instance();
}

register_activation_hook( __FILE__, array( 'Amy_Plugin', 'activate' ) );
register_deactivation_hook( __FILE__, array( 'Amy_Plugin', 'deactivate' ) );

amy_agent();
