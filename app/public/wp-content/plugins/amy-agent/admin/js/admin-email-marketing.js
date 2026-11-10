/**
 * Amy Agent — Email Marketing admin (Analytics audience + analysis, draft / approve only).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentEmailMarketing || {};
		var i18n = cfg.i18n || {};
		var $tbody = $('#amy-agent-email-body');
		var $empty = $('#amy-agent-email-empty');
		var $error = $('#amy-agent-email-error');
		var $statusMsg = $('#amy-agent-email-status');
		var $count = $('#amy-agent-email-count');
		var $statusFilters = $('[data-amy-email-status]');
		var $statButtons = $('[data-amy-email-stat]');
		var $to = $('#amy-agent-email-to');
		var $subject = $('#amy-agent-email-subject');
		var $body = $('#amy-agent-email-message');
		var $signals = $('#amy-agent-email-signals');
		var $signalsEmpty = $('#amy-agent-email-signals-empty');
		var currentStatus = '';
		var selected = null;
		var allLeads = [];
		var DRAFT_KEY = 'amyAgentEmailDraft';

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
		}

		function formatLastSeen(ts) {
			var seconds = parseFloat(ts);
			if (!seconds) {
				return '—';
			}
			var diff = Math.max(0, Date.now() / 1000 - seconds);
			if (diff < 60) {
				return i18n.justNow || 'just now';
			}
			if (diff < 3600) {
				return Math.floor(diff / 60) + (i18n.minutesAgo || 'm ago');
			}
			if (diff < 86400) {
				return Math.floor(diff / 3600) + (i18n.hoursAgo || 'h ago');
			}
			return Math.floor(diff / 86400) + (i18n.daysAgo || 'd ago');
		}

		function statusLabel(status) {
			if (status === 'hot') {
				return i18n.statusHot || 'Hot';
			}
			if (status === 'warm') {
				return i18n.statusWarm || 'Warm';
			}
			return i18n.statusCold || 'Cold';
		}

		function hasEmail(lead) {
			return !!(lead && lead.lead_email && String(lead.lead_email).trim());
		}

		function emailLeads() {
			return allLeads.filter(hasEmail);
		}

		function showStatus(msg) {
			if (!msg) {
				$statusMsg.attr('hidden', 'hidden').text('');
				return;
			}
			$statusMsg.removeAttr('hidden').text(msg);
		}

		function showError(msg) {
			$error.removeAttr('hidden').text(msg || i18n.loadError || 'Could not load audience.');
			$tbody.empty();
			$empty.attr('hidden', 'hidden');
			$count.text('');
			renderAnalysis([]);
		}

		function setStatusFilter(next) {
			currentStatus = String(next || '');
			$statusFilters.removeClass('is-active').attr('aria-selected', 'false');
			$statusFilters.filter('[data-amy-email-status="' + currentStatus + '"]')
				.addClass('is-active')
				.attr('aria-selected', 'true');
			$statButtons.removeClass('is-active');
			$statButtons.filter('[data-amy-email-stat="' + currentStatus + '"]').addClass('is-active');
			renderTable();
		}

		function selectLead(lead) {
			selected = lead || null;
			$tbody.find('tr').removeClass('is-selected');
			$tbody.find('input[type="radio"]').prop('checked', false);
			if (!selected) {
				$to.val('');
				return;
			}
			var $row = $tbody.find('tr[data-session-id="' + selected.session_id + '"]');
			$row.addClass('is-selected');
			$row.find('input[type="radio"]').prop('checked', true);
			$to.val(selected.lead_email || '');
		}

		function renderAnalysis(leadsWithEmail) {
			var totalVisitors = allLeads.length;
			var totalEmail = leadsWithEmail.length;
			var hot = 0;
			var warm = 0;
			var cold = 0;

			leadsWithEmail.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				if (status === 'hot') {
					hot += 1;
				} else if (status === 'warm') {
					warm += 1;
				} else {
					cold += 1;
				}
			});

			$('#amy-agent-email-stat-total').text(String(totalEmail));
			$('#amy-agent-email-stat-hot').text(String(hot));
			$('#amy-agent-email-stat-warm').text(String(warm));
			$('#amy-agent-email-stat-cold').text(String(cold));

			var $coverageValue = $('#amy-agent-email-coverage-value');
			var $meter = $('#amy-agent-email-coverage-meter');
			if (!totalVisitors) {
				$coverageValue.text(i18n.coverageEmpty || 'No Analytics visitors yet.');
				$meter.css('width', '0%');
			} else {
				var pct = Math.round((totalEmail / totalVisitors) * 100);
				var tpl = i18n.coverageValue || '%1$d of %2$d visitors (%3$s%%)';
				$coverageValue.text(
					tpl
						.replace('%1$d', String(totalEmail))
						.replace('%2$d', String(totalVisitors))
						.replace('%3$s', String(pct))
				);
				$meter.css('width', Math.min(100, pct) + '%');
			}

			var recent = leadsWithEmail
				.slice()
				.sort(function (a, b) {
					return (parseFloat(b.last_seen_at) || 0) - (parseFloat(a.last_seen_at) || 0);
				})
				.slice(0, 5);

			$signals.empty();
			if (!recent.length) {
				$signalsEmpty.removeAttr('hidden');
				return;
			}

			$signalsEmpty.attr('hidden', 'hidden');
			recent.forEach(function (lead) {
				var email = lead.lead_email || '';
				var signal = lead.signal || i18n.unknownSignal || 'No signal';
				var when = formatLastSeen(lead.last_seen_at);
				var status = lead.lead_status || 'cold';
				var rowTpl = i18n.signalRow || '%1$s · %2$s · %3$s';
				var line = rowTpl
					.replace('%1$s', email)
					.replace('%2$s', signal)
					.replace('%3$s', when);
				var li = document.createElement('li');
				li.className = 'amy-agent-email__signal';
				li.innerHTML =
					'<span class="amy-agent-email__badge amy-agent-email__badge--' +
					escapeHtml(status) +
					'">' +
					escapeHtml(statusLabel(status)) +
					'</span>' +
					'<span class="amy-agent-email__signal-text">' +
					escapeHtml(line) +
					'</span>';
				$signals.append(li);
			});
		}

		function renderTable() {
			$error.attr('hidden', 'hidden').text('');
			$tbody.empty();

			var withEmail = emailLeads();
			renderAnalysis(withEmail);

			var filtered = withEmail.filter(function (lead) {
				if (!currentStatus) {
					return true;
				}
				return (lead.lead_status || 'cold') === currentStatus;
			});

			var countTpl = i18n.audienceCount || '%d shown';
			$count.text(countTpl.replace('%d', String(filtered.length)));

			if (!filtered.length) {
				$empty.removeAttr('hidden');
				selectLead(null);
				return;
			}

			$empty.attr('hidden', 'hidden');
			filtered.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				var visitor = lead.visitor_label || ('Visitor ' + (lead.session_id_short || ''));
				var email = lead.lead_email || '';
				var tr = document.createElement('tr');
				tr.setAttribute('data-session-id', lead.session_id || '');
				tr.innerHTML =
					'<td class="amy-agent-email__col-check">' +
					'<input type="radio" name="amy-email-recipient" value="' +
					escapeHtml(lead.session_id || '') +
					'" aria-label="' +
					escapeHtml(email) +
					'" />' +
					'</td>' +
					'<td class="amy-agent-email__contact"><a href="mailto:' +
					escapeHtml(email) +
					'">' +
					escapeHtml(email) +
					'</a></td>' +
					'<td class="amy-agent-email__visitor">' +
					escapeHtml(visitor) +
					'</td>' +
					'<td><span class="amy-agent-email__badge amy-agent-email__badge--' +
					escapeHtml(status) +
					'">' +
					escapeHtml(statusLabel(status)) +
					'</span></td>' +
					'<td>' +
					escapeHtml(lead.signal || '—') +
					' <span class="amy-agent-email__tag">' +
					escapeHtml(i18n.leadOnly || 'Lead capture') +
					'</span></td>' +
					'<td>' +
					escapeHtml(formatLastSeen(lead.last_seen_at)) +
					'</td>';
				$tbody.append(tr);

				$(tr).on('click', function (evt) {
					if ($(evt.target).closest('a').length) {
						return;
					}
					selectLead(lead);
				});
			});

			if (selected) {
				var stillThere = filtered.some(function (lead) {
					return lead.session_id === selected.session_id;
				});
				if (stillThere) {
					selectLead(selected);
				} else {
					selectLead(null);
				}
			}
		}

		function loadAudience() {
			$error.attr('hidden', 'hidden').text('');
			$.ajax({
				url: cfg.ajaxUrl,
				method: 'POST',
				dataType: 'json',
				data: {
					action: 'amy_analytics_leads_list',
					nonce: cfg.nonce,
					status: '',
					has_email: '',
				},
			})
				.done(function (res) {
					if (!res || !res.success) {
						var msg =
							(res && res.data && res.data.message) ||
							i18n.loadError ||
							'Could not load audience.';
						showError(msg);
						return;
					}
					var payload = res.data || {};
					allLeads = Array.isArray(payload.leads) ? payload.leads : [];
					renderTable();
				})
				.fail(function () {
					showError(i18n.loadError || 'Could not load audience.');
				});
		}

		function readDraft() {
			try {
				var raw = window.localStorage.getItem(DRAFT_KEY);
				return raw ? JSON.parse(raw) : null;
			} catch (err) {
				return null;
			}
		}

		function writeDraft(payload) {
			try {
				window.localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
			} catch (err) {
				/* ignore quota / private mode */
			}
		}

		function clearDraftStorage() {
			try {
				window.localStorage.removeItem(DRAFT_KEY);
			} catch (err) {
				/* ignore */
			}
		}

		function restoreDraft() {
			var draft = readDraft();
			if (!draft) {
				return;
			}
			if (draft.subject) {
				$subject.val(draft.subject);
			}
			if (draft.body) {
				$body.val(draft.body);
			}
			if (draft.to) {
				$to.val(draft.to);
				selected = {
					session_id: draft.session_id || '',
					lead_email: draft.to,
				};
			}
			if (draft.approved) {
				showStatus(i18n.approvedNotice || 'Draft approved locally. Nothing was sent.');
			}
		}

		$statusFilters.on('click', function () {
			setStatusFilter($(this).data('amy-email-status') || '');
		});

		$statButtons.on('click', function () {
			setStatusFilter($(this).data('amy-email-stat') || '');
		});

		$('#amy-agent-email-clear').on('click', function () {
			$subject.val('');
			$body.val('');
			selectLead(null);
			clearDraftStorage();
			showStatus(i18n.cleared || 'Draft cleared.');
		});

		$('#amy-agent-email-approve').on('click', function () {
			var to = String($to.val() || '').trim();
			var subject = String($subject.val() || '').trim();
			var body = String($body.val() || '').trim();

			if (!to) {
				showStatus(i18n.selectRecipient || 'Select a recipient from the audience list.');
				return;
			}
			if (!subject) {
				showStatus(i18n.needSubject || 'Add a subject before approving.');
				return;
			}
			if (!body) {
				showStatus(i18n.needBody || 'Add a message body before approving.');
				return;
			}

			var ok = window.confirm(
				i18n.confirmApprove ||
					'Approve this draft for sending? No email will go out until Hostinger Agentic Mail is connected.'
			);
			if (!ok) {
				return;
			}

			writeDraft({
				to: to,
				subject: subject,
				body: body,
				session_id: selected && selected.session_id ? selected.session_id : '',
				approved: true,
				approved_at: Date.now(),
			});
			showStatus(i18n.approvedNotice || 'Draft approved locally. Nothing was sent.');
		});

		restoreDraft();
		loadAudience();
	});
})(jQuery);
