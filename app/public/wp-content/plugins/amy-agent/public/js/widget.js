/**
 * Amy Agent floating chat widget (vanilla JS).
 * Public chat only — visitor-scoped conversations, history, expand mode.
 */
(function () {
	'use strict';

	var cfg = window.amyAgentWidget;
	if (!cfg || !cfg.restUrl) {
		return;
	}

	var EXPAND_MQ = '(min-width: 1024px)';
	var LS_VISITOR = 'amyAgentVisitorId';
	var LS_CONV = 'amyAgentConversationId';
	var LS_EXPAND = 'amyAgentWidgetExpanded';

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

		function escapeHtml(str) {
			return String(str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');
		}

		function iconSvg(name) {
			var common =
				'xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
			if (name === 'history') {
				return (
					'<svg ' +
					common +
					'><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
				);
			}
			if (name === 'new') {
				return (
					'<svg ' +
					common +
					'><path d="M12 5v14M5 12h14"/></svg>'
				);
			}
			if (name === 'expand') {
				return (
					'<svg ' +
					common +
					'><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>'
				);
			}
			if (name === 'collapse') {
				return (
					'<svg ' +
					common +
					'><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="10" y1="14" x2="3" y2="21"/><line x1="14" y1="10" x2="21" y2="3"/></svg>'
				);
			}
			return '×';
		}

		var sessionId = uuid();
		var busy = false;
		var showingHistory = false;
		var expanded = false;
		var lastDateKey = null;
		var focusBeforeExpand = null;
		var reduceMotion = false;
		try {
			reduceMotion =
				window.matchMedia &&
				window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		} catch (e) {
			reduceMotion = false;
		}

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

		var i18n = cfg.i18n || {};

		root.innerHTML =
			'<button type="button" class="amy-agent-launcher" aria-expanded="false" aria-controls="amy-agent-panel" title="' +
			escapeHtml(i18n.open) +
			'">' +
			avatarImg +
			'</button>' +
			'<div class="amy-agent-backdrop" data-amy-backdrop hidden></div>' +
			'<div id="amy-agent-panel" class="amy-agent-panel" role="dialog" aria-modal="false" aria-label="' +
			escapeHtml(i18n.title) +
			'" hidden>' +
			'<div class="amy-agent-header">' +
			'<div class="amy-agent-header__brand">' +
			headerAvatar +
			'<div class="amy-agent-header__titles">' +
			'<p class="amy-agent-header__title">' +
			escapeHtml(i18n.title) +
			'</p>' +
			'<p class="amy-agent-header__subtitle">' +
			escapeHtml(i18n.subtitle) +
			'</p>' +
			'</div>' +
			'</div>' +
			'<div class="amy-agent-header__actions">' +
			'<button type="button" class="amy-agent-icon-btn" data-amy-history aria-label="' +
			escapeHtml(i18n.history) +
			'" title="' +
			escapeHtml(i18n.history) +
			'">' +
			iconSvg('history') +
			'</button>' +
			'<button type="button" class="amy-agent-icon-btn" data-amy-new aria-label="' +
			escapeHtml(i18n.newChat) +
			'" title="' +
			escapeHtml(i18n.newChat) +
			'">' +
			iconSvg('new') +
			'</button>' +
			'<button type="button" class="amy-agent-icon-btn amy-agent-icon-btn--expand" data-amy-expand aria-expanded="false" aria-label="' +
			escapeHtml(i18n.expand) +
			'" title="' +
			escapeHtml(i18n.expand) +
			'">' +
			iconSvg('expand') +
			'</button>' +
			'<button type="button" class="amy-agent-icon-btn amy-agent-header__close" data-amy-close aria-label="' +
			escapeHtml(i18n.close) +
			'" title="' +
			escapeHtml(i18n.close) +
			'">×</button>' +
			'</div>' +
			'</div>' +
			'<div class="amy-agent-body">' +
			'<aside class="amy-agent-history" data-amy-history-pane hidden>' +
			'<div class="amy-agent-history__head">' +
			'<p class="amy-agent-history__title">' +
			escapeHtml(i18n.history) +
			'</p>' +
			'<button type="button" class="amy-agent-history__back amy-agent-icon-btn" data-amy-history-back aria-label="' +
			escapeHtml(i18n.historyBack) +
			'" title="' +
			escapeHtml(i18n.historyBack) +
			'">←</button>' +
			'</div>' +
			'<div class="amy-agent-history__list" data-amy-history-list></div>' +
			'</aside>' +
			'<div class="amy-agent-main">' +
			'<div class="amy-agent-messages" data-amy-messages></div>' +
			'<form class="amy-agent-form" data-amy-form>' +
			'<input class="amy-agent-form__input" type="text" name="message" autocomplete="off" maxlength="2000" placeholder="' +
			escapeHtml(i18n.placeholder) +
			'" data-amy-input />' +
			'<button class="amy-agent-form__send" type="submit" data-amy-send>' +
			escapeHtml(i18n.send) +
			'</button>' +
			'</form>' +
			'</div>' +
			'</div>' +
			'</div>';

		var launcher = root.querySelector('.amy-agent-launcher');
		var panel = root.querySelector('.amy-agent-panel');
		var backdrop = root.querySelector('[data-amy-backdrop]');
		var closeBtn = root.querySelector('[data-amy-close]');
		var historyBtn = root.querySelector('[data-amy-history]');
		var newChatBtn = root.querySelector('[data-amy-new]');
		var expandBtn = root.querySelector('[data-amy-expand]');
		var historyBackBtn = root.querySelector('[data-amy-history-back]');
		var historyPane = root.querySelector('[data-amy-history-pane]');
		var historyList = root.querySelector('[data-amy-history-list]');
		var messagesEl = root.querySelector('[data-amy-messages]');
		var form = root.querySelector('[data-amy-form]');
		var input = root.querySelector('[data-amy-input]');
		var sendBtn = root.querySelector('[data-amy-send]');

		function conversationUrl(suffix) {
			return cfg.restUrl.replace(/\/chat$/, '/chat' + suffix);
		}

		function getVisitorId() {
			try {
				var existing = window.localStorage.getItem(LS_VISITOR);
				if (existing) {
					return existing;
				}
				var next = uuid();
				window.localStorage.setItem(LS_VISITOR, next);
				return next;
			} catch (e) {
				return uuid();
			}
		}

		var visitorId = getVisitorId();
		var conversationId = null;
		try {
			conversationId = window.localStorage.getItem(LS_CONV) || null;
		} catch (e) {
			conversationId = null;
		}

		function persistConversationId(id) {
			conversationId = id;
			try {
				if (id) {
					window.localStorage.setItem(LS_CONV, id);
				} else {
					window.localStorage.removeItem(LS_CONV);
				}
			} catch (e) {}
		}

		function canExpand() {
			try {
				return window.matchMedia && window.matchMedia(EXPAND_MQ).matches;
			} catch (e) {
				return window.innerWidth >= 1024;
			}
		}

		function readExpandedPref() {
			try {
				return window.localStorage.getItem(LS_EXPAND) === '1';
			} catch (e) {
				return false;
			}
		}

		function writeExpandedPref(on) {
			try {
				window.localStorage.setItem(LS_EXPAND, on ? '1' : '0');
			} catch (e) {}
		}

		function startOfLocalDay(ms) {
			var d = new Date(ms);
			d.setHours(0, 0, 0, 0);
			return d.getTime();
		}

		function formatTime(tsSec) {
			var ms = typeof tsSec === 'number' ? tsSec * 1000 : Date.now();
			try {
				return new Date(ms).toLocaleTimeString(undefined, {
					hour: 'numeric',
					minute: '2-digit',
				});
			} catch (e) {
				var d = new Date(ms);
				return d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0');
			}
		}

		function formatDateLabel(tsSec) {
			var ms = typeof tsSec === 'number' ? tsSec * 1000 : Date.now();
			var day = startOfLocalDay(ms);
			var today = startOfLocalDay(Date.now());
			var yesterday = today - 24 * 60 * 60 * 1000;
			if (day === today) {
				return i18n.today || 'Today';
			}
			if (day === yesterday) {
				return i18n.yesterday || 'Yesterday';
			}
			try {
				return new Date(ms).toLocaleDateString(undefined, {
					year: 'numeric',
					month: 'short',
					day: 'numeric',
				});
			} catch (e) {
				return new Date(ms).toDateString();
			}
		}

		function formatHistoryDate(tsSec) {
			var ms = typeof tsSec === 'number' ? tsSec * 1000 : Date.now();
			try {
				return new Date(ms).toLocaleDateString(undefined, {
					year: 'numeric',
					month: 'short',
					day: 'numeric',
				});
			} catch (e) {
				return new Date(ms).toDateString();
			}
		}

		function maybeAppendDateSep(tsSec) {
			var ms = typeof tsSec === 'number' ? tsSec * 1000 : Date.now();
			var key = String(startOfLocalDay(ms));
			if (key === lastDateKey) {
				return;
			}
			lastDateKey = key;
			var sep = document.createElement('div');
			sep.className = 'amy-agent-date-sep';
			sep.setAttribute('role', 'separator');
			sep.textContent = formatDateLabel(tsSec);
			messagesEl.appendChild(sep);
		}

		/**
		 * Safe Markdown → HTML for assistant bubbles.
		 */
		function renderMarkdown(text) {
			var escaped = escapeHtml(String(text || ''));
			var lines = escaped.split(/\r?\n/);
			var html = [];
			var i = 0;

			function formatInline(line) {
				var out = '';
				var rest = line;
				var mdLinkRe = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/;
				var boldRe = /\*\*(.+?)\*\*/;
				var urlRe = /(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"]?)/;

				while (rest.length) {
					var mdLinkMatch = rest.match(mdLinkRe);
					var boldMatch = rest.match(boldRe);
					var urlMatch = rest.match(urlRe);
					var nextIndex = rest.length;
					var kind = null;
					var match = null;

					if (mdLinkMatch && mdLinkMatch.index < nextIndex) {
						nextIndex = mdLinkMatch.index;
						kind = 'mdlink';
						match = mdLinkMatch;
					}
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
					if (kind === 'mdlink') {
						out +=
							'<a href="' +
							match[2] +
							'" target="_blank" rel="noopener noreferrer">' +
							match[1] +
							'</a>';
					} else if (kind === 'bold') {
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

				var headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
				if (headingMatch) {
					html.push(
						'<p class="amy-agent-md-heading"><strong>' +
							formatInline(headingMatch[2]) +
							'</strong></p>'
					);
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
					if (
						/^#{1,3}\s+/.test(next) ||
						/^[\-\*]\s+/.test(next) ||
						/^\d+\.\s+/.test(next)
					) {
						break;
					}
					para.push(formatInline(next));
					i += 1;
				}
				html.push('<p>' + para.join('<br>') + '</p>');
			}

			return html.join('') || '<p></p>';
		}

		function scrollMessagesToEnd() {
			messagesEl.scrollTop = messagesEl.scrollHeight;
		}

		function appendBubble(text, kind, tsSec) {
			var stamp = typeof tsSec === 'number' ? tsSec : Date.now() / 1000;
			if (kind !== 'status') {
				maybeAppendDateSep(stamp);
			}
			var wrap = document.createElement('div');
			wrap.className = 'amy-agent-msg amy-agent-msg--' + kind;
			var el = document.createElement('div');
			el.className = 'amy-agent-bubble amy-agent-bubble--' + kind;
			if (kind === 'assistant') {
				el.innerHTML = renderMarkdown(text);
			} else {
				el.textContent = text;
			}
			wrap.appendChild(el);
			if (kind !== 'status') {
				var timeEl = document.createElement('time');
				timeEl.className = 'amy-agent-msg__time';
				timeEl.dateTime = new Date(stamp * 1000).toISOString();
				timeEl.textContent = formatTime(stamp);
				wrap.appendChild(timeEl);
			}
			messagesEl.appendChild(wrap);
			scrollMessagesToEnd();
			return wrap;
		}

		function clearMessages() {
			messagesEl.innerHTML = '';
			lastDateKey = null;
		}

		function setBusy(next) {
			busy = next;
			sendBtn.disabled = next;
			input.disabled = next;
			newChatBtn.disabled = next;
		}

		function setHistoryVisible(on) {
			showingHistory = !!on;
			root.classList.toggle('is-history', showingHistory);
			if (!expanded) {
				historyPane.hidden = !showingHistory;
			}
			if (showingHistory) {
				loadHistoryList();
			}
		}

		function getFocusable(container) {
			return Array.prototype.slice.call(
				container.querySelectorAll(
					'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
				)
			).filter(function (el) {
				return el.offsetParent !== null || el === document.activeElement;
			});
		}

		function trapFocus(event) {
			if (!expanded || event.key !== 'Tab') {
				return;
			}
			var focusables = getFocusable(panel);
			if (!focusables.length) {
				return;
			}
			var first = focusables[0];
			var last = focusables[focusables.length - 1];
			if (event.shiftKey && document.activeElement === first) {
				event.preventDefault();
				last.focus();
			} else if (!event.shiftKey && document.activeElement === last) {
				event.preventDefault();
				first.focus();
			}
		}

		function setExpanded(on) {
			var want = !!on && canExpand();
			if (want === expanded) {
				updateExpandUi();
				return;
			}
			var draft = input.value;
			expanded = want;
			writeExpandedPref(expanded);
			root.classList.toggle('is-expanded', expanded);
			panel.setAttribute('aria-modal', expanded ? 'true' : 'false');
			backdrop.hidden = !expanded;
			updateExpandUi();

			if (expanded) {
				focusBeforeExpand = document.activeElement;
				historyPane.hidden = false;
				showingHistory = true;
				root.classList.add('is-history');
				loadHistoryList();
				window.setTimeout(function () {
					var focusables = getFocusable(panel);
					if (focusables.length) {
						focusables[0].focus();
					} else {
						input.focus();
					}
				}, reduceMotion ? 0 : 50);
			} else {
				// Collapse back to compact chat — history overlay off unless reopened.
				showingHistory = false;
				root.classList.remove('is-history');
				historyPane.hidden = true;
				if (focusBeforeExpand && typeof focusBeforeExpand.focus === 'function') {
					try {
						focusBeforeExpand.focus();
					} catch (e) {}
				}
				focusBeforeExpand = null;
			}
			input.value = draft;
			scrollMessagesToEnd();
		}

		function updateExpandUi() {
			var label = expanded ? i18n.collapse || 'Collapse chat' : i18n.expand || 'Expand chat';
			expandBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
			expandBtn.setAttribute('aria-label', label);
			expandBtn.setAttribute('title', label);
			expandBtn.innerHTML = iconSvg(expanded ? 'collapse' : 'expand');
			expandBtn.hidden = !canExpand();
		}

		function setOpen(open) {
			root.classList.toggle('is-open', open);
			panel.hidden = !open;
			launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
			launcher.setAttribute('title', open ? i18n.close : i18n.open);
			if (open) {
				if (expanded && canExpand()) {
					backdrop.hidden = false;
				}
				input.focus();
				scrollMessagesToEnd();
				if (window.amyTrack) {
					window.amyTrack('widget_opened');
				}
			} else {
				backdrop.hidden = true;
				if (expanded) {
					// Keep expanded preference; just hide panel.
				}
			}
		}

		function startFreshConversation() {
			clearMessages();
			setHistoryVisible(false);
			appendBubble(i18n.greeting, 'assistant', Date.now() / 1000);
			fetch(conversationUrl('/conversation'), {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-WP-Nonce': cfg.nonce,
				},
				body: JSON.stringify({ visitor_id: visitorId }),
			})
				.then(function (res) {
					return res.json();
				})
				.then(function (data) {
					if (data && data.id) {
						persistConversationId(data.id);
						if (expanded) {
							loadHistoryList();
						}
					}
				})
				.catch(function () {});
		}

		function renderLoadedMessages(messages) {
			clearMessages();
			if (!messages || !messages.length) {
				startFreshConversation();
				return;
			}
			messages.forEach(function (m) {
				var kind = m.role === 'user' ? 'user' : 'assistant';
				var ts =
					typeof m.created_at === 'number' ? m.created_at : Date.now() / 1000;
				appendBubble(m.content, kind, ts);
			});
		}

		function loadConversation(id) {
			fetch(
				conversationUrl('/conversation/') +
					id +
					'?visitor_id=' +
					encodeURIComponent(visitorId),
				{
					credentials: 'same-origin',
					headers: { Accept: 'application/json', 'X-WP-Nonce': cfg.nonce },
				}
			)
				.then(function (res) {
					return res.ok ? res.json() : Promise.reject();
				})
				.then(function (data) {
					if (data && Array.isArray(data.messages) && data.messages.length) {
						persistConversationId(id);
						renderLoadedMessages(data.messages);
						setHistoryVisible(false);
						if (expanded) {
							historyPane.hidden = false;
							loadHistoryList();
						}
						scrollMessagesToEnd();
					} else {
						startFreshConversation();
					}
				})
				.catch(function () {
					persistConversationId(null);
					startFreshConversation();
				});
		}

		function shortenTitle(title) {
			var t = String(title || '').trim();
			if (!t) {
				return i18n.untitledChat || 'Chat';
			}
			if (t.length <= 48) {
				return t;
			}
			return t.slice(0, 45) + '…';
		}

		function loadHistoryList() {
			historyList.innerHTML =
				'<p class="amy-agent-history__loading">' +
				escapeHtml(i18n.thinking || '…') +
				'</p>';
			fetch(
				conversationUrl('/conversations') +
					'?visitor_id=' +
					encodeURIComponent(visitorId),
				{
					credentials: 'same-origin',
					headers: { Accept: 'application/json', 'X-WP-Nonce': cfg.nonce },
				}
			)
				.then(function (res) {
					return res.ok ? res.json() : Promise.reject();
				})
				.then(function (data) {
					var rows =
						data && Array.isArray(data.conversations) ? data.conversations : [];
					historyList.innerHTML = '';
					if (!rows.length) {
						var empty = document.createElement('p');
						empty.className = 'amy-agent-history__empty';
						empty.textContent = i18n.historyEmpty || 'No previous chats yet.';
						historyList.appendChild(empty);
						return;
					}
					rows.forEach(function (row) {
						var btn = document.createElement('button');
						btn.type = 'button';
						btn.className = 'amy-agent-history__item';
						if (row.id === conversationId) {
							btn.classList.add('is-active');
						}
						btn.setAttribute(
							'aria-label',
							shortenTitle(row.title) + ', ' + formatHistoryDate(row.updated_at)
						);
						btn.innerHTML =
							'<span class="amy-agent-history__item-title">' +
							escapeHtml(shortenTitle(row.title)) +
							'</span>' +
							'<span class="amy-agent-history__item-date">' +
							escapeHtml(formatHistoryDate(row.updated_at)) +
							'</span>';
						btn.addEventListener('click', function () {
							if (busy) {
								return;
							}
							loadConversation(row.id);
						});
						historyList.appendChild(btn);
					});
				})
				.catch(function () {
					historyList.innerHTML = '';
					var err = document.createElement('p');
					err.className = 'amy-agent-history__empty';
					err.textContent = i18n.unavailable || 'Amy is unavailable right now.';
					historyList.appendChild(err);
				});
		}

		// Initial conversation bootstrap.
		if (conversationId) {
			loadConversation(conversationId);
		} else {
			startFreshConversation();
		}

		// Restore expand preference on desktop.
		updateExpandUi();
		if (readExpandedPref() && canExpand()) {
			expanded = true;
			root.classList.add('is-expanded');
			panel.setAttribute('aria-modal', 'true');
			historyPane.hidden = false;
			updateExpandUi();
		}

		launcher.addEventListener('click', function () {
			var open = !root.classList.contains('is-open');
			setOpen(open);
			if (open && expanded && canExpand()) {
				backdrop.hidden = false;
				historyPane.hidden = false;
				showingHistory = true;
				root.classList.add('is-history');
				loadHistoryList();
			}
		});

		closeBtn.addEventListener('click', function () {
			setOpen(false);
		});

		backdrop.addEventListener('click', function () {
			if (expanded) {
				setExpanded(false);
			}
		});

		expandBtn.addEventListener('click', function () {
			if (!canExpand()) {
				return;
			}
			if (!root.classList.contains('is-open')) {
				setOpen(true);
			}
			setExpanded(!expanded);
		});

		historyBtn.addEventListener('click', function () {
			if (expanded) {
				loadHistoryList();
				return;
			}
			setHistoryVisible(!showingHistory);
		});

		historyBackBtn.addEventListener('click', function () {
			setHistoryVisible(false);
		});

		newChatBtn.addEventListener('click', function () {
			if (busy) {
				return;
			}
			startFreshConversation();
		});

		document.addEventListener('keydown', function (event) {
			if (event.key === 'Escape' && expanded) {
				event.preventDefault();
				setExpanded(false);
				return;
			}
			trapFocus(event);
		});

		window.addEventListener('resize', function () {
			updateExpandUi();
			if (expanded && !canExpand()) {
				setExpanded(false);
			}
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
			appendBubble(text, 'user', Date.now() / 1000);
			if (window.amyTrack) {
				window.amyTrack('widget_message_sent');
			}

			var thinking = appendBubble(i18n.thinking, 'status');
			setBusy(true);

			var body = {
				session_id: sessionId,
				visitor_id: visitorId,
				mode: 'general',
				messages: [{ role: 'user', content: text }],
				page: {
					url: cfg.pageUrl || window.location.href,
					slug: cfg.pageSlug || '',
				},
				context: {},
			};
			if (conversationId) {
				body.conversation_id = conversationId;
			}
			if (cfg.closingWishes !== false) {
				try {
					var tz =
						typeof Intl !== 'undefined' &&
						Intl.DateTimeFormat &&
						Intl.DateTimeFormat().resolvedOptions
							? Intl.DateTimeFormat().resolvedOptions().timeZone
							: '';
					if (tz) {
						body.visitor_timezone = String(tz).slice(0, 64);
					}
				} catch (tzErr) {
					/* ignore */
				}
				try {
					var lang =
						(navigator.languages && navigator.languages[0]) ||
						navigator.language ||
						'';
					if (lang) {
						body.visitor_language = String(lang).slice(0, 32);
					}
				} catch (langErr) {
					/* ignore */
				}
			}

			fetch(cfg.restUrl, {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-WP-Nonce': cfg.nonce,
				},
				body: JSON.stringify(body),
			})
				.then(function (res) {
					return res
						.json()
						.then(function (data) {
							return { ok: res.ok, status: res.status, data: data };
						})
						.catch(function () {
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
						appendBubble(reply, 'assistant', Date.now() / 1000);
						if (
							result.data.meta &&
							result.data.meta.closing_wish &&
							window.amyTrack
						) {
							window.amyTrack('chat_closing_wish');
						}
						if (expanded) {
							loadHistoryList();
						}
						return;
					}
					appendBubble(i18n.unavailable, 'status');
				})
				.catch(function () {
					thinking.remove();
					appendBubble(i18n.unavailable, 'status');
				})
				.finally(function () {
					setBusy(false);
					input.focus();
				});
		});
	});
})();
