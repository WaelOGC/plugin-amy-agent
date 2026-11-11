/**
 * Shared Amy Agent notification bell (Task Service + My Profile).
 */
(function ($) {
	'use strict';

	window.AmyAgentNotifications = window.AmyAgentNotifications || {};

	window.AmyAgentNotifications.init = function (cfg) {
		cfg = cfg || window.amyAgentNotifications || {};
		var i18n = cfg.i18n || {};
		var assignees = Array.isArray(cfg.assignees) ? cfg.assignees : [];
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

		function assigneeOptionsHtml(selectedId) {
			var html =
				'<option value="">' +
				escapeHtml(i18n.selectAssignee || 'Select someone…') +
				'</option>';
			assignees.forEach(function (a) {
				html +=
					'<option value="' +
					escapeHtml(String(a.id)) +
					'"' +
					(String(a.id) === String(selectedId || '') ? ' selected' : '') +
					'>' +
					escapeHtml(a.label) +
					'</option>';
			});
			return html;
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
			} else if (
				n.requires_action &&
				payload.task_id &&
				(n.type === 'task_expired' || n.type === 'amy_execution_failed')
			) {
				var choices = Array.isArray(payload.choices) ? payload.choices : [];
				var amyCapable = !!payload.amy_capable;
				var amyEnabled = !!payload.amy_execution_enabled;
				var showAmy = choices.indexOf('amy_take') !== -1 || amyCapable;
				var showSame = choices.length === 0 || choices.indexOf('reassign_same') !== -1;
				var showOther = choices.length === 0 || choices.indexOf('reassign_other') !== -1;
				var showAck = choices.length === 0 || choices.indexOf('acknowledge_manual') !== -1;
				actions =
					'<div class="amy-agent-notifications__actions amy-agent-notifications__actions--expiry">';
				if (showSame) {
					actions +=
						'<button type="button" class="amy-agent-notifications__action" data-amy-expiry-same="' +
						escapeHtml(payload.task_id) +
						'">' +
						escapeHtml(i18n.reassignSame || 'Reassign same') +
						'</button>';
				}
				if (showOther) {
					actions +=
						'<button type="button" class="amy-agent-notifications__action" data-amy-expiry-other-toggle="' +
						escapeHtml(payload.task_id) +
						'">' +
						escapeHtml(i18n.reassignOther || 'Reassign…') +
						'</button>';
				}
				if (showAck) {
					actions +=
						'<button type="button" class="amy-agent-notifications__action is-ghost" data-amy-expiry-ack="' +
						escapeHtml(payload.task_id) +
						'">' +
						escapeHtml(i18n.acknowledge || 'Acknowledge') +
						'</button>';
				}
				if (showAmy) {
					actions +=
						'<button type="button" class="amy-agent-notifications__action is-ghost" data-amy-expiry-amy="' +
						escapeHtml(payload.task_id) +
						'"' +
						(amyEnabled && amyCapable ? '' : ' disabled') +
						' title="' +
						escapeHtml(
							amyEnabled && amyCapable
								? i18n.amyTake || 'Let Amy take it'
								: i18n.amyTakeDisabled ||
										'Only Amy-capable (digital / in-system) tasks can be handed to Amy.'
						) +
						'">' +
						escapeHtml(i18n.amyTake || 'Let Amy take it') +
						'</button>';
				}
				actions +=
					'<button type="button" class="amy-agent-notifications__action is-ghost" data-amy-open-task="' +
					escapeHtml(payload.task_id) +
					'">' +
					escapeHtml(i18n.openTask || 'Open task') +
					'</button>' +
					'</div>' +
					'<div class="amy-agent-notifications__reassign" data-amy-reassign-for="' +
					escapeHtml(payload.task_id) +
					'" hidden>' +
					'<select class="amy-agent-notifications__reassign-select">' +
					assigneeOptionsHtml() +
					'</select>' +
					'<button type="button" class="amy-agent-notifications__action" data-amy-expiry-other-confirm="' +
					escapeHtml(payload.task_id) +
					'">' +
					escapeHtml(i18n.confirmReassign || 'Confirm reassign') +
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

		function runExpiryAction(taskId, action, extra, $item) {
			var data = $.extend(
				{
					id: taskId,
					expiry_action: action,
				},
				extra || {}
			);
			return ajax('amy_task_expiry_action', data)
				.done(function (response) {
					if (!response || !response.success) {
						window.alert(
							(response && response.data && response.data.message) ||
								i18n.reassignError ||
								'Could not reassign.'
						);
						return;
					}
					if ($item && $item.data('id')) {
						markRead($item.data('id'));
					}
					if (window.AmyAgentTaskService && window.AmyAgentTaskService.reload) {
						window.AmyAgentTaskService.reload();
					}
				})
				.fail(function (xhr) {
					var msg =
						xhr &&
						xhr.responseJSON &&
						xhr.responseJSON.data &&
						xhr.responseJSON.data.message
							? xhr.responseJSON.data.message
							: i18n.reassignError || 'Could not reassign.';
					window.alert(msg);
				})
				.always(load);
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

		$list.on('click', '[data-amy-expiry-same]', function (event) {
			event.preventDefault();
			var taskId = String($(this).data('amy-expiry-same') || '');
			var $item = $(this).closest('.amy-agent-notifications__item');
			runExpiryAction(taskId, 'reassign_same', {}, $item);
		});

		$list.on('click', '[data-amy-expiry-other-toggle]', function (event) {
			event.preventDefault();
			var taskId = String($(this).data('amy-expiry-other-toggle') || '');
			var $box = $list.find('[data-amy-reassign-for="' + taskId + '"]');
			$box.prop('hidden', !$box.prop('hidden'));
		});

		$list.on('click', '[data-amy-expiry-other-confirm]', function (event) {
			event.preventDefault();
			var taskId = String($(this).data('amy-expiry-other-confirm') || '');
			var $item = $(this).closest('.amy-agent-notifications__item');
			var uid = parseInt($item.find('.amy-agent-notifications__reassign-select').val(), 10) || 0;
			if (!uid) {
				window.alert(i18n.selectAssignee || 'Select someone…');
				return;
			}
			runExpiryAction(taskId, 'reassign_other', { assignee_wp_user_id: uid }, $item);
		});

		$list.on('click', '[data-amy-expiry-ack]', function (event) {
			event.preventDefault();
			var taskId = String($(this).data('amy-expiry-ack') || '');
			var $item = $(this).closest('.amy-agent-notifications__item');
			runExpiryAction(taskId, 'acknowledge_manual', {}, $item);
		});

		$list.on('click', '[data-amy-expiry-amy]', function (event) {
			event.preventDefault();
			if ($(this).prop('disabled')) {
				window.alert(i18n.amyTakeDisabled || 'Amy execution is not live yet.');
				return;
			}
			var taskId = String($(this).data('amy-expiry-amy') || '');
			var $item = $(this).closest('.amy-agent-notifications__item');
			runExpiryAction(taskId, 'amy_take', {}, $item);
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
