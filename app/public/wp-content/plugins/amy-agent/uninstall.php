<?php
/**
 * Uninstall cleanup for Amy Agent.
 *
 * @package Amy_Agent
 */

defined( 'WP_UNINSTALL_PLUGIN' ) || exit;

$option_keys = array(
	'amy_agent_enabled',
	'amy_agent_service_url',
	'amy_agent_shared_secret',
	'amy_agent_ai_provider',
	'amy_agent_ai_api_key',
	'amy_agent_ai_model',
	'amy_agent_avatar_url',
);

foreach ( $option_keys as $key ) {
	delete_option( $key );
}
