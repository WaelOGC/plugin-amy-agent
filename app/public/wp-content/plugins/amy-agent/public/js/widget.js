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
				'xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
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
			if (name === 'attach') {
				return (
					'<svg ' +
					common +
					'><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>'
				);
			}
			if (name === 'image') {
				return (
					'<svg ' +
					common +
					'><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>'
				);
			}
			if (name === 'document') {
				return (
					'<svg ' +
					common +
					'><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
				);
			}
			if (name === 'help') {
				return (
					'<svg ' +
					common +
					'><circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
				);
			}
			return '×';
		}

		var sessionId = uuid();
		var busy = false;
		var showingHistory = false;
		var expanded = false;
		var uploadsEnabled = !!cfg.uploadsEnabled;
		var MAX_PENDING_FILES = 3;
		var pendingFiles = [];
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
			'<div class="amy-agent-form__chips" data-amy-chips hidden></div>' +
			(uploadsEnabled
				? '<p class="amy-agent-form__sensitive" data-amy-sensitive-notice hidden>' +
				  escapeHtml(i18n.sensitiveNotice || '') +
				  '</p>'
				: '') +
			'<div class="amy-agent-form__row">' +
			(uploadsEnabled
				? '<div class="amy-agent-form__attach-wrap">' +
				  '<button type="button" class="amy-agent-icon-btn amy-agent-form__attach" data-amy-attach aria-label="' +
				  escapeHtml(i18n.attach || 'Attach a file') +
				  '" title="' +
				  escapeHtml(i18n.attach || 'Attach a file') +
				  '" aria-haspopup="menu" aria-expanded="false" aria-controls="amy-agent-attach-menu">' +
				  iconSvg('attach') +
				  '</button>' +
				  '<button type="button" class="amy-agent-icon-btn amy-agent-form__upload-info" data-amy-upload-info aria-label="' +
				  escapeHtml(i18n.uploadInfo || 'Upload information') +
				  '" title="' +
				  escapeHtml(i18n.uploadInfo || 'Upload information') +
				  '" aria-haspopup="dialog" aria-expanded="false" aria-controls="amy-agent-upload-info">' +
				  iconSvg('help') +
				  '</button>' +
				  '<div class="amy-agent-popover amy-agent-popover--attach" id="amy-agent-attach-menu" data-amy-attach-menu role="menu" hidden>' +
				  '<button type="button" class="amy-agent-popover__item" role="menuitem" data-amy-attach-choice="image">' +
				  '<span class="amy-agent-popover__icon">' +
				  iconSvg('image') +
				  '</span><span class="amy-agent-popover__text"><span class="amy-agent-popover__label">' +
				  escapeHtml(i18n.attachUploadImage || 'Upload image') +
				  '</span><span class="amy-agent-popover__hint">' +
				  escapeHtml(i18n.attachUploadImageHint || 'JPEG, PNG, WebP') +
				  '</span></span></button>' +
				  '<button type="button" class="amy-agent-popover__item" role="menuitem" data-amy-attach-choice="document">' +
				  '<span class="amy-agent-popover__icon">' +
				  iconSvg('document') +
				  '</span><span class="amy-agent-popover__text"><span class="amy-agent-popover__label">' +
				  escapeHtml(i18n.attachUploadDoc || 'Upload document') +
				  '</span><span class="amy-agent-popover__hint">' +
				  escapeHtml(i18n.attachUploadDocHint || 'PDF, up to 10 pages') +
				  '</span></span></button>' +
				  '</div>' +
				  '<div class="amy-agent-popover amy-agent-popover--info" id="amy-agent-upload-info" data-amy-upload-info-panel role="dialog" aria-label="' +
				  escapeHtml(i18n.uploadInfo || 'Upload information') +
				  '" hidden>' +
				  '<p>' +
				  escapeHtml(i18n.uploadInfoAccepted || '') +
				  '</p><p>' +
				  escapeHtml(i18n.uploadInfoLimits || '') +
				  '</p><p>' +
				  escapeHtml(i18n.uploadInfoSensitive || '') +
				  '</p><p>' +
				  escapeHtml(i18n.uploadInfoRetention || '') +
				  '</p></div>' +
				  '<input type="file" class="amy-agent-form__file-input" data-amy-file-image hidden accept="image/jpeg,image/png,image/webp" multiple />' +
				  '<input type="file" class="amy-agent-form__file-input" data-amy-file-pdf hidden accept="application/pdf" />' +
				  '</div>'
				: '') +
			'<textarea class="amy-agent-form__input amy-agent-form__textarea" name="message" rows="1" autocomplete="off" maxlength="2000" placeholder="' +
			escapeHtml(i18n.placeholder) +
			'" data-amy-input></textarea>' +
			'<button class="amy-agent-form__send" type="submit" data-amy-send>' +
			escapeHtml(i18n.send) +
			'</button>' +
			'</div>' +
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
		var chipsEl = root.querySelector('[data-amy-chips]');
		var attachBtn = root.querySelector('[data-amy-attach]');
		var uploadInfoBtn = root.querySelector('[data-amy-upload-info]');
		var attachMenu = root.querySelector('[data-amy-attach-menu]');
		var uploadInfoPanel = root.querySelector('[data-amy-upload-info-panel]');
		var fileImageInput = root.querySelector('[data-amy-file-image]');
		var filePdfInput = root.querySelector('[data-amy-file-pdf]');
		var sensitiveNoticeEl = root.querySelector('[data-amy-sensitive-notice]');
		var subtitleEl = root.querySelector('.amy-agent-header__subtitle');
		var sensitiveNoticeShown = false;
		var attachMenuOpen = false;
		var uploadInfoOpen = false;
		var attachMenuFocusIndex = 0;

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
			return formatDateLabel(tsSec) + ', ' + formatTime(tsSec);
		}

		function updateSubtitle() {
			if (!subtitleEl) {
				return;
			}
			var text = expanded
				? i18n.subtitleExpanded || i18n.subtitle || ''
				: i18n.subtitleCompact || 'AI assistant';
			subtitleEl.textContent = text;
		}

		function textareaMaxHeightPx() {
			var linePx = 22;
			try {
				var cs = window.getComputedStyle(input);
				var lh = parseFloat(cs.lineHeight);
				if (lh && !isNaN(lh)) {
					linePx = lh;
				}
			} catch (e) {}
			var maxLines = expanded ? 10 : 6;
			return Math.ceil(linePx * maxLines + 8);
		}

		function oneLineTextareaHeightPx() {
			var linePx = 22;
			var pad = 0;
			try {
				var cs = window.getComputedStyle(input);
				var lh = parseFloat(cs.lineHeight);
				if (lh && !isNaN(lh)) {
					linePx = lh;
				}
				var pt = parseFloat(cs.paddingTop) || 0;
				var pb = parseFloat(cs.paddingBottom) || 0;
				var bt = parseFloat(cs.borderTopWidth) || 0;
				var bb = parseFloat(cs.borderBottomWidth) || 0;
				pad = pt + pb + bt + bb;
			} catch (e) {}
			return Math.ceil(linePx + pad);
		}

		function syncTextareaHeight() {
			if (!input) {
				return;
			}
			var maxPx = textareaMaxHeightPx();
			var minPx = oneLineTextareaHeightPx();
			input.style.height = '0px';
			var scroll = input.scrollHeight;
			var next = Math.max(minPx, Math.min(scroll, maxPx));
			input.style.height = next + 'px';
			input.style.overflowY = scroll > maxPx ? 'auto' : 'hidden';
		}

		function resetTextareaHeight() {
			if (!input) {
				return;
			}
			input.value = input.value || '';
			input.style.height = oneLineTextareaHeightPx() + 'px';
			input.style.overflowY = 'hidden';
			syncTextareaHeight();
		}

		function fileUrlWithVisitor(attachment) {
			var url = attachment && attachment.url ? String(attachment.url) : '';
			if (!url && attachment && attachment.id && cfg.filesUrl) {
				url =
					String(cfg.filesUrl).replace(/\/$/, '') +
					'/' +
					encodeURIComponent(attachment.id);
			}
			if (!url) {
				return '#';
			}
			if (url.indexOf('visitor_id=') >= 0) {
				return url;
			}
			var sep = url.indexOf('?') >= 0 ? '&' : '?';
			return url + sep + 'visitor_id=' + encodeURIComponent(visitorId);
		}

		function attachmentKind(attachment) {
			if (attachment.kind) {
				return attachment.kind;
			}
			var ct = attachment.content_type || '';
			if (ct.indexOf('image/') === 0) {
				return 'image';
			}
			if (ct === 'application/pdf') {
				return 'pdf';
			}
			return 'file';
		}

		function renderAttachmentsHtml(attachments) {
			if (!attachments || !attachments.length) {
				return '';
			}
			var parts = ['<div class="amy-agent-attachments">'];
			attachments.forEach(function (a) {
				if (!a) {
					return;
				}
				if (a.expired) {
					parts.push(
						'<span class="amy-agent-attach-chip amy-agent-attach-chip--expired">' +
							escapeHtml(i18n.fileExpired || 'File expired') +
							'</span>'
					);
					return;
				}
				var url = fileUrlWithVisitor(a);
				var kind = attachmentKind(a);
				if (kind === 'image') {
					parts.push(
						'<a class="amy-agent-attach-thumb" href="' +
							escapeHtml(url) +
							'" target="_blank" rel="noopener noreferrer"><img src="' +
							escapeHtml(url) +
							'" alt="" loading="lazy" decoding="async" /></a>'
					);
				} else {
					var name = a.filename || 'PDF';
					parts.push(
						'<a class="amy-agent-attach-chip" href="' +
							escapeHtml(url) +
							'" target="_blank" rel="noopener noreferrer">' +
							escapeHtml(name) +
							'</a>'
					);
				}
			});
			parts.push('</div>');
			return parts.join('');
		}

		function formatFileSize(bytes) {
			var n = typeof bytes === 'number' ? bytes : 0;
			if (n < 1024) {
				return n + ' B';
			}
			if (n < 1024 * 1024) {
				return (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
			}
			return (n / (1024 * 1024)).toFixed(1) + ' MB';
		}

		function clearPendingFiles() {
			pendingFiles = [];
			renderPendingChips();
		}

		function renderPendingChips() {
			if (!chipsEl) {
				return;
			}
			chipsEl.innerHTML = '';
			if (!pendingFiles.length) {
				chipsEl.hidden = true;
				return;
			}
			chipsEl.hidden = false;
			pendingFiles.forEach(function (item) {
				var chip = document.createElement('span');
				chip.className = 'amy-agent-pending-chip';
				if (item.status === 'uploading') {
					chip.classList.add('is-uploading');
				}
				if (item.status === 'error') {
					chip.classList.add('is-error');
				}
				var label =
					'<span class="amy-agent-pending-chip__name" title="' +
					escapeHtml(item.name) +
					'">' +
					escapeHtml(item.name) +
					'</span><span class="amy-agent-pending-chip__size">' +
					escapeHtml(formatFileSize(item.size)) +
					'</span>';
				if (item.status === 'uploading') {
					label +=
						'<span class="amy-agent-pending-chip__progress" aria-hidden="true"></span>';
				}
				chip.innerHTML =
					label +
					'<button type="button" class="amy-agent-pending-chip__remove" data-pending-id="' +
					escapeHtml(item.id) +
					'" aria-label="' +
					escapeHtml(i18n.removeFile || 'Remove attachment') +
					'">×</button>';
				chipsEl.appendChild(chip);
			});
		}

		function removePendingFile(id) {
			pendingFiles = pendingFiles.filter(function (p) {
				return p.id !== id;
			});
			renderPendingChips();
		}

		function successfulAttachments() {
			return pendingFiles
				.filter(function (p) {
					return p.status === 'done' && p.attachment;
				})
				.map(function (p) {
					return p.attachment;
				});
		}

		function showSensitiveNoticeOnce() {
			if (sensitiveNoticeShown || !sensitiveNoticeEl) {
				return;
			}
			sensitiveNoticeShown = true;
			sensitiveNoticeEl.hidden = false;
		}

		function hideSensitiveNotice() {
			if (sensitiveNoticeEl) {
				sensitiveNoticeEl.hidden = true;
			}
		}

		function queueFiles(fileList) {
			if (!uploadsEnabled || !fileList) {
				return;
			}
			var files = Array.prototype.slice.call(fileList);
			if (!files.length) {
				return;
			}
			showSensitiveNoticeOnce();
			var slots = MAX_PENDING_FILES - pendingFiles.length;
			if (slots <= 0) {
				appendBubble(i18n.tooManyFiles || 'Too many files.', 'status');
				return;
			}
			files.slice(0, slots).forEach(function (file) {
				if (pendingFiles.length >= MAX_PENDING_FILES) {
					return;
				}
				var item = {
					id: uuid(),
					file: file,
					name: file.name || 'file',
					size: file.size || 0,
					status: 'uploading',
					attachment: null,
				};
				pendingFiles.push(item);
				renderPendingChips();
				uploadPendingFile(item);
			});
			if (files.length > slots) {
				appendBubble(i18n.tooManyFiles || 'Too many files.', 'status');
			}
		}

		function uploadPendingFile(item) {
			var fd = new FormData();
			fd.append('visitor_id', visitorId);
			fd.append('file', item.file, item.name);
			fd.append('notify', cfg.uploadNotify ? 'true' : 'false');
			fd.append('allow_uploads', 'true');
			if (conversationId) {
				fd.append('conversation_id', conversationId);
			}
			fetch(cfg.uploadUrl, {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					Accept: 'application/json',
					'X-WP-Nonce': cfg.nonce,
				},
				body: fd,
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
					var idx = pendingFiles.findIndex(function (p) {
						return p.id === item.id;
					});
					if (idx < 0) {
						return;
					}
					if (result.ok && result.data) {
						pendingFiles[idx].status = 'done';
						pendingFiles[idx].attachment = result.data;
					} else {
						pendingFiles[idx].status = 'error';
						var rateLimited =
							result.status === 429 ||
							(result.data && result.data.error === 'rate_limited');
						appendBubble(
							rateLimited
								? i18n.uploadRateLimited ||
										"You've reached the upload limit for now, please try again in a bit."
								: i18n.uploadFailed || 'Upload failed.',
							'status'
						);
					}
					renderPendingChips();
				})
				.catch(function () {
					var idx = pendingFiles.findIndex(function (p) {
						return p.id === item.id;
					});
					if (idx >= 0) {
						pendingFiles[idx].status = 'error';
						renderPendingChips();
						appendBubble(i18n.uploadFailed || 'Upload failed.', 'status');
					}
				});
		}

		function createConversationIfNeeded() {
			if (conversationId) {
				return Promise.resolve(conversationId);
			}
			return fetch(conversationUrl('/conversation'), {
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
					return res.ok
						? res.json()
						: Promise.reject(new Error('create_failed'));
				})
				.then(function (data) {
					if (data && data.id) {
						persistConversationId(data.id);
						return data.id;
					}
					return Promise.reject(new Error('create_failed'));
				});
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

		function appendBubble(text, kind, tsSec, attachments) {
			var stamp = typeof tsSec === 'number' ? tsSec : Date.now() / 1000;
			var atts = attachments || [];
			if (kind !== 'status') {
				maybeAppendDateSep(stamp);
			}
			var wrap = document.createElement('div');
			wrap.className = 'amy-agent-msg amy-agent-msg--' + kind;
			var el = document.createElement('div');
			el.className = 'amy-agent-bubble amy-agent-bubble--' + kind;
			if (kind === 'assistant') {
				el.innerHTML = renderMarkdown(text) + renderAttachmentsHtml(atts);
			} else if (kind === 'user') {
				if (atts.length) {
					var body = text
						? '<span class="amy-agent-bubble__text">' +
						  escapeHtml(String(text)).replace(/\n/g, '<br>') +
						  '</span>'
						: '';
					el.innerHTML = body + renderAttachmentsHtml(atts);
				} else {
					el.textContent = text;
				}
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
			if (attachBtn) {
				attachBtn.disabled = next;
			}
			if (uploadInfoBtn) {
				uploadInfoBtn.disabled = next;
			}
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
			syncTextareaHeight();
			scrollMessagesToEnd();
		}

		function updateExpandUi() {
			var label = expanded ? i18n.collapse || 'Collapse chat' : i18n.expand || 'Expand chat';
			expandBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
			expandBtn.setAttribute('aria-label', label);
			expandBtn.setAttribute('title', label);
			expandBtn.innerHTML = iconSvg(expanded ? 'collapse' : 'expand');
			expandBtn.hidden = !canExpand();
			updateSubtitle();
			syncTextareaHeight();
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
			persistConversationId(null);
			clearPendingFiles();
			appendBubble(i18n.greeting, 'assistant', Date.now() / 1000);
			if (expanded) {
				loadHistoryList();
			}
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
				appendBubble(m.content, kind, ts, m.attachments || []);
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

		function shortenTitle(title, fallback) {
			var t = String(title || '').trim();
			if (!t && fallback) {
				t = String(fallback || '').trim();
			}
			if (!t) {
				return '';
			}
			if (t.length <= 40) {
				return t;
			}
			return t.slice(0, 37) + '…';
		}

		function historyItemTitle(row) {
			var title = row && row.title ? String(row.title).trim() : '';
			if (title) {
				return shortenTitle(title);
			}
			var preview = row && row.last_message_preview
				? String(row.last_message_preview).trim()
				: '';
			// Prefer generated title; else trim first-user / preview text to ~40 chars.
			return shortenTitle(preview) || (i18n.untitledChat || 'Chat');
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
					// Service already omits empty shells; belt-and-suspenders client filter.
					rows = rows.filter(function (row) {
						var title = row && row.title ? String(row.title).trim() : '';
						var preview =
							row && row.last_message_preview
								? String(row.last_message_preview).trim()
								: '';
						return !!(title || preview);
					});
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
						var itemTitle = historyItemTitle(row);
						btn.setAttribute(
							'aria-label',
							itemTitle + ', ' + formatHistoryDate(row.updated_at)
						);
						var preview = row.last_message_preview
							? String(row.last_message_preview).trim()
							: '';
						btn.innerHTML =
							'<span class="amy-agent-history__item-title">' +
							escapeHtml(itemTitle) +
							'</span>' +
							'<span class="amy-agent-history__item-date">' +
							escapeHtml(formatHistoryDate(row.updated_at)) +
							'</span>' +
							(preview
								? '<span class="amy-agent-history__item-preview">' +
								  escapeHtml(preview) +
								  '</span>'
								: '');
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
		updateSubtitle();
		syncTextareaHeight();
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
			if (event.key === 'Escape' && (attachMenuOpen || uploadInfoOpen)) {
				// Popover Escape is handled by the upload listeners below.
				return;
			}
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

		input.addEventListener('input', syncTextareaHeight);
		input.addEventListener('keydown', function (event) {
			if (event.key !== 'Enter' || event.shiftKey) {
				return;
			}
			if (event.isComposing || event.keyCode === 229) {
				return;
			}
			event.preventDefault();
			if (typeof form.requestSubmit === 'function') {
				form.requestSubmit();
			} else {
				form.dispatchEvent(new Event('submit', { cancelable: true }));
			}
		});

		if (uploadsEnabled && attachBtn && fileImageInput && filePdfInput) {
			function attachMenuItems() {
				return attachMenu
					? Array.prototype.slice.call(
							attachMenu.querySelectorAll('[role="menuitem"]')
					  )
					: [];
			}

			function closeAttachMenu(restoreFocus) {
				if (!attachMenu || !attachMenuOpen) {
					if (attachBtn) {
						attachBtn.setAttribute('aria-expanded', 'false');
					}
					return;
				}
				attachMenuOpen = false;
				attachMenu.hidden = true;
				attachBtn.setAttribute('aria-expanded', 'false');
				if (restoreFocus !== false) {
					attachBtn.focus();
				}
			}

			function openAttachMenu() {
				closeUploadInfo(false);
				attachMenuOpen = true;
				attachMenu.hidden = false;
				attachBtn.setAttribute('aria-expanded', 'true');
				attachMenuFocusIndex = 0;
				var items = attachMenuItems();
				if (items[0]) {
					items[0].focus();
				}
			}

			function closeUploadInfo(restoreFocus) {
				if (!uploadInfoPanel || !uploadInfoOpen) {
					if (uploadInfoBtn) {
						uploadInfoBtn.setAttribute('aria-expanded', 'false');
					}
					return;
				}
				uploadInfoOpen = false;
				uploadInfoPanel.hidden = true;
				uploadInfoBtn.setAttribute('aria-expanded', 'false');
				if (restoreFocus !== false) {
					uploadInfoBtn.focus();
				}
			}

			function openUploadInfo() {
				closeAttachMenu(false);
				uploadInfoOpen = true;
				uploadInfoPanel.hidden = false;
				uploadInfoBtn.setAttribute('aria-expanded', 'true');
			}

			function closeAllUploadPopovers(restoreFocus) {
				closeAttachMenu(restoreFocus);
				closeUploadInfo(restoreFocus);
			}

			attachBtn.addEventListener('click', function () {
				if (attachMenuOpen) {
					closeAttachMenu();
				} else {
					openAttachMenu();
				}
			});

			if (uploadInfoBtn && uploadInfoPanel) {
				uploadInfoBtn.addEventListener('click', function () {
					if (uploadInfoOpen) {
						closeUploadInfo();
					} else {
						openUploadInfo();
					}
				});
			}

			if (attachMenu) {
				attachMenu.addEventListener('click', function (event) {
					var choice = event.target.closest('[data-amy-attach-choice]');
					if (!choice) {
						return;
					}
					var kind = choice.getAttribute('data-amy-attach-choice');
					closeAttachMenu();
					if (kind === 'image') {
						fileImageInput.click();
					} else if (kind === 'document') {
						filePdfInput.click();
					}
				});
				attachMenu.addEventListener('keydown', function (event) {
					var items = attachMenuItems();
					if (!items.length) {
						return;
					}
					if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
						event.preventDefault();
						attachMenuFocusIndex = (attachMenuFocusIndex + 1) % items.length;
						items[attachMenuFocusIndex].focus();
					} else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
						event.preventDefault();
						attachMenuFocusIndex =
							(attachMenuFocusIndex - 1 + items.length) % items.length;
						items[attachMenuFocusIndex].focus();
					} else if (event.key === 'Home') {
						event.preventDefault();
						attachMenuFocusIndex = 0;
						items[0].focus();
					} else if (event.key === 'End') {
						event.preventDefault();
						attachMenuFocusIndex = items.length - 1;
						items[attachMenuFocusIndex].focus();
					} else if (event.key === 'Escape') {
						event.preventDefault();
						event.stopPropagation();
						closeAttachMenu();
					} else if (event.key === 'Enter' || event.key === ' ') {
						event.preventDefault();
						items[attachMenuFocusIndex].click();
					}
				});
			}

			fileImageInput.addEventListener('change', function () {
				queueFiles(fileImageInput.files);
				fileImageInput.value = '';
			});
			filePdfInput.addEventListener('change', function () {
				queueFiles(filePdfInput.files);
				filePdfInput.value = '';
			});

			document.addEventListener('mousedown', function (event) {
				if (!attachMenuOpen && !uploadInfoOpen) {
					return;
				}
				var t = event.target;
				if (
					attachBtn.contains(t) ||
					(uploadInfoBtn && uploadInfoBtn.contains(t)) ||
					(attachMenu && attachMenu.contains(t)) ||
					(uploadInfoPanel && uploadInfoPanel.contains(t))
				) {
					return;
				}
				closeAllUploadPopovers(false);
			});

			document.addEventListener('keydown', function (event) {
				if (event.key !== 'Escape') {
					return;
				}
				if (attachMenuOpen || uploadInfoOpen) {
					event.preventDefault();
					event.stopPropagation();
					closeAllUploadPopovers(true);
				}
			});

			input.addEventListener('paste', function (event) {
				var items = event.clipboardData && event.clipboardData.items;
				if (!items) {
					return;
				}
				var images = [];
				for (var i = 0; i < items.length; i++) {
					if (items[i].kind === 'file') {
						var f = items[i].getAsFile();
						if (f && f.type && f.type.indexOf('image/') === 0) {
							images.push(f);
						}
					}
				}
				if (images.length) {
					event.preventDefault();
					queueFiles(images);
				}
			});
			if (chipsEl) {
				chipsEl.addEventListener('click', function (event) {
					var btn = event.target.closest('[data-pending-id]');
					if (!btn) {
						return;
					}
					removePendingFile(btn.getAttribute('data-pending-id'));
				});
			}
			function onDragOver(event) {
				event.preventDefault();
				event.dataTransfer.dropEffect = 'copy';
			}
			function onDrop(event) {
				event.preventDefault();
				if (event.dataTransfer && event.dataTransfer.files) {
					queueFiles(event.dataTransfer.files);
				}
			}
			form.addEventListener('dragover', onDragOver);
			form.addEventListener('drop', onDrop);
			panel.addEventListener('dragover', onDragOver);
			panel.addEventListener('drop', onDrop);
		}

		form.addEventListener('submit', function (event) {
			event.preventDefault();
			if (busy) {
				return;
			}

			var text = (input.value || '').trim();
			var attachments = successfulAttachments();
			if (!text && !attachments.length) {
				return;
			}
			if (
				pendingFiles.some(function (p) {
					return p.status === 'uploading';
				})
			) {
				return;
			}

			input.value = '';
			resetTextareaHeight();
			appendBubble(text, 'user', Date.now() / 1000, attachments);
			clearPendingFiles();
			hideSensitiveNotice();
			if (window.amyTrack) {
				window.amyTrack('widget_message_sent');
			}

			var thinking = appendBubble(i18n.thinking, 'status');
			setBusy(true);

			function postChat(convId) {
				var userMsg = { role: 'user', content: text };
				if (attachments.length) {
					userMsg.attachments = attachments;
				}
				var body = {
					session_id: sessionId,
					visitor_id: visitorId,
					mode: 'general',
					messages: [userMsg],
					page: {
						url: cfg.pageUrl || window.location.href,
						slug: cfg.pageSlug || '',
					},
					context: {},
					conversation_id: convId,
				};
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

				return fetch(cfg.restUrl, {
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
					});
			}

			createConversationIfNeeded()
				.then(function (convId) {
					return postChat(convId);
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
