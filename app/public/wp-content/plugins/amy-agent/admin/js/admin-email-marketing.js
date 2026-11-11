/**
 * Amy Agent — Email Marketing admin (multi-select, approve, explicit Send via wp_mail).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentEmailMarketing || {};
		var i18n = cfg.i18n || {};
		var fromEmail = cfg.fromEmail || 'hello@ogcnewfinity.com';
		var $tbody = $('#amy-agent-email-body');
		var $empty = $('#amy-agent-email-empty');
		var $error = $('#amy-agent-email-error');
		var $statusMsg = $('#amy-agent-email-status');
		var $count = $('#amy-agent-email-count');
		var $statusFilters = $('[data-amy-email-status]');
		var $statButtons = $('[data-amy-email-stat]');
		var $to = $('#amy-agent-email-to');
		var $toMeta = $('#amy-agent-email-to-meta');
		var $subject = $('#amy-agent-email-subject');
		var $body = $('#amy-agent-email-message');
		var $approve = $('#amy-agent-email-approve');
		var $send = $('#amy-agent-email-send');
		var $sendHint = $('#amy-agent-email-send-hint');
		var $signals = $('#amy-agent-email-signals');
		var $signalsEmpty = $('#amy-agent-email-signals-empty');
		var $selectAll = $('#amy-agent-email-select-all');
		var $search = $('#amy-agent-email-search');
		var $needsFollowup = $('#amy-agent-email-needs-followup');
		var $selectedBar = $('#amy-agent-email-selected-bar');
		var $selectedCount = $('#amy-agent-email-selected-count');
		var $chartStatus = $('#amy-agent-email-chart-status');
		var $chartSeen = $('#amy-agent-email-chart-seen');
		var $chartSignal = $('#amy-agent-email-chart-signal');
		var currentStatus = '';
		var searchQuery = '';
		var needsFollowupOnly = false;
		var selectedIds = {};
		var allLeads = [];
		var lastFiltered = [];
		var draftApproved = false;
		var approvedSnapshot = null;
		var sending = false;
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

		function selectedLeads() {
			return emailLeads().filter(function (lead) {
				return !!selectedIds[lead.session_id];
			});
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
			syncSelectionUi();
		}

		function showSendError(msg) {
			$error.removeAttr('hidden').text(msg || i18n.sendError || 'Send failed.');
		}

		function setStatusFilter(next) {
			currentStatus = String(next || '');
			$statusFilters.removeClass('is-active').attr('aria-selected', 'false');
			$statusFilters
				.filter('[data-amy-email-status="' + currentStatus + '"]')
				.addClass('is-active')
				.attr('aria-selected', 'true');
			$statButtons.removeClass('is-active');
			$statButtons.filter('[data-amy-email-stat="' + currentStatus + '"]').addClass('is-active');
			if (needsFollowupOnly && currentStatus !== 'hot') {
				needsFollowupOnly = false;
				$needsFollowup.removeClass('is-active').attr('aria-pressed', 'false');
			}
			renderTable();
		}

		function currentDraftPayload() {
			var selected = selectedLeads();
			var emails = selected
				.map(function (lead) {
					return String(lead.lead_email || '').trim();
				})
				.filter(Boolean);
			return {
				recipients: emails,
				session_ids: selected.map(function (lead) {
					return lead.session_id;
				}),
				subject: String($subject.val() || '').trim(),
				body: String($body.val() || '').trim(),
			};
		}

		function snapshotKey(payload) {
			return JSON.stringify({
				recipients: (payload.recipients || []).slice().sort(),
				subject: payload.subject || '',
				body: payload.body || '',
			});
		}

		function markDraftDirtyIfNeeded() {
			if (!draftApproved || !approvedSnapshot) {
				return;
			}
			if (snapshotKey(currentDraftPayload()) !== approvedSnapshot) {
				draftApproved = false;
				approvedSnapshot = null;
				var draft = readDraft() || {};
				draft.approved = false;
				delete draft.approved_at;
				writeDraft(
					Object.assign({}, draft, currentDraftPayload(), {
						to: (currentDraftPayload().recipients || []).join(', '),
						approved: false,
					})
				);
				updateSendButton();
				showStatus(i18n.draftDirty || 'Draft changed after approval — approve again before sending.');
			}
		}

		function updateSendButton() {
			var payload = currentDraftPayload();
			var canSend =
				draftApproved &&
				!sending &&
				payload.recipients.length > 0 &&
				!!payload.subject &&
				!!payload.body &&
				approvedSnapshot &&
				snapshotKey(payload) === approvedSnapshot;
			$send.prop('disabled', !canSend);
			if (canSend) {
				$sendHint.text(
					(i18n.confirmSend || 'Ready to send %1$d recipient(s) From %2$s.')
						.replace('%1$d', String(payload.recipients.length))
						.replace('%2$s', fromEmail)
				);
			} else if (draftApproved) {
				$sendHint.text(i18n.draftDirty || 'Draft changed after approval — approve again before sending.');
			} else {
				$sendHint.text(i18n.needApprove || 'Send stays disabled until you approve the current draft.');
			}
		}

		function syncSelectionUi() {
			var selected = selectedLeads();
			var emails = selected
				.map(function (lead) {
					return String(lead.lead_email || '').trim();
				})
				.filter(Boolean);
			var count = emails.length;
			var countTpl = i18n.selectedCount || '%d selected';

			$to.val(emails.join('\n'));
			if (count) {
				$toMeta.text(
					(i18n.toMeta || '%d recipient(s) selected — approve, then click Send. From %s.')
						.replace('%d', String(count))
						.replace('%s', fromEmail)
				);
				$selectedBar.removeAttr('hidden');
				$selectedCount.text(countTpl.replace('%d', String(count)));
			} else {
				$toMeta.text('');
				$selectedBar.attr('hidden', 'hidden');
				$selectedCount.text(i18n.selectedNone || 'No emails selected');
			}
			markDraftDirtyIfNeeded();
			updateSendButton();

			var visibleIds = lastFiltered.map(function (lead) {
				return lead.session_id;
			});
			var checkedVisible = 0;
			visibleIds.forEach(function (id) {
				if (selectedIds[id]) {
					checkedVisible += 1;
				}
			});
			var allVisibleSelected = visibleIds.length > 0 && checkedVisible === visibleIds.length;
			$selectAll.prop('checked', allVisibleSelected);
			$selectAll.prop('indeterminate', checkedVisible > 0 && !allVisibleSelected);

			$tbody.find('tr').each(function () {
				var id = $(this).attr('data-session-id');
				var on = !!selectedIds[id];
				$(this).toggleClass('is-selected', on);
				$(this).find('input[type="checkbox"]').prop('checked', on);
			});
		}

		function toggleLead(lead, force) {
			if (!lead || !lead.session_id) {
				return;
			}
			var id = lead.session_id;
			var next = typeof force === 'boolean' ? force : !selectedIds[id];
			if (next) {
				selectedIds[id] = true;
			} else {
				delete selectedIds[id];
			}
			syncSelectionUi();
		}

		function clearSelection(showNotice) {
			selectedIds = {};
			syncSelectionUi();
			if (showNotice) {
				showStatus(i18n.selectionCleared || 'Selection cleared.');
			}
		}

		function renderStatusChart(hot, warm, cold) {
			var total = hot + warm + cold;
			if (!total) {
				$chartStatus.html(
					'<p class="amy-agent-email__chart-empty">' +
						escapeHtml(i18n.chartEmpty || 'No data yet') +
						'</p>'
				);
				return;
			}

			var r = 36;
			var c = 2 * Math.PI * r;
			var segs = [
				{ key: 'hot', value: hot, color: '#E35D6A' },
				{ key: 'warm', value: warm, color: '#F7941D' },
				{ key: 'cold', value: cold, color: '#8A8A8A' },
			];
			var offset = 0;
			var circles = segs
				.map(function (seg) {
					var len = (seg.value / total) * c;
					var circle =
						'<circle class="amy-agent-email__donut-seg amy-agent-email__donut-seg--' +
						seg.key +
						'" cx="48" cy="48" r="' +
						r +
						'" fill="none" stroke="' +
						seg.color +
						'" stroke-width="12" stroke-dasharray="' +
						len +
						' ' +
						(c - len) +
						'" stroke-dashoffset="' +
						-offset +
						'" transform="rotate(-90 48 48)"></circle>';
					offset += len;
					return circle;
				})
				.join('');

			$chartStatus.html(
				'<div class="amy-agent-email__donut-wrap">' +
					'<svg class="amy-agent-email__donut" viewBox="0 0 96 96" width="96" height="96" aria-hidden="true">' +
					'<circle cx="48" cy="48" r="' +
					r +
					'" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="12"></circle>' +
					circles +
					'</svg>' +
					'<ul class="amy-agent-email__legend">' +
					'<li><span class="amy-agent-email__swatch amy-agent-email__swatch--hot"></span>' +
					escapeHtml(statusLabel('hot')) +
					' · ' +
					hot +
					'</li>' +
					'<li><span class="amy-agent-email__swatch amy-agent-email__swatch--warm"></span>' +
					escapeHtml(statusLabel('warm')) +
					' · ' +
					warm +
					'</li>' +
					'<li><span class="amy-agent-email__swatch amy-agent-email__swatch--cold"></span>' +
					escapeHtml(statusLabel('cold')) +
					' · ' +
					cold +
					'</li>' +
					'</ul></div>'
			);
		}

		function renderBarChart($el, rows) {
			if (!rows.length) {
				$el.html(
					'<p class="amy-agent-email__chart-empty">' +
						escapeHtml(i18n.chartEmpty || 'No data yet') +
						'</p>'
				);
				return;
			}
			var max = 0;
			rows.forEach(function (row) {
				if (row.value > max) {
					max = row.value;
				}
			});
			if (!max) {
				max = 1;
			}
			var html = rows
				.map(function (row) {
					var pct = Math.round((row.value / max) * 100);
					return (
						'<div class="amy-agent-email__bar-row">' +
						'<span class="amy-agent-email__bar-label">' +
						escapeHtml(row.label) +
						'</span>' +
						'<span class="amy-agent-email__bar-track"><span class="amy-agent-email__bar-fill' +
						(row.mod ? ' ' + row.mod : '') +
						'" style="width:' +
						pct +
						'%"></span></span>' +
						'<span class="amy-agent-email__bar-value">' +
						row.value +
						'</span></div>'
					);
				})
				.join('');
			$el.html(html);
		}

		function lastSeenBucket(ts) {
			var seconds = parseFloat(ts);
			if (!seconds) {
				return 'older';
			}
			var diff = Math.max(0, Date.now() / 1000 - seconds);
			if (diff < 86400) {
				return '24h';
			}
			if (diff < 7 * 86400) {
				return '7d';
			}
			if (diff < 30 * 86400) {
				return '30d';
			}
			return 'older';
		}

		function renderCharts(leadsWithEmail) {
			var hot = 0;
			var warm = 0;
			var cold = 0;
			var buckets = { '24h': 0, '7d': 0, '30d': 0, older: 0 };
			var signals = {};

			leadsWithEmail.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				if (status === 'hot') {
					hot += 1;
				} else if (status === 'warm') {
					warm += 1;
				} else {
					cold += 1;
				}
				buckets[lastSeenBucket(lead.last_seen_at)] += 1;
				var signal = String(lead.signal || i18n.unknownSignal || 'No signal').trim() || 'No signal';
				signals[signal] = (signals[signal] || 0) + 1;
			});

			renderStatusChart(hot, warm, cold);

			renderBarChart($chartSeen, [
				{ label: i18n.seen24h || 'Last 24h', value: buckets['24h'], mod: 'amy-agent-email__bar-fill--hot' },
				{ label: i18n.seen7d || '1–7 days', value: buckets['7d'], mod: 'amy-agent-email__bar-fill--warm' },
				{ label: i18n.seen30d || '8–30 days', value: buckets['30d'] },
				{ label: i18n.seenOlder || 'Older', value: buckets.older, mod: 'amy-agent-email__bar-fill--cold' },
			]);

			var signalRows = Object.keys(signals)
				.map(function (key) {
					return { label: key, value: signals[key] };
				})
				.sort(function (a, b) {
					return b.value - a.value;
				})
				.slice(0, 5);
			renderBarChart($chartSignal, signalRows);
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
			} else {
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

			renderCharts(leadsWithEmail);
		}

		function getFilteredLeads() {
			var withEmail = emailLeads();
			var q = String(searchQuery || '')
				.trim()
				.toLowerCase();

			return withEmail.filter(function (lead) {
				var status = lead.lead_status || 'cold';
				if (needsFollowupOnly && status !== 'hot') {
					return false;
				}
				if (currentStatus && status !== currentStatus) {
					return false;
				}
				if (!q) {
					return true;
				}
				var email = String(lead.lead_email || '').toLowerCase();
				var visitor = String(lead.visitor_label || '').toLowerCase();
				var signal = String(lead.signal || '').toLowerCase();
				return email.indexOf(q) !== -1 || visitor.indexOf(q) !== -1 || signal.indexOf(q) !== -1;
			});
		}

		function renderTable() {
			$error.attr('hidden', 'hidden').text('');
			$tbody.empty();

			var withEmail = emailLeads();
			renderAnalysis(withEmail);

			var filtered = getFilteredLeads();
			lastFiltered = filtered;

			var countTpl = i18n.audienceCount || '%d shown';
			$count.text(countTpl.replace('%d', String(filtered.length)));

			if (!filtered.length) {
				$empty
					.removeAttr('hidden')
					.text(
						withEmail.length
							? i18n.emptyFiltered || 'No email leads match this filter or search.'
							: i18n.empty ||
									'No visitor emails yet. Captures appear after Submit Idea or contact form completion.'
					);
				syncSelectionUi();
				return;
			}

			$empty.attr('hidden', 'hidden');
			filtered.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				var visitor = lead.visitor_label || 'Visitor ' + (lead.session_id_short || '');
				var email = lead.lead_email || '';
				var checked = selectedIds[lead.session_id] ? ' checked' : '';
				var tr = document.createElement('tr');
				tr.setAttribute('data-session-id', lead.session_id || '');
				if (selectedIds[lead.session_id]) {
					tr.className = 'is-selected';
				}
				tr.innerHTML =
					'<td class="amy-agent-email__col-check">' +
					'<input type="checkbox" value="' +
					escapeHtml(lead.session_id || '') +
					'" aria-label="' +
					escapeHtml(email) +
					'"' +
					checked +
					' />' +
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
					if ($(evt.target).is('input[type="checkbox"]')) {
						toggleLead(lead, evt.target.checked);
						return;
					}
					toggleLead(lead);
				});
			});

			syncSelectionUi();
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
					var valid = {};
					emailLeads().forEach(function (lead) {
						if (selectedIds[lead.session_id]) {
							valid[lead.session_id] = true;
						}
					});
					selectedIds = valid;
					renderTable();
				})
				.fail(function (xhr) {
					var msg =
						(xhr &&
							xhr.responseJSON &&
							xhr.responseJSON.data &&
							xhr.responseJSON.data.message) ||
						i18n.loadError ||
						'Could not load audience.';
					showError(msg);
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
			var recipients = [];
			if (Array.isArray(draft.recipients) && draft.recipients.length) {
				recipients = draft.recipients;
			} else if (draft.to) {
				recipients = String(draft.to)
					.split(/[\n,;]+/)
					.map(function (part) {
						return part.trim();
					})
					.filter(Boolean);
			}
			if (recipients.length) {
				$to.val(recipients.join('\n'));
				$toMeta.text(
					(i18n.toMeta || '%d recipient(s) selected — approve, then click Send. From %s.')
						.replace('%d', String(recipients.length))
						.replace('%s', fromEmail)
				);
			}
			if (Array.isArray(draft.session_ids)) {
				draft.session_ids.forEach(function (id) {
					if (id) {
						selectedIds[id] = true;
					}
				});
			} else if (draft.session_id) {
				selectedIds[draft.session_id] = true;
			}
			if (draft.approved) {
				draftApproved = true;
				approvedSnapshot = snapshotKey({
					recipients: recipients,
					subject: String(draft.subject || '').trim(),
					body: String(draft.body || '').trim(),
				});
				showStatus(i18n.approvedNotice || 'Draft approved. Click Send to deliver. Nothing was sent yet.');
			}
			updateSendButton();
		}

		function exportSelectedCsv() {
			var selected = selectedLeads();
			if (!selected.length) {
				showStatus(i18n.exportEmpty || 'Select at least one email to export.');
				return;
			}
			var lines = ['email,visitor,status,signal,last_seen_at,session_id'];
			selected.forEach(function (lead) {
				var cells = [
					lead.lead_email || '',
					lead.visitor_label || '',
					lead.lead_status || 'cold',
					lead.signal || '',
					lead.last_seen_at || '',
					lead.session_id || '',
				].map(function (cell) {
					var value = String(cell == null ? '' : cell);
					if (/[",\n]/.test(value)) {
						return '"' + value.replace(/"/g, '""') + '"';
					}
					return value;
				});
				lines.push(cells.join(','));
			});
			var blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
			var url = URL.createObjectURL(blob);
			var a = document.createElement('a');
			a.href = url;
			a.download = 'amy-email-audience-selected.csv';
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			showStatus(i18n.exportDone || 'Selected emails exported as CSV.');
		}

		$statusFilters.on('click', function () {
			setStatusFilter($(this).data('amy-email-status') || '');
		});

		$statButtons.on('click', function () {
			setStatusFilter($(this).data('amy-email-stat') || '');
		});

		$selectAll.on('change', function () {
			var on = !!this.checked;
			lastFiltered.forEach(function (lead) {
				toggleLead(lead, on);
			});
		});

		$search.on('input', function () {
			searchQuery = String($(this).val() || '');
			renderTable();
		});

		$needsFollowup.on('click', function () {
			needsFollowupOnly = !needsFollowupOnly;
			$needsFollowup.toggleClass('is-active', needsFollowupOnly).attr('aria-pressed', needsFollowupOnly ? 'true' : 'false');
			if (needsFollowupOnly) {
				currentStatus = 'hot';
				$statusFilters.removeClass('is-active').attr('aria-selected', 'false');
				$statusFilters.filter('[data-amy-email-status="hot"]').addClass('is-active').attr('aria-selected', 'true');
				$statButtons.removeClass('is-active');
				$statButtons.filter('[data-amy-email-stat="hot"]').addClass('is-active');
			}
			renderTable();
		});

		$('#amy-agent-email-export').on('click', exportSelectedCsv);
		$('#amy-agent-email-clear-selection').on('click', function () {
			clearSelection(true);
		});

		$('#amy-agent-email-clear').on('click', function () {
			$subject.val('');
			$body.val('');
			clearSelection(false);
			clearDraftStorage();
			draftApproved = false;
			approvedSnapshot = null;
			updateSendButton();
			showStatus(i18n.cleared || 'Draft cleared.');
		});

		$subject.on('input', markDraftDirtyIfNeeded);
		$body.on('input', markDraftDirtyIfNeeded);

		$approve.on('click', function () {
			var payload = currentDraftPayload();
			var emails = payload.recipients;

			if (!emails.length) {
				showStatus(i18n.selectRecipient || 'Select at least one recipient from the audience list.');
				return;
			}
			if (!payload.subject) {
				showStatus(i18n.needSubject || 'Add a subject before approving.');
				return;
			}
			if (!payload.body) {
				showStatus(i18n.needBody || 'Add a message body before approving.');
				return;
			}

			var ok = window.confirm(
				i18n.confirmApprove ||
					'Approve this draft for the selected audience? Nothing is sent yet — you must click Send afterward.'
			);
			if (!ok) {
				return;
			}

			draftApproved = true;
			approvedSnapshot = snapshotKey(payload);
			writeDraft({
				to: emails.join(', '),
				recipients: emails,
				session_ids: payload.session_ids,
				subject: payload.subject,
				body: payload.body,
				approved: true,
				approved_at: Date.now(),
				from_email: fromEmail,
			});
			updateSendButton();
			showStatus(
				i18n.approvedNotice ||
					'Draft approved. Click Send to deliver via wp_mail / FluentSMTP. Nothing was sent yet.'
			);
		});

		$send.on('click', function () {
			if (sending) {
				return;
			}
			var payload = currentDraftPayload();
			if (
				!draftApproved ||
				!approvedSnapshot ||
				snapshotKey(payload) !== approvedSnapshot ||
				!payload.recipients.length
			) {
				showStatus(i18n.needApprove || 'Approve the draft first. Send stays disabled until you approve.');
				updateSendButton();
				return;
			}

			var confirmMsg = (i18n.confirmSend || 'Send this approved draft to %1$d recipient(s) From %2$s via FluentSMTP (wp_mail)? This cannot be undone.')
				.replace('%1$d', String(payload.recipients.length))
				.replace('%2$s', fromEmail);
			if (!window.confirm(confirmMsg)) {
				return;
			}

			sending = true;
			updateSendButton();
			showStatus(i18n.sending || 'Sending…');
			$error.attr('hidden', 'hidden').text('');

			$.ajax({
				url: cfg.ajaxUrl,
				method: 'POST',
				dataType: 'json',
				data: {
					action: 'amy_email_marketing_send',
					nonce: cfg.sendNonce,
					approved: '1',
					confirmed: '1',
					subject: payload.subject,
					body: payload.body,
					recipients: payload.recipients,
				},
			})
				.done(function (res) {
					if (!res || !res.success) {
						var failMsg =
							(res && res.data && res.data.message) ||
							i18n.sendError ||
							('Send failed. Check FluentSMTP logs and that ' + fromEmail + ' is authorized on the connection.');
						showSendError(failMsg);
						showStatus('');
						return;
					}
					var data = res.data || {};
					$error.attr('hidden', 'hidden').text('');
					showStatus(data.message || 'Sent.');
					draftApproved = false;
					approvedSnapshot = null;
					clearDraftStorage();
					updateSendButton();
				})
				.fail(function (xhr) {
					var msg =
						(xhr &&
							xhr.responseJSON &&
							xhr.responseJSON.data &&
							xhr.responseJSON.data.message) ||
						i18n.sendError ||
						('Send failed. Check FluentSMTP logs and that ' + fromEmail + ' is authorized on the connection.');
					showSendError(msg);
					showStatus('');
				})
				.always(function () {
					sending = false;
					updateSendButton();
				});
		});

		restoreDraft();
		loadAudience();
		updateSendButton();
	});
})(jQuery);
