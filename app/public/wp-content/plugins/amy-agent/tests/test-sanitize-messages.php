<?php
/**
 * Unit tests for Amy_Rest::sanitize_messages() attachment handling.
 *
 * Run: php tests/test-sanitize-messages.php
 *
 * @package Amy_Agent
 */

declare(strict_types=1);

if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/**
 * Minimal WordPress sanitize stubs used by Amy_Rest message helpers.
 */
if ( ! function_exists( 'sanitize_key' ) ) {
	/**
	 * @param string $key Raw key.
	 */
	function sanitize_key( $key ) {
		$key = strtolower( (string) $key );
		return (string) preg_replace( '/[^a-z0-9_\-]/', '', $key );
	}
}

if ( ! function_exists( 'sanitize_text_field' ) ) {
	/**
	 * @param string $str Raw string.
	 */
	function sanitize_text_field( $str ) {
		$str = (string) $str;
		$str = strip_tags( $str );
		$str = preg_replace( '/[\r\n\t]+/', ' ', $str );
		return trim( $str );
	}
}

if ( ! function_exists( 'sanitize_textarea_field' ) ) {
	/**
	 * @param string $str Raw string.
	 */
	function sanitize_textarea_field( $str ) {
		$str = (string) $str;
		$str = strip_tags( $str );
		return trim( $str );
	}
}

if ( ! function_exists( 'esc_url_raw' ) ) {
	/**
	 * @param string $url Raw URL.
	 */
	function esc_url_raw( $url ) {
		$url = trim( (string) $url );
		if ( '' === $url ) {
			return '';
		}
		if ( ! preg_match( '#^https?://#i', $url ) && ! preg_match( '#^/#', $url ) ) {
			return '';
		}
		return $url;
	}
}

require_once dirname( __DIR__ ) . '/includes/class-amy-rest.php';

/**
 * Invoke private Amy_Rest::sanitize_messages via reflection.
 *
 * @param mixed $messages Raw messages.
 * @return array
 */
function amy_test_sanitize_messages( $messages ) {
	$ref  = new ReflectionClass( Amy_Rest::class );
	$inst = $ref->newInstanceWithoutConstructor();
	$meth = $ref->getMethod( 'sanitize_messages' );
	$meth->setAccessible( true );
	return $meth->invoke( $inst, $messages );
}

/**
 * @param bool   $ok      Assertion result.
 * @param string $label   Case label.
 * @param string $detail  Failure detail.
 */
function amy_assert( bool $ok, string $label, string $detail = '' ): void {
	global $amy_test_failed, $amy_test_passed;
	if ( $ok ) {
		++$amy_test_passed;
		echo "PASS  {$label}\n";
		return;
	}
	++$amy_test_failed;
	echo "FAIL  {$label}" . ( '' !== $detail ? " — {$detail}" : '' ) . "\n";
}

$amy_test_passed = 0;
$amy_test_failed = 0;

// 1) Empty content + 1 valid attachment → kept with attachments.
$out = amy_test_sanitize_messages(
	array(
		array(
			'role'        => 'user',
			'content'     => '',
			'attachments' => array(
				array(
					'url'          => 'https://example.com/f/1',
					'filename'     => 'brief.pdf',
					'content_type' => 'application/pdf',
					'id'           => 'abc-123',
					'kind'         => 'pdf',
					'size'         => 1200,
				),
			),
		),
	)
);
amy_assert( 1 === count( $out ), 'empty content + valid attachment kept', 'count=' . count( $out ) );
amy_assert( isset( $out[0]['attachments'] ) && 1 === count( $out[0]['attachments'] ), 'attachments array present' );
if ( ! empty( $out[0]['attachments'][0] ) ) {
	$a = $out[0]['attachments'][0];
	amy_assert(
		isset( $a['url'], $a['filename'], $a['content_type'], $a['id'], $a['kind'], $a['size'] ),
		'attachment has AttachmentRef keys'
	);
	amy_assert( 'https://example.com/f/1' === $a['url'], 'url preserved' );
	amy_assert( 'brief.pdf' === $a['filename'], 'filename preserved' );
	amy_assert( 'application/pdf' === $a['content_type'], 'content_type preserved' );
	amy_assert( 'abc-123' === $a['id'], 'id preserved' );
	amy_assert( 'pdf' === $a['kind'], 'kind preserved' );
	amy_assert( 1200 === $a['size'], 'size preserved' );
	amy_assert( '' === $out[0]['content'], 'empty content kept as empty string' );
}

// 2) Empty content + no attachments → dropped.
$out = amy_test_sanitize_messages(
	array(
		array(
			'role'    => 'user',
			'content' => '',
		),
	)
);
amy_assert( 0 === count( $out ), 'empty content + no attachments dropped' );

// 3) Text + attachments → both kept.
$out = amy_test_sanitize_messages(
	array(
		array(
			'role'        => 'user',
			'content'     => 'Please review',
			'attachments' => array(
				array(
					'url'      => 'https://example.com/f/img.png',
					'filename' => 'shot.png',
					'kind'     => 'image',
				),
			),
		),
	)
);
amy_assert( 1 === count( $out ), 'text + attachments kept' );
amy_assert( 'Please review' === ( $out[0]['content'] ?? null ), 'content kept' );
amy_assert( 1 === count( $out[0]['attachments'] ?? array() ), 'attachments kept with text' );

// 4) Attachment missing url or filename → dropped from attachments; message kept if content non-empty.
$out = amy_test_sanitize_messages(
	array(
		array(
			'role'        => 'user',
			'content'     => 'hello',
			'attachments' => array(
				array(
					'url'      => 'https://example.com/ok.pdf',
					'filename' => 'ok.pdf',
				),
				array(
					'url'      => 'https://example.com/missing-name.pdf',
					'filename' => '',
				),
				array(
					'url'      => '',
					'filename' => 'missing-url.pdf',
				),
			),
		),
	)
);
amy_assert( 1 === count( $out ), 'message with text kept when some attachments invalid' );
amy_assert( 1 === count( $out[0]['attachments'] ?? array() ), 'only valid attachments retained' );
amy_assert( 'ok.pdf' === ( $out[0]['attachments'][0]['filename'] ?? null ), 'valid attachment filename' );

// 5) Cap at MAX_ATTACHMENTS_PER_MESSAGE (3).
$many = array();
for ( $i = 0; $i < 5; $i++ ) {
	$many[] = array(
		'url'      => "https://example.com/f/{$i}.pdf",
		'filename' => "f{$i}.pdf",
	);
}
$out = amy_test_sanitize_messages(
	array(
		array(
			'role'        => 'user',
			'content'     => 'many',
			'attachments' => $many,
		),
	)
);
amy_assert(
	Amy_Rest::MAX_ATTACHMENTS_PER_MESSAGE === count( $out[0]['attachments'] ?? array() ),
	'attachments capped at MAX_ATTACHMENTS_PER_MESSAGE'
);

// 6) Invalid role still dropped even with attachments.
$out = amy_test_sanitize_messages(
	array(
		array(
			'role'        => 'tool',
			'content'     => '',
			'attachments' => array(
				array(
					'url'      => 'https://example.com/f/1',
					'filename' => 'a.pdf',
				),
			),
		),
	)
);
amy_assert( 0 === count( $out ), 'invalid role dropped' );

echo "\n{$amy_test_passed} passed, {$amy_test_failed} failed\n";
exit( $amy_test_failed > 0 ? 1 : 0 );
