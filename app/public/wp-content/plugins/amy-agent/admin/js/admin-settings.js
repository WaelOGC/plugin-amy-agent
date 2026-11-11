/**
 * Amy Agent — Settings: tabs, connection health check, From-email validation hint.
 */
(function () {
	'use strict';

	var cfg = window.amyAgentSettings || {};
	var blockedHosts = cfg.blockedFromHosts || [
		'gmail.com',
		'googlemail.com',
		'agentmail.to',
		'yahoo.com',
		'outlook.com',
		'hotmail.com',
		'live.com',
		'icloud.com',
	];
	var i18n = cfg.i18n || {};

	function qs(sel, root) {
		return (root || document).querySelector(sel);
	}

	function qsa(sel, root) {
		return Array.prototype.slice.call((root || document).querySelectorAll(sel));
	}

	function setActiveTab(tabId) {
		qsa('.amy-agent-settings__tab').forEach(function (btn) {
			var active = btn.getAttribute('data-amy-settings-tab') === tabId;
			btn.classList.toggle('is-active', active);
			btn.setAttribute('aria-selected', active ? 'true' : 'false');
		});
		qsa('.amy-agent-settings__panel').forEach(function (panel) {
			var match = panel.id === 'amy-settings-panel-' + tabId;
			panel.hidden = !match;
		});
		try {
			if (window.history && window.history.replaceState) {
				var url = new URL(window.location.href);
				url.searchParams.set('tab', tabId);
				window.history.replaceState({}, '', url.toString());
			}
			// Keep Settings API redirect on the same tab after save.
			var referer = qs('input[name="_wp_http_referer"]');
			if (referer) {
				var refUrl = new URL(referer.value, window.location.origin);
				refUrl.searchParams.set('tab', tabId);
				referer.value = refUrl.pathname + refUrl.search + refUrl.hash;
			}
		} catch (e) {
			/* ignore */
		}
	}

	function initTabs() {
		var tabs = qsa('.amy-agent-settings__tab');
		if (!tabs.length) {
			return;
		}

		var initial = 'general';
		try {
			var fromUrl = new URL(window.location.href).searchParams.get('tab');
			if (fromUrl === 'connection' || fromUrl === 'general') {
				initial = fromUrl;
			}
		} catch (e) {
			/* ignore */
		}
		setActiveTab(initial);

		tabs.forEach(function (btn) {
			btn.addEventListener('click', function () {
				var id = btn.getAttribute('data-amy-settings-tab') || 'general';
				setActiveTab(id);
			});
		});
	}

	function hostFromEmail(email) {
		var at = String(email || '').lastIndexOf('@');
		if (at < 0) {
			return '';
		}
		return String(email)
			.slice(at + 1)
			.trim()
			.toLowerCase();
	}

	function initFromValidation() {
		var input = qs('#amy_agent_marketing_from_email');
		var err = qs('#amy-settings-from-error');
		if (!input || !err) {
			return;
		}

		function validate() {
			var email = String(input.value || '').trim();
			var host = hostFromEmail(email);
			var blocked = host && blockedHosts.indexOf(host) !== -1;
			input.classList.toggle('is-invalid', !!blocked);
			if (blocked) {
				err.textContent =
					i18n.fromBlocked ||
					'Marketing From cannot be personal Gmail, AgentMail, or free webmail. Use a domain mailbox such as hello@ogcnewfinity.com.';
				err.hidden = false;
			} else {
				err.textContent = '';
				err.hidden = true;
			}
		}

		input.addEventListener('input', validate);
		input.addEventListener('blur', validate);
		validate();
	}

	function describeHealth(data) {
		if (!data || typeof data !== 'object') {
			return {
				ok: false,
				text: i18n.healthFail || 'Health check failed.',
			};
		}

		var settings = data.settings || {};
		var parts = [];

		if (!settings.service_configured) {
			parts.push(i18n.needUrlSecret || 'Set service URL and shared secret first.');
		} else if (data.ok) {
			parts.push(i18n.healthOk || 'Python service reachable.');
		} else {
			parts.push(i18n.healthUnreachable || 'Python service unreachable (check URL, secret, and Dokploy).');
		}

		if (settings.enabled) {
			parts.push(i18n.enabledOn || 'Enable Amy is on.');
		} else {
			parts.push(i18n.enabledOff || 'Enable Amy is off — widget and Submit Idea stay hidden.');
		}

		if (settings.has_api_key) {
			parts.push(
				(i18n.providerLabel || 'Provider:') + ' ' + (settings.provider || '—') + ' (' + (i18n.keySaved || 'key saved') + ')'
			);
		} else {
			parts.push(i18n.noApiKey || 'AI API key not set.');
		}

		if (data.plugin_version) {
			parts.push((i18n.pluginVersion || 'Plugin') + ' ' + data.plugin_version);
		}

		return {
			ok: !!data.ok,
			text: parts.join(' '),
		};
	}

	function initHealthCheck() {
		var btn = qs('#amy-settings-health-check');
		var status = qs('#amy-settings-health-status');
		if (!btn || !status || !cfg.healthUrl) {
			return;
		}

		btn.addEventListener('click', function () {
			btn.disabled = true;
			status.hidden = false;
			status.classList.remove('is-ok', 'is-bad');
			status.textContent = i18n.healthChecking || 'Checking connection…';

			fetch(cfg.healthUrl, {
				method: 'GET',
				credentials: 'same-origin',
				headers: {
					Accept: 'application/json',
					'X-WP-Nonce': cfg.restNonce || '',
				},
			})
				.then(function (res) {
					return res.json().then(function (body) {
						return { status: res.status, body: body };
					});
				})
				.then(function (result) {
					var info = describeHealth(result.body);
					status.classList.add(info.ok ? 'is-ok' : 'is-bad');
					status.textContent = info.text;
				})
				.catch(function () {
					status.classList.add('is-bad');
					status.textContent = i18n.healthFail || 'Health check failed. Could not reach WordPress REST.';
				})
				.finally(function () {
					btn.disabled = false;
				});
		});
	}

	document.addEventListener('DOMContentLoaded', function () {
		if (!qs('.amy-agent-settings')) {
			return;
		}
		initTabs();
		initFromValidation();
		initHealthCheck();
	});
})();
