/**
 * Site-wide visitor tracking beacon.
 *
 * Public contract: window.amyTrack(eventType, data)
 * Other scripts (widget, Submit Idea, theme contact form) must call this —
 * they must not implement their own fetch/session logic.
 */
(function () {
	'use strict';

	var STORAGE_KEY = 'amy_session_id';
	var cfg = window.amyAgentTracking || {};
	var restUrl = cfg.restUrl || '';
	var nonce = cfg.nonce || '';
	var ABANDON_TYPES = {
		submit_idea_abandoned: true,
		contact_form_abandoned: true,
	};

	function uuid() {
		if (window.crypto && typeof window.crypto.randomUUID === 'function') {
			return window.crypto.randomUUID();
		}
		return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
			var r = (Math.random() * 16) | 0;
			var v = c === 'x' ? r : (r & 0x3) | 0x8;
			return v.toString(16);
		});
	}

	function getSessionId() {
		try {
			var existing = window.sessionStorage.getItem(STORAGE_KEY);
			if (existing) {
				return existing;
			}
			var id = uuid();
			window.sessionStorage.setItem(STORAGE_KEY, id);
			return id;
		} catch (err) {
			return uuid();
		}
	}

	var sessionId = getSessionId();

	function currentPath() {
		try {
			return window.location.pathname || '/';
		} catch (err) {
			return '/';
		}
	}

	function buildPayload(eventType, data) {
		var body = {
			session_id: sessionId,
			event_type: eventType,
			page_path: currentPath(),
		};
		if (data && typeof data === 'object') {
			body.event_data = data;
		}
		return body;
	}

	function withNonce(url) {
		if (!url || !nonce) {
			return url;
		}
		return url + (url.indexOf('?') >= 0 ? '&' : '?') + '_wpnonce=' + encodeURIComponent(nonce);
	}

	function sendFetch(body) {
		if (!restUrl) {
			return;
		}
		fetch(restUrl, {
			method: 'POST',
			credentials: 'same-origin',
			headers: {
				'Content-Type': 'application/json',
				Accept: 'application/json',
				'X-WP-Nonce': nonce,
			},
			body: JSON.stringify(body),
			keepalive: true,
		}).catch(function () {
			/* tracking must never break the page */
		});
	}

	function sendViaBeacon(body) {
		if (!restUrl) {
			return;
		}
		var url = withNonce(restUrl);
		try {
			if (navigator.sendBeacon) {
				var blob = new Blob([JSON.stringify(body)], { type: 'application/json' });
				if (navigator.sendBeacon(url, blob)) {
					return;
				}
			}
		} catch (err) {
			/* fall through to fetch */
		}
		sendFetch(body);
	}

	window.amyTrack = function (eventType, data) {
		if (!eventType || typeof eventType !== 'string') {
			return;
		}
		var body = buildPayload(eventType, data);
		if (ABANDON_TYPES[eventType]) {
			sendViaBeacon(body);
		} else {
			sendFetch(body);
		}
	};

	function firePageView() {
		window.amyTrack('page_view');
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', firePageView);
	} else {
		firePageView();
	}
})();
