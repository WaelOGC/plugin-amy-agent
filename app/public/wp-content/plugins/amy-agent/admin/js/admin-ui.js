/**
 * Amy Agent — shared admin UI: (?) help popovers (click + hover, Esc, outside).
 */
(function () {
	'use strict';

	var HOVER_OPEN_MS = 120;
	var HOVER_CLOSE_MS = 180;
	var openTimer = null;
	var closeTimer = null;

	function qsa(sel, root) {
		return Array.prototype.slice.call((root || document).querySelectorAll(sel));
	}

	function clearTimers() {
		if (openTimer) {
			window.clearTimeout(openTimer);
			openTimer = null;
		}
		if (closeTimer) {
			window.clearTimeout(closeTimer);
			closeTimer = null;
		}
	}

	function getWrap(el) {
		return el && el.closest ? el.closest('[data-amy-admin-help]') : null;
	}

	function getParts(wrap) {
		if (!wrap) {
			return null;
		}
		return {
			wrap: wrap,
			btn: wrap.querySelector('[data-amy-admin-help-btn]'),
			panel: wrap.querySelector('[data-amy-admin-help-panel]'),
		};
	}

	function closeHelp(wrap, restoreFocus) {
		var parts = getParts(wrap);
		if (!parts || !parts.panel || !parts.btn) {
			return;
		}
		if (parts.panel.hidden && !parts.wrap.classList.contains('is-open')) {
			return;
		}
		parts.panel.hidden = true;
		parts.wrap.classList.remove('is-open');
		parts.btn.setAttribute('aria-expanded', 'false');
		if (restoreFocus) {
			parts.btn.focus();
		}
	}

	function closeAll(except, restoreFocus) {
		qsa('[data-amy-admin-help].is-open').forEach(function (wrap) {
			if (except && wrap === except) {
				return;
			}
			closeHelp(wrap, false);
		});
		if (restoreFocus && except) {
			var parts = getParts(except);
			if (parts && parts.btn) {
				parts.btn.focus();
			}
		}
	}

	function openHelp(wrap) {
		var parts = getParts(wrap);
		if (!parts || !parts.panel || !parts.btn) {
			return;
		}
		closeAll(wrap, false);
		parts.panel.hidden = false;
		parts.wrap.classList.add('is-open');
		parts.btn.setAttribute('aria-expanded', 'true');
	}

	function toggleHelp(wrap) {
		if (!wrap) {
			return;
		}
		if (wrap.classList.contains('is-open')) {
			closeHelp(wrap, false);
		} else {
			openHelp(wrap);
		}
	}

	function init() {
		document.addEventListener('click', function (event) {
			var btn = event.target.closest('[data-amy-admin-help-btn]');
			if (btn) {
				event.preventDefault();
				clearTimers();
				toggleHelp(getWrap(btn));
				return;
			}
			if (!event.target.closest('[data-amy-admin-help]')) {
				clearTimers();
				closeAll(null, false);
			}
		});

		document.addEventListener('keydown', function (event) {
			if (event.key !== 'Escape') {
				return;
			}
			var open = document.querySelector('[data-amy-admin-help].is-open');
			if (!open) {
				return;
			}
			event.preventDefault();
			clearTimers();
			closeHelp(open, true);
		});

		document.addEventListener('mouseover', function (event) {
			var wrap = getWrap(event.target);
			if (!wrap) {
				return;
			}
			clearTimers();
			openTimer = window.setTimeout(function () {
				openHelp(wrap);
			}, HOVER_OPEN_MS);
		});

		document.addEventListener('mouseout', function (event) {
			var wrap = getWrap(event.target);
			if (!wrap) {
				return;
			}
			var related = event.relatedTarget;
			if (related && wrap.contains(related)) {
				return;
			}
			clearTimers();
			closeTimer = window.setTimeout(function () {
				closeHelp(wrap, false);
			}, HOVER_CLOSE_MS);
		});
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}
})();
