/**
 * Shared Amy Agent notification bell (Task Service + My Profile).
 */
(function ($) {
	'use strict';

	window.AmyAgentNotifications = window.AmyAgentNotifications || {};

	window.AmyAgentNotifications.init = function (cfg) {
		cfg = cfg || window.amyAgentNotifications || {};
		var i18n = cfg.i18n || {};
		var $root = $('#amy-agent-notifications');
		if (!$root.length) {
			return;
		}

		var $toggle = $root.find('.amy-agent-notifications__toggle');
		var $panel = $root.find('.amy-agent-notifications__panel');
		var $list = $root.find('.amy-agent-notifications__list');
		var $empty = $root.find('.amy-agent-notifications__empty');
		var $badge = $root.find('.amy-agent-notifications__badge');
		var open = false;

		function ajax(action, data) {
			return $.post(
				cfg.ajaxUrl,
				$.extend({ action: action, nonce: cfg.nonce }, data || {})
			);
		}

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
		}

		function setBadge(count) {
			if (count > 0) {
				$badge.text(String(count)).prop('hidden', false);
			} else {
				$badge.text('').prop('hidden', true);
			}
		}

		function itemHtml(n) {
			var actions = '';
			var payload = n.action_payload || {};
			if (n.requires_action && n.type === 'extension_needs_approval' && payload.extension_request_id) {
				actions =
					'<div class="amy-agent-notifications__actions">' +
					'<button type="button" class="amy-agent-notifications__action" data-amy-ext-approve="' +
					escapeHtml(payload.extension_request_id) +
					'">' +
					escapeHtml(i18n.approve || 'Approve') +
					'</button>' +
					'<button type="button" class="amy-agent-notifications__action is-deny" data-amy-ext-deny="' +
					escapeHtml(payload.extension_request_id) +
					'">' +
					escapeHtml(i18n.deny || 'Deny') +
					'</button>' +
					'</div>';
			} else if (n.requires_action && n.type === 'task_expired' && payload.task_id) {
				actions =
					'<div class="amy-agent-notifications__actions">' +
					'<button type="button" class="amy-agent-notifications__action" data-amy-open-task="' +
					escapeHtml(payload.task_id) +
					'">' +
					escapeHtml(i18n.openTask || 'Open task') +
					'</button>' +
					'<button type="button" class="amy-agent-notifications__action is-ghost" data-amy-dismiss="' +
					escapeHtml(n.id) +
					'">' +
					escapeHtml(i18n.acknowledge || 'Acknowledge') +
					'</button>' +
					'</div>';
			} else if (n.requires_action && payload.task_id) {
				actions =
					'<div class="amy-agent-notifications__actions">' +
					'<button type="button" class="amy-agent-notifications__action" data-amy-open-task="' +
					escapeHtml(payload.task_id) +
					'">' +
					escapeHtml(i18n.openTask || 'Open task') +
					'</button>' +
					'</div>';
			}

			return (
				'<li class="amy-agent-notifications__item" data-id="' +
				escapeHtml(n.id) +
				'">' +
				'<p class="amy-agent-notifications__message">' +
				escapeHtml(n.message) +
				'</p>' +
				actions +
				'<button type="button" class="amy-agent-notifications__dismiss" data-amy-dismiss="' +
				escapeHtml(n.id) +
				'" aria-label="' +
				escapeHtml(i18n.dismiss || 'Dismiss') +
				'">×</button>' +
				'</li>'
			);
		}

		function render(notifications) {
			notifications = Array.isArray(notifications) ? notifications : [];
			setBadge(notifications.length);
			if (!notifications.length) {
				$list.empty();
				$empty.prop('hidden', false);
				return;
			}
			$empty.prop('hidden', true);
			$list.html(notifications.map(itemHtml).join(''));
		}

		function load() {
			return ajax('amy_notifications_list', { unread_only: '1' })
				.done(function (response) {
					if (!response || !response.success) {
						render([]);
						return;
					}
					var list =
						response.data && Array.isArray(response.data.notifications)
							? response.data.notifications
							: [];
					render(list);
				})
				.fail(function () {
					render([]);
				});
		}

		function markRead(id) {
			return ajax('amy_notification_read', { id: id });
		}

		function setOpen(next) {
			open = !!next;
			$panel.prop('hidden', !open);
			$toggle.attr('aria-expanded', open ? 'true' : 'false');
		}

		$toggle.on('click', function (event) {
			event.preventDefault();
			setOpen(!open);
		});

		$(document).on('click', function (event) {
			if (!open) {
				return;
			}
			if (!$root.is(event.target) && $root.has(event.target).length === 0) {
				setOpen(false);
			}
		});

		$list.on('click', '[data-amy-dismiss]', function (event) {
			event.preventDefault();
			var id = $(this).data('amy-dismiss');
			markRead(id).always(load);
		});

		$list.on('click', '[data-amy-ext-approve]', function (event) {
			event.preventDefault();
			var id = $(this).data('amy-ext-approve');
			var $item = $(this).closest('.amy-agent-notifications__item');
			ajax('amy_extension_approve', { id: id })
				.done(function () {
					if ($item.data('id')) {
						markRead($item.data('id'));
					}
				})
				.always(load);
		});

		$list.on('click', '[data-amy-ext-deny]', function (event) {
			event.preventDefault();
			var id = $(this).data('amy-ext-deny');
			var $item = $(this).closest('.amy-agent-notifications__item');
			ajax('amy_extension_deny', { id: id })
				.done(function () {
					if ($item.data('id')) {
						markRead($item.data('id'));
					}
				})
				.always(load);
		});

		$list.on('click', '[data-amy-open-task]', function (event) {
			event.preventDefault();
			var taskId = String($(this).data('amy-open-task') || '');
			var $item = $(this).closest('.amy-agent-notifications__item');
			if ($item.data('id')) {
				markRead($item.data('id'));
			}
			setOpen(false);
			if (typeof window.AmyAgentTaskService !== 'undefined' && window.AmyAgentTaskService.openTaskById) {
				window.AmyAgentTaskService.openTaskById(taskId);
			} else if (cfg.taskServiceUrl) {
				window.location.href = cfg.taskServiceUrl;
			}
			load();
		});

		load();
		window.AmyAgentNotifications.reload = load;
	};

	$(function () {
		if (window.amyAgentNotifications) {
			window.AmyAgentNotifications.init(window.amyAgentNotifications);
		}
	});
})(jQuery);
