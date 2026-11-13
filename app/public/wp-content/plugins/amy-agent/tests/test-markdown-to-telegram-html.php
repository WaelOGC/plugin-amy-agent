<?php
/**
 * Unit tests for Amy_Telegram::markdown_to_telegram_html().
 *
 * Run: php tests/test-markdown-to-telegram-html.php
 *
 * @package Amy_Agent
 */

declare(strict_types=1);

if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/**
 * Minimal esc_url stub (http/https only).
 *
 * @param string       $url       Raw URL.
 * @param array|null   $protocols Allowed protocols.
 * @return string
 */
if ( ! function_exists( 'esc_url' ) ) {
	function esc_url( $url, $protocols = null ) {
		$url = trim( (string) $url );
		if ( '' === $url ) {
			return '';
		}
		$allowed = is_array( $protocols ) ? $protocols : array( 'http', 'https' );
		foreach ( $allowed as $proto ) {
			if ( 0 === stripos( $url, $proto . '://' ) ) {
				return $url;
			}
		}
		return '';
	}
}

require_once dirname( __DIR__ ) . '/includes/class-amy-telegram.php';

$failures = 0;

/**
 * @param string $label Assertion label.
 * @param bool   $ok    Pass?
 * @param string $detail Optional detail.
 */
function amy_assert( string $label, bool $ok, string $detail = '' ): void {
	global $failures;
	if ( $ok ) {
		echo "PASS  {$label}\n";
		return;
	}
	++$failures;
	echo "FAIL  {$label}" . ( '' !== $detail ? " — {$detail}" : '' ) . "\n";
}

// --- Headings ---
$h3 = Amy_Telegram::markdown_to_telegram_html( "### Snapshot" );
amy_assert( '### heading → bold line', '<b>Snapshot</b>' === $h3, $h3 );

$h2 = Amy_Telegram::markdown_to_telegram_html( "## Leads" );
amy_assert( '## heading → bold line', '<b>Leads</b>' === $h2, $h2 );

$h1 = Amy_Telegram::markdown_to_telegram_html( "# Overview" );
amy_assert( '# heading → bold line', '<b>Overview</b>' === $h1, $h1 );

amy_assert(
	'heading leaves no raw #',
	false === strpos( $h3, '#' ) && false === strpos( $h2, '#' ),
	$h3 . ' | ' . $h2
);

// --- Bullets ---
$star = Amy_Telegram::markdown_to_telegram_html( "* first item" );
amy_assert( '* bullet → •', '• first item' === $star, $star );

$dash = Amy_Telegram::markdown_to_telegram_html( "- second item" );
amy_assert( '- bullet → •', '• second item' === $dash, $dash );

$multi = Amy_Telegram::markdown_to_telegram_html( "* one\n- two\n* three" );
amy_assert(
	'mixed * / - bullets',
	"• one\n• two\n• three" === $multi,
	$multi
);
amy_assert(
	'bullets leave no leading * or -',
	! preg_match( '/^[\*\-]/m', $multi ),
	$multi
);

// --- Bold / italic still work ---
$bi = Amy_Telegram::markdown_to_telegram_html( 'Say **hello** and *world* please' );
amy_assert(
	'bold + italic',
	'<b>hello</b>' === substr( $bi, strpos( $bi, '<b>' ), 15 ) || false !== strpos( $bi, '<b>hello</b>' ),
	$bi
);
amy_assert( 'italic present', false !== strpos( $bi, '<i>world</i>' ), $bi );

// --- Blockquote (Next step box) ---
$bq = Amy_Telegram::markdown_to_telegram_html( "> **Next step**\n> Follow up the hot lead." );
amy_assert( 'blockquote opens', false !== strpos( $bq, '<blockquote>' ), $bq );
amy_assert( 'blockquote bold Next step', false !== strpos( $bq, '<b>Next step</b>' ), $bq );
amy_assert( 'blockquote closes', false !== strpos( $bq, '</blockquote>' ), $bq );

// --- Mixed lead-snapshot style fixture ---
$fixture = <<<'MD'
### Lead snapshot

Here is the current visitor picture.

**Status**
🔥 2 hot · 🌤️ 1 warm · ❄️ 4 cold

**Hot sample**
* Visitor a1b2c3d4: lead@example.com
* 📍 The Hague, NL — last seen 2h ago

**Confidence: medium**

> **Next step**
> Review the hot sample and follow up.
MD;

$html = Amy_Telegram::markdown_to_telegram_html( $fixture );

amy_assert( 'fixture: heading is bold', false !== strpos( $html, '<b>Lead snapshot</b>' ), $html );
amy_assert( 'fixture: section Status bold', false !== strpos( $html, '<b>Status</b>' ), $html );
amy_assert( 'fixture: bullet → •', false !== strpos( $html, '• Visitor a1b2c3d4' ), $html );
amy_assert( 'fixture: location row kept', false !== strpos( $html, '📍 The Hague' ), $html );
amy_assert( 'fixture: confidence bold', false !== strpos( $html, '<b>Confidence: medium</b>' ), $html );
amy_assert( 'fixture: next-step blockquote', false !== strpos( $html, '<blockquote>' ), $html );
amy_assert( 'fixture: no raw # survives', false === strpos( $html, '#' ), $html );
amy_assert(
	'fixture: no leading * or - list markers',
	! preg_match( '/^[\*\-] /m', $html ),
	$html
);
amy_assert( 'fixture: escapes angle brackets', false === strpos( $html, '<script>' ), $html );

$escaped = Amy_Telegram::markdown_to_telegram_html( 'Use <b>tags</b> & more' );
amy_assert(
	'raw HTML escaped',
	false !== strpos( $escaped, '&lt;b&gt;' ) && false !== strpos( $escaped, '&amp;' ),
	$escaped
);

// --- AA-20: service HTML sentinel block (no Markdown **) ---
$service_html_rec = <<<'HTML'
@@AMY_TG_HTML@@
<b>Recommendations</b>
<b>Finding</b>
7 visitor sessions are scored hot (high-intent).
<b>Evidence</b>
234 lead sessions total; hot=7, warm=5, cold=222; with_email=3; hot_with_email=2; hot_without_email=5; seen_7d=43.
<b>Confidence: high</b>
<b>Limitations</b>
Hot scoring is rule-based; having an email does not prove consent for marketing — use Approve → Send in Email Marketing.
<b>Next step</b>
Prioritize the hot leads that already left an email, then review the remaining hot sessions in Analytics.
@@/AMY_TG_HTML@@
HTML;

$model_body = <<<'MD'
**Activity Overview**
Here is today's picture of potential clients.

**Lead Status Breakdown**
🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold

**Hot Leads Sample**
• Visitor abc12345: (email on file)
MD;

$outbound = $model_body . "\n\n" . $service_html_rec;
$html_e2e = Amy_Telegram::markdown_to_telegram_html( $outbound );

amy_assert( 'e2e: Activity Overview bold', false !== strpos( $html_e2e, '<b>Activity Overview</b>' ), $html_e2e );
amy_assert( 'e2e: Recommendations bold', false !== strpos( $html_e2e, '<b>Recommendations</b>' ), $html_e2e );
amy_assert( 'e2e: Finding bold', false !== strpos( $html_e2e, '<b>Finding</b>' ), $html_e2e );
amy_assert( 'e2e: Evidence bold', false !== strpos( $html_e2e, '<b>Evidence</b>' ), $html_e2e );
amy_assert( 'e2e: Confidence bold', false !== strpos( $html_e2e, '<b>Confidence: high</b>' ), $html_e2e );
amy_assert( 'e2e: Limitations bold', false !== strpos( $html_e2e, '<b>Limitations</b>' ), $html_e2e );
amy_assert( 'e2e: Next step bold', false !== strpos( $html_e2e, '<b>Next step</b>' ), $html_e2e );
amy_assert( 'e2e: finding body kept', false !== strpos( $html_e2e, '7 visitor sessions are scored hot' ), $html_e2e );
amy_assert( 'e2e: Approve arrow kept', false !== strpos( $html_e2e, 'Approve → Send' ), $html_e2e );
amy_assert( 'e2e: sentinel stripped', false === strpos( $html_e2e, 'AMY_TG_HTML' ), $html_e2e );
amy_assert( 'e2e: no raw ** left', false === strpos( $html_e2e, '**' ), $html_e2e );
// Must not double-escape service <b> into visible &lt;b&gt;.
amy_assert( 'e2e: no escaped b tags', false === strpos( $html_e2e, '&lt;b&gt;' ), $html_e2e );

// --- AA-20 regression: LITERAL live paste — bare labels, NO asterisks ---
$live_plain = <<<'TXT'
**Lead Status Breakdown**
🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold

**Hot Leads Sample**
• Visitor sample

Recommendations
Finding
7 visitor sessions are scored hot (high-intent).
Evidence
234 lead sessions total; hot=7, warm=5, cold=222; with_email=3; hot_with_email=2; hot_without_email=5; seen_7d=43.
Confidence: high
Limitations
Hot scoring is rule-based; having an email does not prove consent for marketing — use Approve → Send in Email Marketing.
Next step
Prioritize the hot leads that already left an email, then review the remaining hot sessions in Analytics.
TXT;

$html_live = Amy_Telegram::markdown_to_telegram_html( $live_plain );
amy_assert( 'live: Lead Status bold', false !== strpos( $html_live, '<b>Lead Status Breakdown</b>' ), $html_live );
amy_assert( 'live: Recommendations bold', false !== strpos( $html_live, '<b>Recommendations</b>' ), $html_live );
amy_assert( 'live: Finding bold', false !== strpos( $html_live, '<b>Finding</b>' ), $html_live );
amy_assert( 'live: Evidence bold', false !== strpos( $html_live, '<b>Evidence</b>' ), $html_live );
amy_assert( 'live: Confidence bold', false !== strpos( $html_live, '<b>Confidence: high</b>' ), $html_live );
amy_assert( 'live: Limitations bold', false !== strpos( $html_live, '<b>Limitations</b>' ), $html_live );
amy_assert( 'live: Next step bold', false !== strpos( $html_live, '<b>Next step</b>' ), $html_live );
amy_assert( 'live: no bare Finding line', 1 !== preg_match( '/^Finding$/m', $html_live ), $html_live );
amy_assert( 'live: no bare Next step line', 1 !== preg_match( '/^Next step$/m', $html_live ), $html_live );

// bold_recommendation_labels is idempotent on already-bold lines.
$already = Amy_Telegram::bold_recommendation_labels( "<b>Finding</b>\nbody" );
amy_assert( 'idempotent Finding', '<b>Finding</b>' === explode( "\n", $already )[0], $already );

// Dangerous body chars are escaped when they arrive as Markdown (not sentinel HTML).
$dangerous = Amy_Telegram::markdown_to_telegram_html(
	"Finding\nSaw <script>x</script> & more\nEvidence\nn=1\nConfidence: low\nLimitations\nn/a"
);
amy_assert( 'escapes script', false !== strpos( $dangerous, '&lt;script&gt;' ), $dangerous );
amy_assert( 'escapes amp', false !== strpos( $dangerous, '&amp;' ), $dangerous );
amy_assert( 'still bolds Finding', false !== strpos( $dangerous, '<b>Finding</b>' ), $dangerous );

// Parse-error detection: Bot API often returns HTTP 200 + error_code 400.
$parse_http200 = array(
	'ok'     => false,
	'status' => 200,
	'data'   => array(
		'ok'          => false,
		'error_code'  => 400,
		'description' => "Bad Request: can't parse entities: Unsupported start tag \"blockquote\"",
	),
	'error'  => "Bad Request: can't parse entities: Unsupported start tag \"blockquote\"",
);
amy_assert(
	'parse error detects error_code 400 on HTTP 200',
	Amy_Telegram::is_telegram_parse_error( $parse_http200 ),
	'expected true'
);
amy_assert(
	'parse error false when ok',
	! Amy_Telegram::is_telegram_parse_error(
		array(
			'ok'     => true,
			'status' => 200,
			'data'   => array( 'ok' => true ),
			'error'  => null,
		)
	),
	'expected false'
);

$with_bq = '<b>Next step</b><blockquote>Do the thing</blockquote>';
$stripped = Amy_Telegram::strip_telegram_blockquotes( $with_bq );
amy_assert( 'strip blockquote keeps bold', false !== strpos( $stripped, '<b>Next step</b>' ), $stripped );
amy_assert( 'strip blockquote removes tags', false === strpos( $stripped, 'blockquote' ), $stripped );

if ( $failures > 0 ) {
	echo "\n{$failures} failure(s)\n";
	exit( 1 );
}

echo "\nAll markdown_to_telegram_html tests passed.\n";
exit( 0 );
