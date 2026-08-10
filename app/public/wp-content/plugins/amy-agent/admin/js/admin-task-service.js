/**
 * Amy Agent — Task Service (visual phase: board/list toggle + modal UI).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentTaskService || {};
		var tasks = Array.isArray(cfg.tasks) ? cfg.tasks.slice() : [];
		var i18n = cfg.i18n || {};
		var $board = $('#amy-agent-task-board');
		var $list = $('#amy-agent-task-list');
		var $listBody = $('#amy-agent-task-list-body');
		var $empty = $('#amy-agent-task-empty');
		var $modal = $('#amy-agent-task-modal');
		var $assigneeFilter = $('#amy-agent-filter-assignee');
		var $priorityFilter = $('#amy-agent-filter-priority');
		var $search = $('#amy-agent-filter-search');

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
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
				'">' +
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
				'">' +
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

		function openModal() {
			$modal.prop('hidden', false);
			$('#amy-agent-task-title').trigger('focus');
		}

		function closeModal() {
			$modal.prop('hidden', true);
		}

		populateAssigneeFilter();
		render();
		setView('board');

		$('.amy-agent-task-service__view-btn').on('click', function () {
			setView($(this).data('amy-view'));
		});

		$assigneeFilter.add($priorityFilter).on('change', render);
		$search.on('input', render);

		$('#amy-agent-task-new').on('click', function (event) {
			event.preventDefault();
			openModal();
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

		$('#amy-agent-task-create').on('click', function (event) {
			event.preventDefault();
		});

		$('#amy-agent-task-form').on('submit', function (event) {
			event.preventDefault();
		});
	});
})(jQuery);
