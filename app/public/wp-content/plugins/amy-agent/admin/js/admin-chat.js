/**
 * Amy Agent — Dashboard Chat (REST → Python conversation memory).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentAdminChat || {};
		var i18n = cfg.i18n || {};
		var restUrl = String(cfg.restUrl || '').replace(/\/$/, '');
		var conversations = [];
		var activeId = null;
		var pendingAttachments = [];
		var sending = false;
		var uploading = false;
		var creatingPromise = null;

		var $root = $('#amy-agent-chat-root');
		if (!$root.length) {
			return;
		}

		$root.append(
			'<div class="amy-agent-chat__layout">' +
				'<aside class="amy-agent-chat__sidebar" aria-label="' +
				escapeHtml(i18n.newChat || 'Conversations') +
				'">' +
				'<div class="amy-agent-chat__sidebar-head">' +
				'<button type="button" class="amy-agent-chat__btn amy-agent-chat__btn--accent" id="amy-chat-new">' +
				'<span class="dashicons dashicons-plus-alt2" aria-hidden="true"></span> ' +
				escapeHtml(i18n.newChat || 'New chat') +
				'</button>' +
				'</div>' +
				'<div class="amy-agent-chat__list" id="amy-chat-list" role="list"></div>' +
				'<p class="amy-agent-chat__list-error" id="amy-chat-list-error" hidden role="alert"></p>' +
				'<div class="amy-agent-chat__sidebar-foot">' +
				'<img class="amy-agent-chat__sidebar-foot-avatar" src="' +
				escapeHtml(cfg.currentUserAvatarUrl || '') +
				'" alt="" />' +
				'<span class="amy-agent-chat__sidebar-foot-name">' +
				escapeHtml(cfg.currentUserName || '') +
				'</span>' +
				'</div>' +
				'</aside>' +
				'<section class="amy-agent-chat__pane">' +
				'<header class="amy-agent-chat__pane-head" id="amy-chat-pane-head" hidden>' +
				'<h2 class="amy-agent-chat__pane-title" id="amy-chat-pane-title"></h2>' +
				'</header>' +
				'<div class="amy-agent-chat__thread" id="amy-chat-thread" aria-live="polite"></div>' +
				'<p class="amy-agent-chat__empty" id="amy-chat-empty">' +
				escapeHtml(i18n.emptyState || 'Start a new chat or pick one from the list.') +
				'</p>' +
				'<div class="amy-agent-chat__composer" id="amy-chat-composer" hidden>' +
				'<div class="amy-agent-chat__chips" id="amy-chat-chips" hidden></div>' +
				'<p class="amy-agent-chat__error" id="amy-chat-error" hidden role="alert"></p>' +
				'<div class="amy-agent-chat__composer-row">' +
				'<button type="button" class="amy-agent-chat__icon-btn" id="amy-chat-attach" title="' +
				escapeHtml(i18n.attach || 'Attach a file') +
				'" aria-label="' +
				escapeHtml(i18n.attach || 'Attach a file') +
				'">' +
				'<span class="dashicons dashicons-paperclip" aria-hidden="true"></span>' +
				'</button>' +
				'<textarea id="amy-chat-input" class="amy-agent-chat__input" rows="2" placeholder="' +
				escapeHtml(i18n.composerPlaceholder || 'Message Amy…') +
				'"></textarea>' +
				'<button type="button" class="amy-agent-chat__btn amy-agent-chat__btn--accent" id="amy-chat-send" title="' +
				escapeHtml(i18n.send || 'Send') +
				'" aria-label="' +
				escapeHtml(i18n.send || 'Send') +
				'">' +
				'<span class="dashicons dashicons-arrow-up-alt2" aria-hidden="true"></span>' +
				'</button>' +
				'</div>' +
				'<input type="file" id="amy-chat-file" hidden accept="' +
				escapeHtml(cfg.uploadAccept || '') +
				'" />' +
				'</div>' +
				'</section>' +
				'</div>'
		);

		var $list = $('#amy-chat-list');
		var $listError = $('#amy-chat-list-error');
		var $thread = $('#amy-chat-thread');
		var $empty = $('#amy-chat-empty');
		var $composer = $('#amy-chat-composer');
		var $paneHead = $('#amy-chat-pane-head');
		var $paneTitle = $('#amy-chat-pane-title');
		var $chips = $('#amy-chat-chips');
		var $error = $('#amy-chat-error');
		var $input = $('#amy-chat-input');
		var $send = $('#amy-chat-send');
		var $attach = $('#amy-chat-attach');
		var $file = $('#amy-chat-file');

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
		}

		function renderMarkdown(raw) {
			var html = escapeHtml(raw || '');
			html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
			html = html.replace(
				/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
				'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
			);
			html = html.replace(/\n/g, '<br>');
			return html;
		}

		function resizeComposer() {
			var el = $input[0];
			if (!el) {
				return;
			}
			el.style.height = 'auto';
			var maxPx = parseFloat(window.getComputedStyle(el).maxHeight);
			if (!maxPx || isNaN(maxPx)) {
				maxPx = Infinity;
			}
			el.style.height = Math.min(el.scrollHeight, maxPx) + 'px';
		}

		function api(path, options) {
			var opts = options || {};
			var headers = $.extend(
				{
					Accept: 'application/json',
					'X-WP-Nonce': cfg.restNonce,
				},
				opts.headers || {}
			);
			var init = {
				method: opts.method || 'GET',
				credentials: 'same-origin',
				headers: headers,
			};
			if (opts.body instanceof FormData) {
				init.body = opts.body;
			} else if (opts.body != null) {
				headers['Content-Type'] = 'application/json';
				init.body = JSON.stringify(opts.body);
			}
			return fetch(restUrl + path, init).then(function (res) {
				if (res.status === 204) {
					return { ok: true, status: 204, data: null };
				}
				return res
					.json()
					.then(function (data) {
						return { ok: res.ok, status: res.status, data: data };
					})
					.catch(function () {
						return { ok: false, status: res.status, data: null };
					});
			});
		}

		function relativeTime(ts) {
			var seconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(ts || 0)));
			if (seconds < 60) {
				return i18n.justNow || 'just now';
			}
			if (seconds < 3600) {
				return Math.floor(seconds / 60) + (i18n.minutesAgo || 'm ago');
			}
			if (seconds < 86400) {
				return Math.floor(seconds / 3600) + (i18n.hoursAgo || 'h ago');
			}
			return Math.floor(seconds / 86400) + (i18n.daysAgo || 'd ago');
		}

		function showError(msg) {
			$error.text(msg || i18n.error || 'Something went wrong.').prop('hidden', false);
		}

		function clearError() {
			$error.prop('hidden', true).text('');
		}

		function setSending(on) {
			sending = !!on;
			$send.prop('disabled', sending || uploading);
			$attach.prop('disabled', sending || uploading);
			$input.prop('disabled', sending);
			var sendLabel = sending
				? i18n.sending || 'Sending…'
				: i18n.send || 'Send';
			$send.attr('aria-label', sendLabel);
			$send.attr('title', sendLabel);
		}

		function conversationTitle(conv) {
			return (conv && conv.title) || i18n.untitled || '(untitled)';
		}

		function renderList() {
			$list.empty();
			if (!conversations.length) {
				$list.append(
					'<p class="amy-agent-chat__list-empty">' +
						escapeHtml(i18n.emptyState || 'No conversations yet.') +
						'</p>'
				);
				return;
			}
			conversations.forEach(function (conv) {
				var isActive = conv.id === activeId;
				var $item = $(
					'<div class="amy-agent-chat__item' +
						(isActive ? ' is-active' : '') +
						'" role="listitem" data-id="' +
						escapeHtml(conv.id) +
						'">' +
						'<button type="button" class="amy-agent-chat__item-main" data-amy-open="' +
						escapeHtml(conv.id) +
						'">' +
						'<span class="amy-agent-chat__item-title" data-amy-title>' +
						escapeHtml(conversationTitle(conv)) +
						'</span>' +
						'<span class="amy-agent-chat__item-meta">' +
						escapeHtml(relativeTime(conv.updated_at)) +
						'</span>' +
						'</button>' +
						'<div class="amy-agent-chat__item-actions">' +
						'<button type="button" class="amy-agent-chat__icon-btn" data-amy-rename="' +
						escapeHtml(conv.id) +
						'" title="' +
						escapeHtml(i18n.rename || 'Rename') +
						'" aria-label="' +
						escapeHtml(i18n.rename || 'Rename') +
						'"><span class="dashicons dashicons-edit" aria-hidden="true"></span></button>' +
						'<button type="button" class="amy-agent-chat__icon-btn" data-amy-export="' +
						escapeHtml(conv.id) +
						'" title="' +
						escapeHtml(i18n.export || 'Export') +
						'" aria-label="' +
						escapeHtml(i18n.export || 'Export') +
						'"><span class="dashicons dashicons-download" aria-hidden="true"></span></button>' +
						'<button type="button" class="amy-agent-chat__icon-btn amy-agent-chat__icon-btn--danger" data-amy-delete="' +
						escapeHtml(conv.id) +
						'" title="' +
						escapeHtml(i18n.delete || 'Delete') +
						'" aria-label="' +
						escapeHtml(i18n.delete || 'Delete') +
						'"><span class="dashicons dashicons-trash" aria-hidden="true"></span></button>' +
						'</div>' +
						'</div>'
				);
				$list.append($item);
			});
		}

		function renderChips() {
			$chips.empty();
			if (!pendingAttachments.length) {
				$chips.prop('hidden', true);
				return;
			}
			$chips.prop('hidden', false);
			pendingAttachments.forEach(function (att, index) {
				$chips.append(
					'<span class="amy-agent-chat__chip">' +
						'<span class="dashicons dashicons-media-default" aria-hidden="true"></span>' +
						'<span class="amy-agent-chat__chip-name">' +
						escapeHtml(att.filename) +
						'</span>' +
						'<button type="button" class="amy-agent-chat__chip-remove" data-amy-chip-remove="' +
						index +
						'" aria-label="' +
						escapeHtml(i18n.removeAttach || 'Remove attachment') +
						'">&times;</button>' +
						'</span>'
				);
			});
		}

		function renderAttachmentsHtml(attachments) {
			if (!attachments || !attachments.length) {
				return '';
			}
			var html = '<div class="amy-agent-chat__msg-atts">';
			attachments.forEach(function (att) {
				html +=
					'<a class="amy-agent-chat__msg-att" href="' +
					escapeHtml(att.url) +
					'" target="_blank" rel="noopener noreferrer">' +
					'<span class="dashicons dashicons-paperclip" aria-hidden="true"></span> ' +
					escapeHtml(att.filename || 'file') +
					'</a>';
			});
			html += '</div>';
			return html;
		}

		function appendBubble(role, content, attachments) {
			var isUser = role === 'user';
			var $bubble = $(
				'<div class="amy-agent-chat__msg amy-agent-chat__msg--' +
					(isUser ? 'user' : 'assistant') +
					'">' +
					'<div class="amy-agent-chat__bubble">' +
					'<div class="amy-agent-chat__bubble-text"></div>' +
					renderAttachmentsHtml(attachments) +
					'</div>' +
					'</div>'
			);
			$bubble.find('.amy-agent-chat__bubble-text').each(function () {
				if (isUser) {
					$(this).text(content || '');
				} else {
					$(this).html(renderMarkdown(content || ''));
				}
			});
			$thread.append($bubble);
			$thread.scrollTop($thread[0].scrollHeight);
		}

		function showThinking(on) {
			$thread.find('.amy-agent-chat__thinking').remove();
			if (!on) {
				return;
			}
			$thread.append(
				'<div class="amy-agent-chat__thinking">' +
					escapeHtml(i18n.thinking || 'Amy is thinking…') +
					'</div>'
			);
			$thread.scrollTop($thread[0].scrollHeight);
		}

		function renderThread(detail) {
			$thread.empty();
			$empty.prop('hidden', true);
			$composer.prop('hidden', false);
			$paneHead.prop('hidden', false);
			$paneTitle.text(conversationTitle(detail));
			var messages = (detail && detail.messages) || [];
			if (!messages.length) {
				$thread.append(
					'<p class="amy-agent-chat__thread-empty">' +
						escapeHtml(i18n.emptyThread || 'No messages yet.') +
						'</p>'
				);
			} else {
				messages.forEach(function (msg) {
					appendBubble(msg.role, msg.content, msg.attachments);
				});
			}
			setSending(false);
			$input.focus();
		}

		function showDraftPane() {
			activeId = null;
			pendingAttachments = [];
			renderChips();
			$thread.empty();
			$empty.prop('hidden', true);
			$composer.prop('hidden', false);
			$paneHead.prop('hidden', false);
			$paneTitle.text(i18n.newChat || 'New chat');
			clearError();
			renderList();
			setSending(false);
			$input.val('');
			resizeComposer();
			$input.trigger('focus');
		}

		function ensureActiveConversation() {
			if (activeId) {
				return Promise.resolve(activeId);
			}
			if (creatingPromise) {
				return creatingPromise;
			}
			clearError();
			creatingPromise = api('/admin-chat/conversations', {
				method: 'POST',
				body: {},
			})
				.then(function (res) {
					creatingPromise = null;
					if (!res.ok || !res.data || !res.data.id) {
						showError(
							(res.data && res.data.message) || i18n.error || 'Error'
						);
						return Promise.reject(new Error('create_failed'));
					}
					conversations.unshift(res.data);
					activeId = res.data.id;
					$paneHead.prop('hidden', false);
					$paneTitle.text(conversationTitle(res.data));
					$empty.prop('hidden', true);
					renderList();
					return activeId;
				})
				.catch(function (err) {
					creatingPromise = null;
					return Promise.reject(err);
				});
			return creatingPromise;
		}

		function loadList() {
			$listError.prop('hidden', true).text('');
			return api('/admin-chat/conversations').then(function (res) {
				if (!res.ok) {
					$listError
						.text(
							(res.data && res.data.message) ||
								i18n.loadError ||
								'Could not load conversations.'
						)
						.prop('hidden', false);
					conversations = [];
					renderList();
					return;
				}
				conversations = (res.data && res.data.conversations) || [];
				renderList();
			});
		}

		function openConversation(id) {
			clearError();
			pendingAttachments = [];
			renderChips();
			return api('/admin-chat/conversations/' + encodeURIComponent(id)).then(
				function (res) {
					if (!res.ok) {
						showError(
							(res.data && res.data.message) || i18n.error || 'Error'
						);
						return;
					}
					activeId = id;
					renderList();
					renderThread(res.data);
				}
			);
		}

		function deleteConversation(id) {
			if (!window.confirm(i18n.deleteConfirm || 'Delete this conversation?')) {
				return;
			}
			api('/admin-chat/conversations/' + encodeURIComponent(id), {
				method: 'DELETE',
			}).then(function (res) {
				if (!res.ok && res.status !== 204) {
					showError((res.data && res.data.message) || i18n.error || 'Error');
					return;
				}
				conversations = conversations.filter(function (c) {
					return c.id !== id;
				});
				if (activeId === id) {
					showDraftPane();
				} else {
					renderList();
				}
			});
		}

		function beginRename(id) {
			var conv = conversations.find(function (c) {
				return c.id === id;
			});
			if (!conv) {
				return;
			}
			var $item = $list.find('[data-id="' + id + '"]');
			var $title = $item.find('[data-amy-title]');
			if (!$title.length || $item.find('.amy-agent-chat__rename-input').length) {
				return;
			}
			var current = conversationTitle(conv);
			var $inputEl = $(
				'<input type="text" class="amy-agent-chat__rename-input" />'
			);
			$inputEl.val(conv.title || '');
			$title.replaceWith($inputEl);
			$inputEl.trigger('focus').trigger('select');

			function finish(save) {
				var next = $.trim($inputEl.val());
				var $span = $(
					'<span class="amy-agent-chat__item-title" data-amy-title></span>'
				);
				if (!save || !next || next === (conv.title || '')) {
					$span.text(current);
					$inputEl.replaceWith($span);
					return;
				}
				api('/admin-chat/conversations/' + encodeURIComponent(id), {
					method: 'PATCH',
					body: { title: next },
				}).then(function (res) {
					if (!res.ok) {
						showError((res.data && res.data.message) || i18n.error || 'Error');
						$span.text(current);
						$inputEl.replaceWith($span);
						return;
					}
					conv.title = res.data.title;
					$span.text(conversationTitle(conv));
					$inputEl.replaceWith($span);
					if (activeId === id) {
						$paneTitle.text(conversationTitle(conv));
					}
				});
			}

			$inputEl.on('keydown', function (e) {
				if (e.key === 'Enter') {
					e.preventDefault();
					finish(true);
				} else if (e.key === 'Escape') {
					e.preventDefault();
					finish(false);
				}
			});
			$inputEl.on('blur', function () {
				finish(true);
			});
		}

		function exportConversation(id) {
			fetch(restUrl + '/admin-chat/conversations/' + encodeURIComponent(id) + '/export', {
				method: 'GET',
				credentials: 'same-origin',
				headers: {
					Accept: 'application/json',
					'X-WP-Nonce': cfg.restNonce,
				},
			})
				.then(function (res) {
					if (!res.ok) {
						return res.json().then(function (data) {
							throw new Error(
								(data && data.message) || i18n.error || 'Export failed'
							);
						});
					}
					var disposition = res.headers.get('Content-Disposition') || '';
					var filename = 'conversation-' + id + '.json';
					var match = /filename="([^"]+)"/i.exec(disposition);
					if (match && match[1]) {
						filename = match[1];
					}
					return res.blob().then(function (blob) {
						return { blob: blob, filename: filename };
					});
				})
				.then(function (payload) {
					var url = URL.createObjectURL(payload.blob);
					var a = document.createElement('a');
					a.href = url;
					a.download = payload.filename;
					document.body.appendChild(a);
					a.click();
					a.remove();
					URL.revokeObjectURL(url);
				})
				.catch(function (err) {
					showError(err.message || i18n.error || 'Export failed');
				});
		}

		function sendMessage() {
			if (sending) {
				return;
			}
			var typed = $.trim($input.val());
			if (!typed && !pendingAttachments.length) {
				return;
			}
			var content = typed || '(attachment)';
			clearError();
			var attachments = pendingAttachments.slice();

			function doSend(conversationId) {
				appendBubble('user', typed || content, attachments);
				$input.val('');
				resizeComposer();
				pendingAttachments = [];
				renderChips();
				setSending(true);
				showThinking(true);

				api(
					'/admin-chat/conversations/' +
						encodeURIComponent(conversationId) +
						'/messages',
					{
						method: 'POST',
						body: {
							content: content,
							attachments: attachments,
						},
					}
				)
					.then(function (res) {
						showThinking(false);
						setSending(false);
						if (!res.ok) {
							$input.val(typed);
							resizeComposer();
							pendingAttachments = attachments.slice();
							renderChips();
							$thread.children('.amy-agent-chat__msg--user').last().remove();
							showError(
								(res.data && res.data.message) || i18n.error || 'Error'
							);
							return;
						}
						var reply =
							res.data &&
							res.data.reply &&
							res.data.reply.content
								? res.data.reply.content
								: '';
						appendBubble('assistant', reply);
						var idx = conversations.findIndex(function (c) {
							return c.id === conversationId;
						});
						if (idx >= 0) {
							conversations[idx].updated_at = Date.now() / 1000;
							if (!conversations[idx].title && typed) {
								conversations[idx].title = typed.slice(0, 60);
								$paneTitle.text(conversationTitle(conversations[idx]));
							}
							var moved = conversations.splice(idx, 1)[0];
							conversations.unshift(moved);
							renderList();
						}
					})
					.catch(function () {
						showThinking(false);
						setSending(false);
						$input.val(typed);
						resizeComposer();
						pendingAttachments = attachments.slice();
						renderChips();
						$thread.children('.amy-agent-chat__msg--user').last().remove();
						showError(i18n.error || 'Something went wrong.');
					});
			}

			ensureActiveConversation()
				.then(function (conversationId) {
					doSend(conversationId);
				})
				.catch(function () {
					setSending(false);
				});
		}

		function uploadFile(file) {
			if (!file || uploading) {
				return;
			}
			ensureActiveConversation()
				.then(function (conversationId) {
					uploading = true;
					setSending(sending);
					var fd = new FormData();
					fd.append('file', file);
					return api(
						'/admin-chat/conversations/' +
							encodeURIComponent(conversationId) +
							'/upload',
						{
							method: 'POST',
							body: fd,
						}
					);
				})
				.then(function (res) {
					uploading = false;
					setSending(sending);
					if (!res || !res.ok || !res.data || !res.data.url) {
						showError(
							(res && res.data && res.data.message) ||
								i18n.uploadError ||
								'Upload failed'
						);
						return;
					}
					pendingAttachments.push({
						url: res.data.url,
						filename: res.data.filename || file.name,
						content_type: res.data.content_type || file.type || null,
					});
					renderChips();
				})
				.catch(function () {
					uploading = false;
					setSending(sending);
					showError(i18n.uploadError || 'Upload failed');
				});
		}

		$('#amy-chat-new').on('click', function () {
			showDraftPane();
		});

		$list.on('click', '[data-amy-open]', function () {
			openConversation($(this).attr('data-amy-open'));
		});

		$list.on('click', '[data-amy-delete]', function (e) {
			e.stopPropagation();
			deleteConversation($(this).attr('data-amy-delete'));
		});

		$list.on('click', '[data-amy-rename]', function (e) {
			e.stopPropagation();
			beginRename($(this).attr('data-amy-rename'));
		});

		$list.on('click', '[data-amy-export]', function (e) {
			e.stopPropagation();
			exportConversation($(this).attr('data-amy-export'));
		});

		$attach.on('click', function () {
			$file.trigger('click');
		});

		$file.on('change', function () {
			var file = this.files && this.files[0];
			this.value = '';
			if (file) {
				uploadFile(file);
			}
		});

		$chips.on('click', '[data-amy-chip-remove]', function () {
			var index = parseInt($(this).attr('data-amy-chip-remove'), 10);
			if (!isNaN(index)) {
				pendingAttachments.splice(index, 1);
				renderChips();
			}
		});

		$send.on('click', sendMessage);

		$input.on('keydown', function (e) {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault();
				sendMessage();
			}
		});

		$input.on('input', resizeComposer);

		showDraftPane();
		loadList();
	});
})(jQuery);
