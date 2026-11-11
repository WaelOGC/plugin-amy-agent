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

	function tabForHash(hash) {
		var h = String(hash || '').replace(/^#/, '');
		if (h === 'telegram') {
			return 'telegram';
		}
		if (h === 'connection' || h === 'ai-key') {
			return 'connection';
		}
		if (h === 'general-from' || h === 'general-from-playbook' || h === 'enable-amy') {
			return 'general';
		}
		return '';
	}

	function scrollToHashTarget(hash) {
		var id = String(hash || '').replace(/^#/, '');
		if (!id) {
			return;
		}
		var el = document.getElementById(id);
		if (el && typeof el.scrollIntoView === 'function') {
			window.setTimeout(function () {
				el.scrollIntoView({ behavior: 'smooth', block: 'start' });
			}, 60);
		}
	}

	function initTabs() {
		var tabs = qsa('.amy-agent-settings__tab');
		if (!tabs.length) {
			return;
		}

		var initial = 'general';
		var hash = '';
		try {
			var url = new URL(window.location.href);
			var fromUrl = url.searchParams.get('tab');
			hash = url.hash || window.location.hash || '';
			var fromHash = tabForHash(hash);
			if (fromUrl === 'connection' || fromUrl === 'general' || fromUrl === 'telegram') {
				initial = fromUrl;
			} else if (fromHash) {
				initial = fromHash;
			}
		} catch (e) {
			/* ignore */
		}
		setActiveTab(initial);
		if (hash) {
			scrollToHashTarget(hash);
		}

		tabs.forEach(function (btn) {
			btn.addEventListener('click', function () {
				var id = btn.getAttribute('data-amy-settings-tab') || 'general';
				setActiveTab(id);
				if (id === 'telegram') {
					loadTelegramStatus();
				}
			});
		});

		// Readiness deep-links on the same page: switch tab + scroll without full reload.
		qsa('.amy-agent-settings__readiness-link').forEach(function (link) {
			link.addEventListener('click', function (ev) {
				var href = link.getAttribute('href') || '';
				var tab = '';
				var frag = '';
				try {
					var u = new URL(href, window.location.origin);
					tab = u.searchParams.get('tab') || '';
					frag = u.hash || '';
					if (!tab) {
						tab = tabForHash(frag);
					}
				} catch (err) {
					return;
				}
				if (!tab || !qs('#amy-settings-panel-' + tab)) {
					return;
				}
				ev.preventDefault();
				setActiveTab(tab);
				if (tab === 'telegram') {
					loadTelegramStatus();
				}
				if (frag) {
					scrollToHashTarget(frag);
					try {
						if (window.history && window.history.replaceState) {
							var next = new URL(window.location.href);
							next.searchParams.set('tab', tab);
							next.hash = frag.replace(/^#/, '');
							window.history.replaceState({}, '', next.toString());
						}
					} catch (err2) {
						/* ignore */
					}
				}
			});
		});
	}

	function reindexTelegramAdmins() {
		var rows = qsa('#amy-telegram-admins-body [data-amy-admin-row]');
		rows.forEach(function (row, index) {
			var tid = row.querySelector('[data-field="telegram_id"]') || row.querySelector('input[name*="[telegram_id]"]');
			var lab = row.querySelector('[data-field="label"]') || row.querySelector('input[name*="[label]"]');
			var uid = row.querySelector('[data-field="wp_user_id"]') || row.querySelector('select[name*="[wp_user_id]"]');
			if (tid) {
				tid.name = 'amy_agent_telegram_admins[' + index + '][telegram_id]';
			}
			if (lab) {
				lab.name = 'amy_agent_telegram_admins[' + index + '][label]';
			}
			if (uid) {
				uid.name = 'amy_agent_telegram_admins[' + index + '][wp_user_id]';
			}
		});
	}

	function initTelegramAdminsTable() {
		var addBtn = qs('#amy-telegram-add-admin');
		var body = qs('#amy-telegram-admins-body');
		var tpl = qs('#amy-telegram-admin-row-template');
		if (!addBtn || !body || !tpl) {
			return;
		}

		function bindRemove(row) {
			var btn = qs('[data-amy-remove-admin]', row);
			if (btn) {
				btn.addEventListener('click', function () {
					row.remove();
					reindexTelegramAdmins();
				});
			}
		}

		qsa('#amy-telegram-admins-body [data-amy-admin-row]').forEach(bindRemove);

		addBtn.addEventListener('click', function () {
			var count = qsa('#amy-telegram-admins-body [data-amy-admin-row]').length;
			if (count >= 10) {
				showTelegramFeedback(i18n.tgMaxAdmins || 'Maximum 10 admins.', true);
				return;
			}
			var row = tpl.content.cloneNode(true).querySelector('tr');
			body.appendChild(row);
			bindRemove(row);
			reindexTelegramAdmins();
		});

		var form = qs('.amy-agent-settings__form');
		if (form) {
			form.addEventListener('submit', function () {
				reindexTelegramAdmins();
			});
		}
	}

	function showTelegramFeedback(message, isError) {
		var el = qs('#amy-settings-telegram-feedback');
		if (!el) {
			return;
		}
		el.hidden = false;
		el.textContent = message;
		el.classList.toggle('is-error', !!isError);
		el.classList.toggle('is-ok', !isError);
	}

	function telegramHasUnsavedToken() {
		var input = qs('[data-amy-tg-token-input]');
		if (!input) {
			return false;
		}
		return String(input.value || '').trim() !== '';
	}

	function telegramAjax(action, loadingText) {
		if (!cfg.ajaxUrl || !cfg.telegramNonce) {
			return Promise.reject(new Error('missing config'));
		}
		if (telegramHasUnsavedToken()) {
			showTelegramFeedback(i18n.tgSaveFirst || 'Save settings first so the bot token is stored.', true);
			return Promise.reject(new Error('unsaved'));
		}
		showTelegramFeedback(loadingText || '', false);
		var body = new URLSearchParams();
		body.set('action', action);
		body.set('nonce', cfg.telegramNonce);
		return fetch(cfg.ajaxUrl, {
			method: 'POST',
			credentials: 'same-origin',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
			body: body.toString(),
		}).then(function (res) {
			return res.json().then(function (data) {
				return { status: res.status, data: data };
			});
		});
	}

	function renderTelegramStatus(data) {
		var el = qs('#amy-settings-telegram-status');
		if (!el || !data) {
			return;
		}
		var parts = [];
		if (data.username) {
			parts.push('@' + data.username);
		}
		var state = data.webhook_state || 'not_connected';
		var badgeClass = 'amy-agent-settings__tg-badge--amber';
		var stateLabel = i18n.tgNotConnected || 'Not connected';
		if (state === 'connected') {
			badgeClass = 'amy-agent-settings__tg-badge--green';
			stateLabel = i18n.tgConnected || 'Connected';
		} else if (state === 'error') {
			badgeClass = 'amy-agent-settings__tg-badge--red';
			stateLabel = (i18n.tgError || 'Error') + (data.last_error ? ': ' + data.last_error : '');
		}
		el.innerHTML =
			parts.join(' ') +
			' <span class="amy-agent-settings__tg-badge ' +
			badgeClass +
			'">' +
			stateLabel +
			'</span>' +
			(data.pending !== null && data.pending !== undefined ? ' · pending: ' + data.pending : '');

		var nextSteps = qs('#amy-settings-telegram-next-steps');
		if (nextSteps) {
			nextSteps.hidden = state === 'connected';
		}
	}

	function loadTelegramStatus() {
		var el = qs('#amy-settings-telegram-status');
		if (el) {
			el.textContent = i18n.tgStatusLoading || 'Loading Telegram status…';
		}
		telegramAjax('amy_telegram_status', '')
			.then(function (result) {
				if (result.data && result.data.success && result.data.data) {
					renderTelegramStatus(result.data.data);
				} else {
					showTelegramFeedback(
						(result.data && result.data.data && result.data.data.message) ||
							i18n.tgStatusFailed ||
							'Status request failed. Save settings, then reload Amy → Settings → Telegram.',
						true
					);
					var nextSteps = qs('#amy-settings-telegram-next-steps');
					if (nextSteps) {
						nextSteps.hidden = false;
					}
				}
			})
			.catch(function () {
				/* unsaved or network */
			});
	}

	function initTelegramActions() {
		var connect = qs('#amy-settings-telegram-connect');
		var disconnect = qs('#amy-settings-telegram-disconnect');
		var test = qs('#amy-settings-telegram-test');
		if (!connect && !disconnect && !test) {
			return;
		}

		if (connect) {
			connect.addEventListener('click', function () {
				if (!cfg.isHttps) {
					showTelegramFeedback(i18n.tgHttpsRequired || 'HTTPS required.', true);
					return;
				}
				connect.disabled = true;
				telegramAjax('amy_telegram_connect', i18n.tgConnecting || 'Connecting…')
					.then(function (result) {
						if (result.data && result.data.success) {
							showTelegramFeedback(result.data.data.message || 'Connected.', false);
							loadTelegramStatus();
						} else {
							showTelegramFeedback(
								(result.data && result.data.data && result.data.data.message) ||
									i18n.tgConnectFailed ||
									'Connect failed. Check token, Enable Telegram Admin Bot, HTTPS, then Connect again under Settings → Telegram.',
								true
							);
						}
					})
					.catch(function () {})
					.finally(function () {
						connect.disabled = !cfg.isHttps;
					});
			});
		}

		if (disconnect) {
			disconnect.addEventListener('click', function () {
				disconnect.disabled = true;
				telegramAjax('amy_telegram_disconnect', i18n.tgDisconnecting || 'Disconnecting…')
					.then(function (result) {
						if (result.data && result.data.success) {
							showTelegramFeedback(result.data.data.message || 'Disconnected.', false);
							loadTelegramStatus();
						} else {
							showTelegramFeedback(
								(result.data && result.data.data && result.data.data.message) || 'Disconnect failed.',
								true
							);
						}
					})
					.finally(function () {
						disconnect.disabled = false;
					});
			});
		}

		if (test) {
			test.addEventListener('click', function () {
				test.disabled = true;
				telegramAjax('amy_telegram_test', i18n.tgTesting || 'Sending test messages…')
					.then(function (result) {
						if (result.data && result.data.success && result.data.data && result.data.data.results) {
							var lines = result.data.data.results.map(function (r) {
								return (r.label || r.telegram_id) + ': ' + (r.ok ? 'OK' : r.error || 'failed');
							});
							showTelegramFeedback(lines.join(' · ') || 'Done.', false);
						} else {
							showTelegramFeedback(
								(result.data && result.data.data && result.data.data.message) ||
									i18n.tgTestFailed ||
									'Test failed. Enable the bot, save a BotFather token, add at least one numeric admin ID, then Send test message under Settings → Telegram.',
								true
							);
						}
					})
					.finally(function () {
						test.disabled = false;
					});
			});
		}

		try {
			var tab = new URL(window.location.href).searchParams.get('tab');
			if (tab === 'telegram') {
				loadTelegramStatus();
			}
		} catch (e) {
			/* ignore */
		}
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
					'Marketing From cannot be personal Gmail, AgentMail, or free webmail. Use your own domain mailbox authorized in FluentSMTP.';
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
			parts.push(i18n.healthUnreachable || 'Python service unreachable (check URL, secret, and your Amy Python service host).');
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
		initTelegramAdminsTable();
		initTelegramActions();
	});
})();
