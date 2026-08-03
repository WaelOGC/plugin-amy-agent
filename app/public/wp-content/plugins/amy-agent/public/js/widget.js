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
		var avatarUrl = cfg.avatarUrl || '';
		var avatarImg = avatarUrl
			? '<img class="amy-agent-avatar amy-agent-avatar--launcher" src="' +
			  escapeHtml(avatarUrl) +
			  '" alt="" width="56" height="56" decoding="async" />'
			: '';
		var headerAvatar = avatarUrl
			? '<img class="amy-agent-avatar amy-agent-avatar--header" src="' +
			  escapeHtml(avatarUrl) +
			  '" alt="" width="40" height="40" decoding="async" />'
			: '';

		root.innerHTML =
			'<button type="button" class="amy-agent-launcher" aria-expanded="false" aria-controls="amy-agent-panel" title="' +
			escapeHtml(cfg.i18n.open) +
			'">' +
			avatarImg +
			'</button>' +
			'<div id="amy-agent-panel" class="amy-agent-panel" role="dialog" aria-label="' +
			escapeHtml(cfg.i18n.title) +
			'" hidden>' +
			'<div class="amy-agent-header">' +
			'<div class="amy-agent-header__brand">' +
			headerAvatar +
			'<div class="amy-agent-header__titles">' +
			'<p class="amy-agent-header__title">' +
			escapeHtml(cfg.i18n.title) +
			'</p>' +
			'<p class="amy-agent-header__subtitle">' +
			escapeHtml(cfg.i18n.subtitle) +
			'</p>' +
			'</div>' +
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

		/**
		 * Safe Markdown → HTML for assistant bubbles.
		 * Escapes raw HTML first, then applies a small allowlist of transforms.
		 */
		function renderMarkdown(text) {
			var escaped = escapeHtml(String(text || ''));
			var lines = escaped.split(/\r?\n/);
			var html = [];
			var i = 0;

			function formatInline(line) {
				var out = '';
				var rest = line;
				var boldRe = /\*\*(.+?)\*\*/;
				var urlRe = /(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"]?)/;

				while (rest.length) {
					var boldMatch = rest.match(boldRe);
					var urlMatch = rest.match(urlRe);
					var nextIndex = rest.length;
					var kind = null;
					var match = null;

					if (boldMatch && boldMatch.index < nextIndex) {
						nextIndex = boldMatch.index;
						kind = 'bold';
						match = boldMatch;
					}
					if (urlMatch && urlMatch.index < nextIndex) {
						nextIndex = urlMatch.index;
						kind = 'url';
						match = urlMatch;
					}

					if (!kind) {
						out += rest;
						break;
					}

					out += rest.slice(0, nextIndex);
					if (kind === 'bold') {
						out += '<strong>' + match[1] + '</strong>';
					} else {
						var href = match[1];
						out +=
							'<a href="' +
							href +
							'" target="_blank" rel="noopener noreferrer">' +
							href +
							'</a>';
					}
					rest = rest.slice(nextIndex + match[0].length);
				}

				return out;
			}

			while (i < lines.length) {
				var line = lines[i];

				if (/^\s*$/.test(line)) {
					i += 1;
					continue;
				}

				var ulMatch = line.match(/^[\-\*]\s+(.+)$/);
				var olMatch = line.match(/^\d+\.\s+(.+)$/);

				if (ulMatch) {
					html.push('<ul>');
					while (i < lines.length) {
						var uItem = lines[i].match(/^[\-\*]\s+(.+)$/);
						if (!uItem) {
							break;
						}
						html.push('<li>' + formatInline(uItem[1]) + '</li>');
						i += 1;
					}
					html.push('</ul>');
					continue;
				}

				if (olMatch) {
					html.push('<ol>');
					while (i < lines.length) {
						var oItem = lines[i].match(/^\d+\.\s+(.+)$/);
						if (!oItem) {
							break;
						}
						html.push('<li>' + formatInline(oItem[1]) + '</li>');
						i += 1;
					}
					html.push('</ol>');
					continue;
				}

				var para = [formatInline(line)];
				i += 1;
				while (i < lines.length) {
					var next = lines[i];
					if (/^\s*$/.test(next)) {
						break;
					}
					if (/^[\-\*]\s+/.test(next) || /^\d+\.\s+/.test(next)) {
						break;
					}
					para.push(formatInline(next));
					i += 1;
				}
				html.push('<p>' + para.join('<br>') + '</p>');
			}

			return html.join('') || '<p></p>';
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
			if (kind === 'assistant') {
				el.innerHTML = renderMarkdown(text);
			} else {
				el.textContent = text;
			}
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
