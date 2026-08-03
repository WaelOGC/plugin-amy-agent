/**
 * Amy Agent floating chat widget (vanilla JS).
 */
(function () {
	'use strict';

	var cfg = window.amyAgentWidget;
	if (!cfg || !cfg.restUrl) {
		return;
	}

	document.addEventListener('DOMContentLoaded', function () {
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

		var sessionId = uuid();
		var messages = [];
		var busy = false;

		var root = document.getElementById('amy-agent-root');
		if (!root) {
			return;
		}

		root.hidden = false;
		root.innerHTML =
			'<button type="button" class="amy-agent-launcher" aria-expanded="false" aria-controls="amy-agent-panel" title="' +
			escapeHtml(cfg.i18n.open) +
			'">' +
			'<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.75">' +
			'<path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6A2.5 2.5 0 0 1 16.5 15H13l-3.5 3.5V15H7.5A2.5 2.5 0 0 1 5 12.5v-6Z"/>' +
			'<circle cx="9" cy="9.5" r="0.9" fill="currentColor" stroke="none"/>' +
			'<circle cx="12" cy="9.5" r="0.9" fill="currentColor" stroke="none"/>' +
			'<circle cx="15" cy="9.5" r="0.9" fill="currentColor" stroke="none"/>' +
			'</svg>' +
			'</button>' +
			'<div id="amy-agent-panel" class="amy-agent-panel" role="dialog" aria-label="' +
			escapeHtml(cfg.i18n.title) +
			'" hidden>' +
			'<div class="amy-agent-header">' +
			'<div class="amy-agent-header__titles">' +
			'<p class="amy-agent-header__title">' +
			escapeHtml(cfg.i18n.title) +
			'</p>' +
			'<p class="amy-agent-header__subtitle">' +
			escapeHtml(cfg.i18n.subtitle) +
			'</p>' +
			'</div>' +
			'<button type="button" class="amy-agent-header__close" aria-label="' +
			escapeHtml(cfg.i18n.close) +
			'">×</button>' +
			'</div>' +
			'<div class="amy-agent-messages" data-amy-messages></div>' +
			'<form class="amy-agent-form" data-amy-form>' +
			'<input class="amy-agent-form__input" type="text" name="message" autocomplete="off" maxlength="2000" placeholder="' +
			escapeHtml(cfg.i18n.placeholder) +
			'" data-amy-input />' +
			'<button class="amy-agent-form__send" type="submit" data-amy-send>' +
			escapeHtml(cfg.i18n.send) +
			'</button>' +
			'</form>' +
			'</div>';

		var launcher = root.querySelector('.amy-agent-launcher');
		var panel = root.querySelector('.amy-agent-panel');
		var closeBtn = root.querySelector('.amy-agent-header__close');
		var messagesEl = root.querySelector('[data-amy-messages]');
		var form = root.querySelector('[data-amy-form]');
		var input = root.querySelector('[data-amy-input]');
		var sendBtn = root.querySelector('[data-amy-send]');

		appendBubble(cfg.i18n.greeting, 'assistant');

		function escapeHtml(str) {
			return String(str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');
		}

		function setOpen(open) {
			root.classList.toggle('is-open', open);
			panel.hidden = !open;
			launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
			launcher.setAttribute('title', open ? cfg.i18n.close : cfg.i18n.open);
			if (open) {
				input.focus();
			}
		}

		function appendBubble(text, kind) {
			var el = document.createElement('div');
			el.className = 'amy-agent-bubble amy-agent-bubble--' + kind;
			el.textContent = text;
			messagesEl.appendChild(el);
			messagesEl.scrollTop = messagesEl.scrollHeight;
			return el;
		}

		function setBusy(next) {
			busy = next;
			sendBtn.disabled = next;
			input.disabled = next;
		}

		launcher.addEventListener('click', function () {
			setOpen(!root.classList.contains('is-open'));
		});

		closeBtn.addEventListener('click', function () {
			setOpen(false);
		});

		form.addEventListener('submit', function (event) {
			event.preventDefault();
			if (busy) {
				return;
			}

			var text = (input.value || '').trim();
			if (!text) {
				return;
			}

			input.value = '';
			appendBubble(text, 'user');
			messages.push({ role: 'user', content: text });

			var thinking = appendBubble(cfg.i18n.thinking, 'status');
			setBusy(true);

			fetch(cfg.restUrl, {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-WP-Nonce': cfg.nonce,
				},
				body: JSON.stringify({
					session_id: sessionId,
					mode: 'general',
					messages: messages,
					page: {
						url: cfg.pageUrl || window.location.href,
						slug: cfg.pageSlug || '',
					},
					context: {},
				}),
			})
				.then(function (res) {
					return res.json().then(function (data) {
						return { ok: res.ok, status: res.status, data: data };
					}).catch(function () {
						return { ok: false, status: res.status, data: null };
					});
				})
				.then(function (result) {
					thinking.remove();
					if (
						result.ok &&
						result.data &&
						result.data.reply &&
						typeof result.data.reply.content === 'string'
					) {
						var reply = result.data.reply.content;
						appendBubble(reply, 'assistant');
						messages.push({ role: 'assistant', content: reply });
						return;
					}
					appendBubble(cfg.i18n.unavailable, 'status');
				})
				.catch(function () {
					thinking.remove();
					appendBubble(cfg.i18n.unavailable, 'status');
				})
				.finally(function () {
					setBusy(false);
					input.focus();
				});
		});
	});
})();
