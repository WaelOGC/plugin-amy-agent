/**
 * Contract tests for public-chat upload error messaging (widget.js).
 *
 * Run: node tests/test-upload-rate-limit-message.js
 *
 * Mirrors the selection used in uploadPendingFile(): 429 / error=rate_limited
 * → uploadRateLimited; every other failure → uploadFailed.
 */

'use strict';

var fs = require('fs');
var path = require('path');

var FAILED = 'Could not upload that file.';
var RATE_LIMITED = "You've reached the upload limit for now, please try again in a bit.";

var i18n = {
	uploadFailed: FAILED,
	uploadRateLimited: RATE_LIMITED,
};

/**
 * Same selection rules as widget.js uploadPendingFile failure branch.
 *
 * @param {{ status?: number, data?: { error?: string }|null }} result
 * @param {{ uploadFailed?: string, uploadRateLimited?: string }} strings
 * @return {string}
 */
function resolveUploadErrorMessage(result, strings) {
	var rateLimited =
		result.status === 429 ||
		(result.data && result.data.error === 'rate_limited');
	return rateLimited
		? strings.uploadRateLimited || RATE_LIMITED
		: strings.uploadFailed || 'Upload failed.';
}

var failures = 0;

function assert(cond, msg) {
	if (!cond) {
		failures += 1;
		console.error('FAIL:', msg);
	} else {
		console.log('ok:', msg);
	}
}

assert(
	resolveUploadErrorMessage({ status: 429, data: { error: 'rate_limited' } }, i18n) ===
		RATE_LIMITED,
	'429 + rate_limited → uploadRateLimited'
);

assert(
	resolveUploadErrorMessage({ status: 429, data: null }, i18n) === RATE_LIMITED,
	'429 alone → uploadRateLimited'
);

assert(
	resolveUploadErrorMessage(
		{ status: 400, data: { error: 'rate_limited' } },
		i18n
	) === RATE_LIMITED,
	'error=rate_limited without 429 → uploadRateLimited'
);

assert(
	resolveUploadErrorMessage(
		{ status: 400, data: { error: 'invalid_request' } },
		i18n
	) === FAILED,
	'validation error → uploadFailed'
);

assert(
	resolveUploadErrorMessage({ status: 500, data: null }, i18n) === FAILED,
	'server error → uploadFailed'
);

assert(
	resolveUploadErrorMessage({ status: 413, data: { error: 'too_large' } }, i18n) ===
		FAILED,
	'413 → uploadFailed'
);

var pluginRoot = path.join(__dirname, '..');
var widgetSrc = fs.readFileSync(
	path.join(pluginRoot, 'public/js/widget.js'),
	'utf8'
);
var assetsSrc = fs.readFileSync(
	path.join(pluginRoot, 'includes/class-amy-assets.php'),
	'utf8'
);

assert(
	widgetSrc.indexOf('uploadRateLimited') !== -1,
	'widget.js references uploadRateLimited'
);
assert(
	widgetSrc.indexOf("result.data.error === 'rate_limited'") !== -1,
	'widget.js checks error === rate_limited'
);
assert(
	widgetSrc.indexOf('result.status === 429') !== -1,
	'widget.js checks status === 429'
);
assert(
	assetsSrc.indexOf("'uploadRateLimited'") !== -1,
	'class-amy-assets.php localizes uploadRateLimited'
);
assert(
	assetsSrc.indexOf(RATE_LIMITED) !== -1,
	'class-amy-assets.php English default matches'
);

if (failures > 0) {
	console.error('\n' + failures + ' failure(s)');
	process.exit(1);
}
console.log('\nAll upload rate-limit message checks passed.');
