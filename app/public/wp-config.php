<?php
/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the web site, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * Localized language
 * * ABSPATH
 *
 * @link https://wordpress.org/support/article/editing-wp-config-php/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', 'local' );

/** Database username */
define( 'DB_USER', 'root' );

/** Database password */
define( 'DB_PASSWORD', 'root' );

/** Database hostname */
define( 'DB_HOST', 'localhost' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define( 'AUTH_KEY',          '*o#bCU?uU7loh@I;6-Ymv#(%OBxy9UKDTwc!MA+tLy{-iYdI+ ^:a2?|._va?1n~' );
define( 'SECURE_AUTH_KEY',   '70]V`ul5s7 -=z+jISWo3VDD9:~(=NkSJmwCYkiCca]q!o.>bq.XCqgLL-gzQI4p' );
define( 'LOGGED_IN_KEY',     ').@PWw}B0u+)g)52Rx[}<&(#WgIGfvj:sB+~_|&-SV?4%JPi/VW3PDX6%rdabw1j' );
define( 'NONCE_KEY',         'mXBEBvR:e^bhE`<bbIu-CPmm#&hfIRjF2qA!6Z,_(d)WZ_?(k018[*=u=<jG9AVJ' );
define( 'AUTH_SALT',         'Gz^U.KXf-+<A}tTs&W01`(aE|HO27nsUBWm[XBZECI*+[ZRrg`)?|zNF+VC&+rco' );
define( 'SECURE_AUTH_SALT',  '#]czWd Yg+LA0~JReT#1xtwNk9(bj-GqYW&k~gK6~!T CCHI5QquPM]g;(@lRotV' );
define( 'LOGGED_IN_SALT',    '2$qTtu@RC(d+=s4z&dvHUgf(ZCf+BU{((6M&yaT8XmESLE/NO6Wu,&~Ny#T9b0XG' );
define( 'NONCE_SALT',        ':x$T|Y)5_W5xX-|(L}AO@!cMua|<Obb Aqh{+DQ&cnN$:)~wM_YghGwK@BP(bEab' );
define( 'WP_CACHE_KEY_SALT', 'iJmSp(LqXI9yK!39@2Z}~d5^Y4fSYhVDKjXXF HHG_dMPP:9;=f2V4~=Rh3ZY3bB' );


/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 */
$table_prefix = 'wp_';


/* Add any custom values between this line and the "stop editing" line. */



/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://wordpress.org/support/article/debugging-in-wordpress/
 */
if ( ! defined( 'WP_DEBUG' ) ) {
	define( 'WP_DEBUG', false );
}

define( 'WP_ENVIRONMENT_TYPE', 'local' );
/* That's all, stop editing! Happy publishing. */

/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
require_once ABSPATH . 'wp-settings.php';
