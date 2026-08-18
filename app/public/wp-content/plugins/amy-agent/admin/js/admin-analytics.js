/**
 * Amy Agent — Analytics admin page (real lead list via admin-ajax → Python).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentAnalytics || {};
		var i18n = cfg.i18n || {};
		var $tbody = $('#amy-agent-analytics-body');
		var $empty = $('#amy-agent-analytics-empty');
		var $error = $('#amy-agent-analytics-error');
		var $statusFilters = $('[data-amy-analytics-status]');
		var currentStatus = '';

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

		function formatLocation(lead) {
			var city = (lead.ip_city || '').trim();
			var country = (lead.ip_country || '').trim();
			if (city && country) {
				return city + ', ' + country;
			}
			return city || country || '—';
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

		function render(leads) {
			$error.attr('hidden', 'hidden').text('');
			$tbody.empty();

			if (!leads.length) {
				$empty.removeAttr('hidden');
				return;
			}

			$empty.attr('hidden', 'hidden');
			leads.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				var visitor = lead.visitor_label || ('Visitor ' + (lead.session_id_short || ''));
				if (lead.lead_email) {
					visitor += ' · ' + lead.lead_email;
				}
				var tr = document.createElement('tr');
				tr.innerHTML =
					'<td class="amy-agent-analytics__visitor">' +
					escapeHtml(visitor) +
					'</td>' +
					'<td>' +
					escapeHtml(formatLocation(lead)) +
					'</td>' +
					'<td>' +
					escapeHtml(formatLastSeen(lead.last_seen_at)) +
					'</td>' +
					'<td>' +
					escapeHtml(lead.signal || '—') +
					'</td>' +
					'<td>' +
					'<span class="amy-agent-analytics__badge amy-agent-analytics__badge--' +
					escapeHtml(status) +
					'">' +
					escapeHtml(statusLabel(status)) +
					'</span>' +
					'</td>';
				$tbody.append(tr);
			});
		}

		function loadLeads() {
			$error.attr('hidden', 'hidden').text('');
			$.ajax({
				url: cfg.ajaxUrl,
				method: 'POST',
				dataType: 'json',
				data: {
					action: 'amy_analytics_leads_list',
					nonce: cfg.nonce,
					status: currentStatus,
				},
			})
				.done(function (res) {
					if (!res || !res.success) {
						var msg =
							(res && res.data && res.data.message) ||
							i18n.loadError ||
							'Could not load leads.';
						$error.removeAttr('hidden').text(msg);
						$tbody.empty();
						$empty.attr('hidden', 'hidden');
						return;
					}
					var payload = res.data || {};
					var leads = Array.isArray(payload.leads) ? payload.leads : [];
					render(leads);
				})
				.fail(function () {
					$error.removeAttr('hidden').text(i18n.loadError || 'Could not load leads.');
					$tbody.empty();
					$empty.attr('hidden', 'hidden');
				});
		}

		$statusFilters.on('click', function () {
			var next = String($(this).data('amy-analytics-status') || '');
			currentStatus = next;
			$statusFilters.removeClass('is-active').attr('aria-selected', 'false');
			$(this).addClass('is-active').attr('aria-selected', 'true');
			loadLeads();
		});

		loadLeads();
	});
})(jQuery);
