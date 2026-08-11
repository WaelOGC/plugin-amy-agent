/**
 * Amy Agent — Task Service (real CRUD via admin-ajax → Python service).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentTaskService || {};
		var tasks = [];
		var i18n = cfg.i18n || {};
		var assignees = Array.isArray(cfg.assignees) ? cfg.assignees : [];
		var assigneeByKey = {};
		var $board = $('#amy-agent-task-board');
		var $list = $('#amy-agent-task-list');
		var $listBody = $('#amy-agent-task-list-body');
		var $empty = $('#amy-agent-task-empty');
		var $modal = $('#amy-agent-task-modal');
		var $form = $('#amy-agent-task-form');
		var $formError = $('#amy-agent-task-form-error');
		var $notice = $('#amy-agent-task-notice');
		var $assigneeFilter = $('#amy-agent-filter-assignee');
		var $priorityFilter = $('#amy-agent-filter-priority');
		var $search = $('#amy-agent-filter-search');
		var $submitBtn = $('#amy-agent-task-submit');
		var $deleteBtn = $('#amy-agent-task-delete');
		var $statusField = $('#amy-agent-task-status-field');
		var $modalTitle = $('#amy-agent-task-modal-title');
		var $extension = $('#amy-agent-task-extension');
		var $extensionHours = $('#amy-agent-task-extension-hours');
		var $extensionSubmit = $('#amy-agent-task-extension-submit');
		var $extensionResult = $('#amy-agent-task-extension-result');
		var noticeTimer = null;
		var defaultStatus = 'todo';
		var currentUserId = parseInt(cfg.currentUserId, 10) || 0;

		assignees.forEach(function (a) {
			assigneeByKey[a.key] = a;
		});

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
		}

		function statusLabel(status) {
			var map = {
				todo: i18n.statusTodo || 'To Do',
				in_progress: i18n.statusInProgress || 'In Progress',
				waiting_extension: i18n.statusWaiting || 'Waiting on Extension',
				done: i18n.statusDone || 'Done',
			};
			return map[status] || status;
		}

		function formatDue(iso) {
			if (!iso) {
				return i18n.noDue || 'No due date';
			}
			var datePart = String(iso).slice(0, 10);
			var parts = datePart.split('-');
			if (parts.length !== 3) {
				return iso;
			}
			var months = [
				'Jan',
				'Feb',
				'Mar',
				'Apr',
				'May',
				'Jun',
				'Jul',
				'Aug',
				'Sep',
				'Oct',
				'Nov',
				'Dec',
			];
			var monthIndex = parseInt(parts[1], 10) - 1;
			var day = parseInt(parts[2], 10);
			if (isNaN(monthIndex) || isNaN(day) || !months[monthIndex]) {
				return iso;
			}
			return months[monthIndex] + ' ' + day;
		}

		function dueInputValue(iso) {
			if (!iso) {
				return '';
			}
			return String(iso).slice(0, 10);
		}

		function assigneeKeyFromTask(task) {
			if (task.assignee_type === 'amy') {
				return 'amy';
			}
			if (task.assignee_wp_user_id) {
				return 'user:' + String(task.assignee_wp_user_id);
			}
			return '';
		}

		function resolveAssignee(task) {
			var key = assigneeKeyFromTask(task);
			var meta = assigneeByKey[key];
			if (meta) {
				return meta;
			}
			if (task.assignee_type === 'amy') {
				return {
					key: 'amy',
					label: i18n.amy || 'Amy',
					type: 'amy',
					initials: 'A',
					color: '#FF7A18',
				};
			}
			return {
				key: key || 'unknown',
				label: 'User #' + (task.assignee_wp_user_id || '?'),
				type: 'human',
				initials: '?',
				color: '#555',
			};
		}

		function enrichTask(raw) {
			var meta = resolveAssignee(raw);
			return {
				id: raw.id,
				title: raw.title,
				description: raw.description || '',
				assignee: meta.label,
				assigneeKey: meta.key,
				assigneeType: raw.assignee_type,
				assigneeWpUserId: raw.assignee_wp_user_id,
				initials: meta.initials,
				color: meta.color,
				avatarUrl: raw.assignee_type === 'amy' ? cfg.amyAvatarUrl || '' : '',
				priority: raw.priority,
				status: raw.status,
				statusLabel: statusLabel(raw.status),
				due: formatDue(raw.due_date),
				dueDate: raw.due_date || '',
				createdBy: raw.created_by_wp_user_id,
				createdAt: raw.created_at,
				updatedAt: raw.updated_at,
				acknowledgedAt: raw.acknowledged_at,
				extensionTotalSeconds: raw.extension_total_seconds || 0,
			};
		}

		function avatarHtml(task) {
			if (task.assigneeType === 'amy' && task.avatarUrl) {
				return (
					'<span class="amy-agent-task-service__avatar is-amy" title="' +
					escapeHtml(task.assignee) +
					'">' +
					'<img src="' +
					escapeHtml(task.avatarUrl) +
					'" alt="" width="24" height="24" decoding="async" />' +
					'</span>'
				);
			}

			return (
				'<span class="amy-agent-task-service__avatar" style="background:' +
				escapeHtml(task.color || '#555') +
				'" title="' +
				escapeHtml(task.assignee) +
				'">' +
				escapeHtml(task.initials || '?') +
				'</span>'
			);
		}

		function cardHtml(task) {
			var urgent = task.priority === 'urgent';
			return (
				'<article class="amy-agent-task-service__card' +
				(urgent ? ' is-urgent' : '') +
				'" data-id="' +
				escapeHtml(task.id) +
				'" tabindex="0" role="button">' +
				'<div class="amy-agent-task-service__card-top">' +
				'<h3 class="amy-agent-task-service__card-title">' +
				escapeHtml(task.title) +
				'</h3>' +
				(urgent ? '<span class="amy-agent-task-service__urgent-badge">Urgent</span>' : '') +
				'</div>' +
				'<div class="amy-agent-task-service__card-meta">' +
				'<span class="amy-agent-task-service__assignee">' +
				avatarHtml(task) +
				'<span>' +
				escapeHtml(task.assignee) +
				'</span>' +
				'<span class="amy-agent-task-service__priority-flag' +
				(urgent ? ' is-urgent' : '') +
				'" aria-hidden="true">' +
				(urgent ? '⚑' : '⚐') +
				'</span>' +
				'</span>' +
				'<span class="amy-agent-task-service__due">' +
				escapeHtml(task.due) +
				'</span>' +
				'</div>' +
				'</article>'
			);
		}

		function rowHtml(task) {
			var urgent = task.priority === 'urgent';
			return (
				'<tr class="' +
				(urgent ? 'is-urgent' : '') +
				'" data-id="' +
				escapeHtml(task.id) +
				'" tabindex="0" role="button">' +
				'<td class="amy-agent-task-service__table-task">' +
				escapeHtml(task.title) +
				(urgent
					? ' <span class="amy-agent-task-service__urgent-badge">Urgent</span>'
					: '') +
				'</td>' +
				'<td><span class="amy-agent-task-service__assignee">' +
				avatarHtml(task) +
				'<span>' +
				escapeHtml(task.assignee) +
				'</span></span></td>' +
				'<td>' +
				escapeHtml(urgent ? 'Urgent' : 'Normal') +
				'</td>' +
				'<td>' +
				escapeHtml(task.statusLabel || task.status) +
				'</td>' +
				'<td>' +
				escapeHtml(task.due) +
				'</td>' +
				'</tr>'
			);
		}

		function populateAssigneeFilter() {
			var current = String($assigneeFilter.val() || '');
			$assigneeFilter.find('option:not(:first)').remove();
			var seen = {};
			tasks.forEach(function (task) {
				if (!task.assigneeKey || seen[task.assigneeKey]) {
					return;
				}
				seen[task.assigneeKey] = true;
				$assigneeFilter.append(
					$('<option></option>').val(task.assigneeKey).text(task.assignee)
				);
			});
			if (current) {
				$assigneeFilter.val(current);
			}
		}

		function getFilteredTasks() {
			var assignee = String($assigneeFilter.val() || '');
			var priority = String($priorityFilter.val() || '');
			var query = String($search.val() || '')
				.trim()
				.toLowerCase();

			return tasks.filter(function (task) {
				if (assignee && task.assigneeKey !== assignee) {
					return false;
				}
				if (priority && task.priority !== priority) {
					return false;
				}
				if (query && String(task.title || '').toLowerCase().indexOf(query) === -1) {
					return false;
				}
				return true;
			});
		}

		function render() {
			var filtered = getFilteredTasks();
			var byStatus = {
				todo: [],
				in_progress: [],
				waiting_extension: [],
				done: [],
			};

			filtered.forEach(function (task) {
				if (byStatus[task.status]) {
					byStatus[task.status].push(task);
				}
			});

			Object.keys(byStatus).forEach(function (status) {
				var $cards = $('[data-cards-for="' + status + '"]');
				var html = byStatus[status].map(cardHtml).join('');
				$cards.html(html);
				$('[data-count-for="' + status + '"]').text(String(byStatus[status].length));
			});

			if (!filtered.length) {
				$listBody.empty();
				$empty.text(i18n.noResults || 'No tasks match your filters.').prop('hidden', false);
			} else {
				$empty.prop('hidden', true).text('');
				$listBody.html(filtered.map(rowHtml).join(''));
			}
		}

		function setView(view) {
			var isBoard = view === 'board';
			$board.prop('hidden', !isBoard);
			$list.prop('hidden', isBoard);
			$('.amy-agent-task-service__view-btn').each(function () {
				var $btn = $(this);
				var active = $btn.data('amy-view') === view;
				$btn.toggleClass('is-active', active).attr('aria-selected', active ? 'true' : 'false');
			});
		}

		function showNotice(message, isError) {
			if (noticeTimer) {
				window.clearTimeout(noticeTimer);
			}
			$notice
				.text(message)
				.toggleClass('is-error', !!isError)
				.prop('hidden', false);
			noticeTimer = window.setTimeout(function () {
				$notice.prop('hidden', true).text('').removeClass('is-error');
			}, 3500);
		}

		function showFormError(message) {
			$formError.text(message || (i18n.error || 'Error')).prop('hidden', false);
		}

		function clearFormError() {
			$formError.prop('hidden', true).text('');
		}

		function parseAssigneeValue(value) {
			if (value === 'amy') {
				return { assignee_type: 'amy', assignee_wp_user_id: null };
			}
			if (value && value.indexOf('user:') === 0) {
				return {
					assignee_type: 'human',
					assignee_wp_user_id: parseInt(value.slice(5), 10) || 0,
				};
			}
			return null;
		}

		function resetForm(presetStatus) {
			$('#amy-agent-task-id').val('');
			$('#amy-agent-task-title').val('');
			$('#amy-agent-task-assignee').val('');
			$('#amy-agent-task-description').val('');
			$('#amy-agent-task-due').val('');
			$form.find('input[name="priority"][value="normal"]').prop('checked', true);
			$('#amy-agent-task-status').val(presetStatus || 'todo');
			$statusField.prop('hidden', true);
			$deleteBtn.prop('hidden', true);
			$extension.prop('hidden', true);
			$extensionHours.val('');
			$extensionResult.prop('hidden', true).text('');
			$modalTitle.text(i18n.newTask || 'New Task');
			$submitBtn.text(i18n.create || 'Create Task');
			clearFormError();
			defaultStatus = presetStatus || 'todo';
		}

		function maybeAcknowledge(task) {
			if (
				!task ||
				task.assigneeType !== 'human' ||
				String(task.assigneeWpUserId) !== String(currentUserId)
			) {
				return;
			}
			ajax('amy_task_acknowledge', { id: task.id });
		}

		function showExtensionFor(task) {
			var isAssignee =
				task.assigneeType === 'human' &&
				String(task.assigneeWpUserId) === String(currentUserId);
			var canExtend = isAssignee && task.status !== 'done';
			$extension.prop('hidden', !canExtend);
			$extensionHours.val('');
			$extensionResult.prop('hidden', true).text('');
		}

		function openCreateModal(presetStatus) {
			resetForm(presetStatus || 'todo');
			$modal.prop('hidden', false);
			$('#amy-agent-task-title').trigger('focus');
		}

		function openEditModal(task) {
			resetForm(task.status);
			$('#amy-agent-task-id').val(task.id);
			$('#amy-agent-task-title').val(task.title);
			$('#amy-agent-task-assignee').val(task.assigneeKey);
			$('#amy-agent-task-description').val(task.description || '');
			$('#amy-agent-task-due').val(dueInputValue(task.dueDate));
			$form.find('input[name="priority"][value="' + (task.priority || 'normal') + '"]').prop('checked', true);
			$('#amy-agent-task-status').val(task.status);
			$statusField.prop('hidden', false);
			$deleteBtn.prop('hidden', false);
			showExtensionFor(task);
			$modalTitle.text(i18n.editTask || 'Edit Task');
			$submitBtn.text(i18n.save || 'Save changes');
			$modal.prop('hidden', false);
			$('#amy-agent-task-title').trigger('focus');
			maybeAcknowledge(task);
		}

		function closeModal() {
			$modal.prop('hidden', true);
			clearFormError();
		}

		function findTask(id) {
			for (var i = 0; i < tasks.length; i++) {
				if (tasks[i].id === id) {
					return tasks[i];
				}
			}
			return null;
		}

		window.AmyAgentTaskService = {
			openTaskById: function (id) {
				var task = findTask(id);
				if (task) {
					openEditModal(task);
					return;
				}
				loadTasks().done(function () {
					var found = findTask(id);
					if (found) {
						openEditModal(found);
					}
				});
			},
		};

		function ajax(action, data) {
			var payload = $.extend(
				{
					action: action,
					nonce: cfg.nonce,
				},
				data || {}
			);
			return $.post(cfg.ajaxUrl, payload);
		}

		function applyStats(stats) {
			if (!stats) {
				return;
			}
			$('[data-stat-value="open_tasks"]').text(String(stats.open_tasks != null ? stats.open_tasks : 0));
			$('[data-stat-value="urgent_tasks"]').text(String(stats.urgent_tasks != null ? stats.urgent_tasks : 0));
			$('[data-stat-value="completed_this_week"]').text(
				String(stats.completed_this_week != null ? stats.completed_this_week : 0)
			);
			$('[data-stat-value="team_completion_rate"]').text(
				String(stats.team_completion_rate != null ? stats.team_completion_rate : 0) + '%'
			);
		}

		function refreshStats() {
			return ajax('amy_task_stats')
				.done(function (response) {
					if (response && response.success && response.data) {
						applyStats(response.data);
					}
				});
		}

		function loadTasks() {
			return ajax('amy_task_list')
				.done(function (response) {
					if (!response || !response.success) {
						var msg =
							response && response.data && response.data.message
								? response.data.message
								: i18n.loadError || 'Could not load tasks.';
						showNotice(msg, true);
						tasks = [];
						render();
						return;
					}
					var rawList =
						response.data && Array.isArray(response.data.tasks) ? response.data.tasks : [];
					tasks = rawList.map(enrichTask);
					populateAssigneeFilter();
					render();
				})
				.fail(function () {
					showNotice(i18n.loadError || 'Could not load tasks.', true);
					tasks = [];
					render();
				});
		}

		function extractError(response, xhr) {
			if (response && response.data && response.data.message) {
				return response.data.message;
			}
			if (xhr && xhr.responseJSON && xhr.responseJSON.data && xhr.responseJSON.data.message) {
				return xhr.responseJSON.data.message;
			}
			return i18n.error || 'Something went wrong. Please try again.';
		}

		setView('board');
		loadTasks();

		if (cfg.openNewTask) {
			openCreateModal('todo');
		}

		$('.amy-agent-task-service__view-btn').on('click', function () {
			setView($(this).data('amy-view'));
		});

		$assigneeFilter.add($priorityFilter).on('change', render);
		$search.on('input', render);

		$('#amy-agent-task-new').on('click', function (event) {
			event.preventDefault();
			openCreateModal('todo');
		});

		$('[data-amy-quick-add]').on('click', function (event) {
			event.preventDefault();
			openCreateModal($(this).data('amy-quick-add') || 'todo');
		});

		$modal.on('click', '[data-amy-modal-close]', function (event) {
			event.preventDefault();
			closeModal();
		});

		$(document).on('keydown', function (event) {
			if (event.key === 'Escape' && !$modal.prop('hidden')) {
				closeModal();
			}
		});

		$board.on('click', '.amy-agent-task-service__card', function () {
			var task = findTask($(this).data('id'));
			if (task) {
				openEditModal(task);
			}
		});

		$board.on('keydown', '.amy-agent-task-service__card', function (event) {
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault();
				$(this).trigger('click');
			}
		});

		$listBody.on('click', 'tr[data-id]', function () {
			var task = findTask($(this).data('id'));
			if (task) {
				openEditModal(task);
			}
		});

		$listBody.on('keydown', 'tr[data-id]', function (event) {
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault();
				$(this).trigger('click');
			}
		});

		$deleteBtn.on('click', function (event) {
			event.preventDefault();
			var id = String($('#amy-agent-task-id').val() || '');
			if (!id) {
				return;
			}
			if (!window.confirm(i18n.deleteConfirm || 'Delete this task?')) {
				return;
			}

			$deleteBtn.prop('disabled', true);
			ajax('amy_task_delete', { id: id })
				.done(function (response) {
					if (!response || !response.success) {
						showFormError(extractError(response));
						return;
					}
					closeModal();
					showNotice(i18n.deleteSuccess || 'Task deleted.');
					loadTasks();
					refreshStats();
				})
				.fail(function (xhr) {
					showFormError(extractError(null, xhr));
				})
				.always(function () {
					$deleteBtn.prop('disabled', false);
				});
		});

		$extensionSubmit.on('click', function (event) {
			event.preventDefault();
			var id = String($('#amy-agent-task-id').val() || '');
			var hours = parseFloat($extensionHours.val(), 10);
			$extensionResult.prop('hidden', true).text('');
			if (!id) {
				return;
			}
			if (!hours || hours <= 0) {
				$extensionResult
					.text(i18n.extensionInvalid || 'Enter a positive number of hours.')
					.prop('hidden', false);
				return;
			}
			$extensionSubmit.prop('disabled', true);
			ajax('amy_task_extension_request', { id: id, hours: hours })
				.done(function (response) {
					if (!response || !response.success || !response.data) {
						$extensionResult
							.text(extractError(response))
							.prop('hidden', false);
						return;
					}
					var outcome = response.data.outcome || '';
					var msg =
						outcome === 'auto_approved'
							? i18n.extensionAuto || 'Extension granted automatically. Due date updated.'
							: i18n.extensionPending ||
							  'Extension request sent — awaiting creator approval.';
					$extensionResult.text(msg).prop('hidden', false);
					loadTasks();
					if (window.AmyAgentNotifications && window.AmyAgentNotifications.reload) {
						window.AmyAgentNotifications.reload();
					}
				})
				.fail(function (xhr) {
					$extensionResult.text(extractError(null, xhr)).prop('hidden', false);
				})
				.always(function () {
					$extensionSubmit.prop('disabled', false);
				});
		});

		$form.on('submit', function (event) {
			event.preventDefault();
			clearFormError();

			var id = String($('#amy-agent-task-id').val() || '');
			var title = String($('#amy-agent-task-title').val() || '').trim();
			var assigneeVal = String($('#amy-agent-task-assignee').val() || '');
			var parsed = parseAssigneeValue(assigneeVal);
			var priority = String($form.find('input[name="priority"]:checked').val() || 'normal');
			var dueDate = String($('#amy-agent-task-due').val() || '');
			var description = String($('#amy-agent-task-description').val() || '');
			var statusVal = id
				? String($('#amy-agent-task-status').val() || 'todo')
				: defaultStatus || 'todo';

			if (!title) {
				showFormError(i18n.titleRequired || 'Title is required.');
				$('#amy-agent-task-title').trigger('focus');
				return;
			}
			if (!parsed || (parsed.assignee_type === 'human' && !parsed.assignee_wp_user_id)) {
				showFormError(i18n.assigneeRequired || 'Please select an assignee.');
				$('#amy-agent-task-assignee').trigger('focus');
				return;
			}

			var isEdit = !!id;
			var action = isEdit ? 'amy_task_update' : 'amy_task_create';
			var data = {
				title: title,
				assignee_type: parsed.assignee_type,
				priority: priority,
				status: statusVal,
				due_date: dueDate,
				description: description,
			};

			if (parsed.assignee_type === 'human') {
				data.assignee_wp_user_id = parsed.assignee_wp_user_id;
			} else {
				data.assignee_wp_user_id = '';
			}

			if (isEdit) {
				data.id = id;
			} else {
				data.created_by_wp_user_id = cfg.currentUserId || 0;
			}

			var busyLabel = i18n.saving || 'Saving…';
			var idleLabel = isEdit ? i18n.save || 'Save changes' : i18n.create || 'Create Task';
			$submitBtn.prop('disabled', true).text(busyLabel);

			ajax(action, data)
				.done(function (response) {
					if (!response || !response.success) {
						showFormError(extractError(response));
						return;
					}
					closeModal();
					showNotice(
						isEdit
							? i18n.updateSuccess || 'Task updated.'
							: i18n.createSuccess || 'Task created.'
					);
					loadTasks();
					refreshStats();
				})
				.fail(function (xhr) {
					showFormError(extractError(null, xhr));
				})
				.always(function () {
					$submitBtn.prop('disabled', false).text(idleLabel);
				});
		});
	});
})(jQuery);
