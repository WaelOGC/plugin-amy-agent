/**
 * Amy Agent — Analytics admin page (filters, five views, client-side data).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentAnalytics || {};
		var i18n = cfg.i18n || {};
		var prefs = cfg.prefs || { view: 'table', sort: 'newest' };

		var allLeads = [];
		var loading = false;
		var lastUpdated = null;
		var savePrefsTimer = null;

		var state = {
			search: '',
			status: '',
			country: '',
			seen: '',
			contact: '',
			sort: prefs.sort || 'newest',
			view: prefs.view || 'table',
		};

		var $error = $('#amy-agent-analytics-error');
		var $list = $('#amy-agent-analytics-list');
		var $listInner = $('#amy-agent-analytics-list-inner');
		var $loading = $('#amy-agent-analytics-loading');
		var $empty = $('#amy-agent-analytics-empty');
		var $emptyFilters = $('#amy-agent-analytics-empty-filters');
		var $contactsInfo = $('#amy-agent-analytics-contacts-info');
		var $resultCount = $('#amy-agent-analytics-result-count');
		var $updated = $('#amy-agent-analytics-updated');
		var $reset = $('#amy-agent-analytics-reset');
		var $search = $('#amy-agent-analytics-search');
		var $searchClear = $('#amy-agent-analytics-search-clear');
		var $country = $('#amy-agent-analytics-country');
		var $seen = $('#amy-agent-analytics-seen');
		var $contact = $('#amy-agent-analytics-contact');
		var $sort = $('#amy-agent-analytics-sort');
		var $refresh = $('#amy-agent-analytics-refresh');
		var $toast = $('#amy-agent-analytics-toast');
		var $statusChips = $('.amy-agent-analytics__chip');
		var $viewBtns = $('.amy-agent-analytics__view-btn');
		var searchTimer = null;

		var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		var STATUS_ORDER = { hot: 0, warm: 1, cold: 2 };

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
		}

		function normalizePhone(str) {
			return String(str || '').replace(/[\s+\-()]/g, '');
		}

		function phoneDigits(str) {
			return String(str || '').replace(/\D/g, '');
		}

		function telHref(phone) {
			var digits = phoneDigits(phone);
			if (!digits) {
				return '';
			}
			return '+' + digits;
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

		function visitorLabel(lead) {
			return (lead.visitor_label || '').trim() ||
				('Visitor ' + (lead.session_id_short || ''));
		}

		function hasEmail(lead) {
			return !!(lead.lead_email || '').trim();
		}

		function hasPhone(lead) {
			return !!(lead.lead_whatsapp || '').trim();
		}

		function matchesSeen(lead) {
			if (!state.seen) {
				return true;
			}
			var seconds = parseFloat(lead.last_seen_at);
			if (!seconds) {
				return false;
			}
			var diff = Date.now() / 1000 - seconds;
			if (state.seen === 'hour') {
				return diff >= 0 && diff < 3600;
			}
			if (state.seen === 'today') {
				var d = new Date(seconds * 1000);
				var now = new Date();
				return d.getFullYear() === now.getFullYear() &&
					d.getMonth() === now.getMonth() &&
					d.getDate() === now.getDate();
			}
			if (state.seen === '7') {
				return diff >= 0 && diff < 7 * 86400;
			}
			if (state.seen === '30') {
				return diff >= 0 && diff < 30 * 86400;
			}
			return true;
		}

		function matchesContact(lead) {
			if (!state.contact) {
				return true;
			}
			var em = hasEmail(lead);
			var ph = hasPhone(lead);
			if (state.contact === 'email') {
				return em;
			}
			if (state.contact === 'phone') {
				return ph;
			}
			if (state.contact === 'both') {
				return em && ph;
			}
			if (state.contact === 'none') {
				return !em && !ph;
			}
			return true;
		}

		function matchesSearch(lead) {
			var q = (state.search || '').trim().toLowerCase();
			if (!q) {
				return true;
			}
			var hay = [
				visitorLabel(lead),
				lead.lead_email || '',
				lead.lead_whatsapp || '',
				lead.ip_city || '',
				lead.ip_country || '',
				lead.signal || '',
				lead.session_id_short || '',
			].join(' ').toLowerCase();
			if (hay.indexOf(q) !== -1) {
				return true;
			}
			var qPhone = normalizePhone(q);
			if (qPhone && normalizePhone(lead.lead_whatsapp || '').indexOf(qPhone) !== -1) {
				return true;
			}
			return false;
		}

		function matchesCountry(lead) {
			if (!state.country) {
				return true;
			}
			return (lead.ip_country || '').trim() === state.country;
		}

		function matchesStatus(lead, statusFilter) {
			if (!statusFilter) {
				return true;
			}
			return (lead.lead_status || 'cold') === statusFilter;
		}

		function filterLeads(opts) {
			opts = opts || {};
			var statusFilter = '';
			if (!opts.ignoreStatus && state.view !== 'board') {
				statusFilter = opts.status != null ? opts.status : state.status;
			}
			return allLeads.filter(function (lead) {
				if (!matchesSearch(lead)) {
					return false;
				}
				if (!matchesCountry(lead)) {
					return false;
				}
				if (!matchesSeen(lead)) {
					return false;
				}
				if (!matchesContact(lead)) {
					return false;
				}
				if (!matchesStatus(lead, statusFilter)) {
					return false;
				}
				return true;
			});
		}

		function sortLeads(leads) {
			var list = leads.slice();
			var sortKey = state.sort;
			list.sort(function (a, b) {
				if (sortKey === 'hottest') {
					var sa = STATUS_ORDER[a.lead_status || 'cold'];
					var sb = STATUS_ORDER[b.lead_status || 'cold'];
					if (sa !== sb) {
						return sa - sb;
					}
					return parseFloat(b.last_seen_at || 0) - parseFloat(a.last_seen_at || 0);
				}
				if (sortKey === 'email') {
					var ea = (a.lead_email || '').toLowerCase();
					var eb = (b.lead_email || '').toLowerCase();
					if (!ea && eb) {
						return 1;
					}
					if (ea && !eb) {
						return -1;
					}
					if (ea < eb) {
						return -1;
					}
					if (ea > eb) {
						return 1;
					}
					return parseFloat(b.last_seen_at || 0) - parseFloat(a.last_seen_at || 0);
				}
				if (sortKey === 'oldest') {
					return parseFloat(a.last_seen_at || 0) - parseFloat(b.last_seen_at || 0);
				}
				return parseFloat(b.last_seen_at || 0) - parseFloat(a.last_seen_at || 0);
			});
			return list;
		}

		function contactsViewLeads(leads) {
			return leads.filter(function (lead) {
				return hasEmail(lead) || hasPhone(lead);
			});
		}

		function isFilterActive() {
			return !!(state.search || state.status || state.country || state.seen || state.contact);
		}

		function updateStatusCounts() {
			var base = filterLeads({ ignoreStatus: true });
			var counts = { '': base.length, hot: 0, warm: 0, cold: 0 };
			base.forEach(function (lead) {
				var st = lead.lead_status || 'cold';
				if (counts[st] != null) {
					counts[st]++;
				}
			});
			$('[data-amy-count-all]').text(counts['']);
			$('[data-amy-count-hot]').text(counts.hot);
			$('[data-amy-count-warm]').text(counts.warm);
			$('[data-amy-count-cold]').text(counts.cold);
		}

		function populateCountries() {
			var countries = {};
			allLeads.forEach(function (lead) {
				var c = (lead.ip_country || '').trim();
				if (c) {
					countries[c] = true;
				}
			});
			var sorted = Object.keys(countries).sort(function (a, b) {
				return a.localeCompare(b);
			});
			var current = $country.val();
			$country.find('option:not(:first)').remove();
			sorted.forEach(function (c) {
				$country.append(
					$('<option></option>').attr('value', c).text(c)
				);
			});
			if (current && countries[current]) {
				$country.val(current);
			}
		}

		function copyToClipboard(text) {
			if (navigator.clipboard && navigator.clipboard.writeText) {
				return navigator.clipboard.writeText(text).catch(fallbackCopy);
			}
			return fallbackCopy();

			function fallbackCopy() {
				var ta = document.createElement('textarea');
				ta.value = text;
				ta.setAttribute('readonly', '');
				ta.style.position = 'absolute';
				ta.style.left = '-9999px';
				document.body.appendChild(ta);
				ta.select();
				try {
					document.execCommand('copy');
				} catch (e) {
					// ignore
				}
				document.body.removeChild(ta);
				return Promise.resolve();
			}
		}

		function showToast(msg) {
			$toast.text(msg).removeAttr('hidden');
			clearTimeout(showToast._t);
			showToast._t = setTimeout(function () {
				$toast.attr('hidden', 'hidden').text('');
			}, 1500);
		}

		function badgeHtml(status) {
			return (
				'<span class="amy-agent-analytics__badge amy-agent-analytics__badge--' +
				escapeHtml(status) +
				'">' +
				escapeHtml(statusLabel(status)) +
				'</span>'
			);
		}

		function copyBtn(attr, label, value) {
			return (
				'<button type="button" class="amy-agent-analytics__copy" data-amy-copy="' +
				escapeHtml(value) +
				'" aria-label="' +
				escapeHtml(label) +
				'">' +
				'<span class="dashicons dashicons-clipboard" aria-hidden="true"></span>' +
				'</button>'
			);
		}

		function emailActions(email) {
			if (!email) {
				return '<span class="amy-agent-analytics__muted">—</span>';
			}
			var html = '<span class="amy-agent-analytics__contact-row">';
			if (EMAIL_RE.test(email)) {
				html +=
					'<a class="amy-agent-analytics__ellipsis" href="mailto:' +
					escapeHtml(email) +
					'" title="' +
					escapeHtml(email) +
					'">' +
					escapeHtml(email) +
					'</a>';
			} else {
				html +=
					'<span class="amy-agent-analytics__ellipsis" title="' +
					escapeHtml(email) +
					'">' +
					escapeHtml(email) +
					'</span>';
			}
			html += copyBtn('email', i18n.copyEmail || 'Copy email', email);
			html += '</span>';
			return html;
		}

		function phoneActions(phone) {
			if (!phone) {
				return '<span class="amy-agent-analytics__muted">—</span>';
			}
			var tel = telHref(phone);
			var digits = phoneDigits(phone);
			var html = '<span class="amy-agent-analytics__contact-row">';
			if (tel) {
				html +=
					'<a class="amy-agent-analytics__ellipsis" href="tel:' +
					escapeHtml(tel) +
					'">' +
					escapeHtml(phone) +
					'</a>';
			} else {
				html += '<span>' + escapeHtml(phone) + '</span>';
			}
			if (digits.length >= 8) {
				html +=
					'<a class="amy-agent-analytics__wa" href="https://wa.me/' +
					escapeHtml(digits) +
					'" target="_blank" rel="noopener noreferrer" aria-label="' +
					escapeHtml(i18n.whatsapp || 'Open WhatsApp') +
					'">' +
					'<span class="dashicons dashicons-format-chat" aria-hidden="true"></span>' +
					'</a>';
			}
			html += copyBtn('phone', i18n.copyPhone || 'Copy phone', phone);
			html += '</span>';
			return html;
		}

		function renderTable(leads) {
			var loc = i18n;
			var html =
				'<div class="amy-agent-analytics__table-wrap">' +
				'<table class="amy-agent-analytics__table">' +
				'<colgroup>' +
				'<col style="width:13%">' +
				'<col style="width:21%">' +
				'<col style="width:13%">' +
				'<col style="width:15%">' +
				'<col style="width:8%">' +
				'<col style="width:22%">' +
				'<col style="width:8%">' +
				'</colgroup>' +
				'<thead><tr>' +
				'<th>' + escapeHtml(loc.colVisitor || 'Visitor') + '</th>' +
				'<th>' + escapeHtml(loc.colEmail || 'Email') + '</th>' +
				'<th>' + escapeHtml(loc.colPhone || 'Phone') + '</th>' +
				'<th>' + escapeHtml(loc.colLocation || 'Location') + '</th>' +
				'<th>' + escapeHtml(loc.colLastSeen || 'Last seen') + '</th>' +
				'<th>' + escapeHtml(loc.colSignal || 'Signal') + '</th>' +
				'<th class="amy-agent-analytics__th-status">' + escapeHtml(loc.colStatus || 'Status') + '</th>' +
				'</tr></thead><tbody>';
			leads.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				var visitor = visitorLabel(lead);
				var location = formatLocation(lead);
				html +=
					'<tr>' +
					'<td class="amy-agent-analytics__visitor amy-agent-analytics__ellipsis" title="' +
					escapeHtml(visitor) +
					'">' +
					escapeHtml(visitor) +
					'</td>' +
					'<td class="amy-agent-analytics__contact">' +
					emailActions(lead.lead_email) +
					'</td>' +
					'<td class="amy-agent-analytics__contact">' +
					phoneActions(lead.lead_whatsapp) +
					'</td>' +
					'<td class="amy-agent-analytics__ellipsis" title="' +
					escapeHtml(location) +
					'">' +
					escapeHtml(location) +
					'</td>' +
					'<td>' +
					escapeHtml(formatLastSeen(lead.last_seen_at)) +
					'</td>' +
					'<td class="amy-agent-analytics__signal">' +
					escapeHtml(lead.signal || '—') +
					'</td>' +
					'<td class="amy-agent-analytics__td-status">' +
					badgeHtml(status) +
					'</td>' +
					'</tr>';
			});
			html += '</tbody></table></div>';
			return html;
		}

		function renderCompact(leads) {
			var html = '<ul class="amy-agent-analytics__compact">';
			leads.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				var visitor = visitorLabel(lead);
				var email = (lead.lead_email || '').trim();
				var phone = (lead.lead_whatsapp || '').trim();
				html +=
					'<li class="amy-agent-analytics__compact-row">' +
					'<span class="amy-agent-analytics__dot amy-agent-analytics__dot--' +
					escapeHtml(status) +
					'" aria-hidden="true"></span>' +
					'<span class="amy-agent-analytics__ellipsis" title="' +
					escapeHtml(visitor) +
					'">' +
					escapeHtml(visitor) +
					'</span>' +
					'<span class="amy-agent-analytics__compact-sep" aria-hidden="true">•</span>' +
					'<span class="amy-agent-analytics__ellipsis" title="' +
					escapeHtml(email || '—') +
					'">' +
					escapeHtml(email || '—') +
					'</span>' +
					'<span class="amy-agent-analytics__compact-sep" aria-hidden="true">•</span>' +
					'<span class="amy-agent-analytics__ellipsis">' +
					escapeHtml(phone || '—') +
					'</span>' +
					'<span class="amy-agent-analytics__compact-sep" aria-hidden="true">•</span>' +
					'<span class="amy-agent-analytics__compact-signal amy-agent-analytics__ellipsis">' +
					escapeHtml(lead.signal || '—') +
					'</span>' +
					'<span class="amy-agent-analytics__compact-sep" aria-hidden="true">•</span>' +
					'<span class="amy-agent-analytics__compact-seen">' +
					escapeHtml(formatLastSeen(lead.last_seen_at)) +
					'</span>' +
					'</li>';
			});
			html += '</ul>';
			return html;
		}

		function cardInner(lead, tight) {
			var status = lead.lead_status || 'cold';
			var visitor = visitorLabel(lead);
			var location = formatLocation(lead);
			var cardClass = tight
				? 'amy-agent-analytics__card amy-agent-analytics__card--tight'
				: 'amy-agent-analytics__card';
			return (
				'<article class="' + cardClass + '">' +
				'<div class="amy-agent-analytics__card-badge">' +
				badgeHtml(status) +
				'</div>' +
				'<h3 class="amy-agent-analytics__card-title">' +
				escapeHtml(visitor) +
				'</h3>' +
				'<div class="amy-agent-analytics__card-row">' +
				emailActions(lead.lead_email) +
				'</div>' +
				'<div class="amy-agent-analytics__card-row">' +
				phoneActions(lead.lead_whatsapp) +
				'</div>' +
				'<p class="amy-agent-analytics__card-meta">' +
				escapeHtml(location) +
				' · ' +
				escapeHtml(formatLastSeen(lead.last_seen_at)) +
				'</p>' +
				'<p class="amy-agent-analytics__card-signal">' +
				escapeHtml(lead.signal || '—') +
				'</p>' +
				'</article>'
			);
		}

		function renderCards(leads) {
			var html = '<div class="amy-agent-analytics__cards">';
			leads.forEach(function (lead) {
				html += cardInner(lead);
			});
			html += '</div>';
			return html;
		}

		function renderBoard(leads) {
			var cols = { hot: [], warm: [], cold: [] };
			leads.forEach(function (lead) {
				var st = lead.lead_status || 'cold';
				if (cols[st]) {
					cols[st].push(lead);
				} else {
					cols.cold.push(lead);
				}
			});
			var html = '<div class="amy-agent-analytics__board">';
			['hot', 'warm', 'cold'].forEach(function (st) {
				html +=
					'<section class="amy-agent-analytics__board-col">' +
					'<header class="amy-agent-analytics__board-head">' +
					'<span>' +
					escapeHtml(statusLabel(st)) +
					'</span>' +
					'<span class="amy-agent-analytics__board-count">' +
					cols[st].length +
					'</span>' +
					'</header>' +
					'<div class="amy-agent-analytics__board-list">';
				cols[st].forEach(function (lead) {
					html += cardInner(lead, true);
				});
				html += '</div></section>';
			});
			html += '</div>';
			return html;
		}

		function renderContacts(leads) {
			var html = '<ul class="amy-agent-analytics__contacts">';
			leads.forEach(function (lead) {
				var status = lead.lead_status || 'cold';
				var location = formatLocation(lead);
				html +=
					'<li class="amy-agent-analytics__contacts-row">' +
					'<div class="amy-agent-analytics__contacts-main">' +
					'<div class="amy-agent-analytics__contacts-email">' +
					emailActions(lead.lead_email) +
					'</div>' +
					'<div class="amy-agent-analytics__contacts-phone">' +
					phoneActions(lead.lead_whatsapp) +
					'</div>' +
					'<p class="amy-agent-analytics__contacts-meta">' +
					escapeHtml(lead.signal || '—') +
					' · ' +
					escapeHtml(location) +
					' · ' +
					escapeHtml(formatLastSeen(lead.last_seen_at)) +
					'</p>' +
					'</div>' +
					'<div class="amy-agent-analytics__contacts-badge">' +
					badgeHtml(status) +
					'</div>' +
					'</li>';
			});
			html += '</ul>';
			return html;
		}

		function setBoardChipState() {
			var disabled = state.view === 'board';
			$statusChips.prop('disabled', disabled);
			$statusChips.toggleClass('is-disabled', disabled);
		}

		function updateViewUi() {
			$viewBtns.each(function () {
				var v = $(this).data('amy-view');
				var active = v === state.view;
				$(this).toggleClass('is-active', active);
				$(this).attr('aria-checked', active ? 'true' : 'false');
			});
			$list.attr('data-view', state.view);
			setBoardChipState();
		}

		function formatShowing(shown, total) {
			var tpl = i18n.showing || 'Showing %1$s of %2$s visitors';
			return tpl.replace('%1$s', String(shown)).replace('%2$s', String(total));
		}

		function updateUpdatedLabel() {
			if (!lastUpdated) {
				$updated.text('');
				return;
			}
			var d = lastUpdated;
			var hh = String(d.getHours()).padStart(2, '0');
			var mm = String(d.getMinutes()).padStart(2, '0');
			$updated.text((i18n.updated || 'Updated') + ' ' + hh + ':' + mm);
		}

		function paint() {
			$error.attr('hidden', 'hidden').text('');
			$empty.attr('hidden', 'hidden');
			$emptyFilters.attr('hidden', 'hidden');
			$contactsInfo.attr('hidden', 'hidden');
			$listInner.empty();

			if (!allLeads.length) {
				$empty.removeAttr('hidden');
				$resultCount.text('');
				$reset.attr('hidden', 'hidden');
				updateStatusCounts();
				return;
			}

			var filtered = filterLeads();
			var display = sortLeads(filtered);

			if (state.view === 'contacts') {
				if (state.contact === 'none') {
					$contactsInfo.removeAttr('hidden');
				}
				display = contactsViewLeads(display);
			}

			updateStatusCounts();
			populateCountries();

			var total = allLeads.length;
			var shown = display.length;

			$resultCount.text(formatShowing(shown, total));
			if (isFilterActive()) {
				$reset.removeAttr('hidden');
			} else {
				$reset.attr('hidden', 'hidden');
			}

			if (!display.length) {
				if (isFilterActive() || state.view === 'contacts') {
					$emptyFilters.removeAttr('hidden');
				} else {
					$empty.removeAttr('hidden');
				}
				return;
			}

			var html = '';
			if (state.view === 'table') {
				html = renderTable(display);
			} else if (state.view === 'compact') {
				html = renderCompact(display);
			} else if (state.view === 'cards') {
				html = renderCards(display);
			} else if (state.view === 'board') {
				html = renderBoard(display);
			} else if (state.view === 'contacts') {
				html = renderContacts(display);
			}
			$listInner.html(html);
			updateViewUi();
		}

		function setLoading(on) {
			loading = on;
			if (on) {
				$loading.removeAttr('hidden');
				$listInner.empty();
			} else {
				$loading.attr('hidden', 'hidden');
			}
		}

		function loadLeads() {
			$error.attr('hidden', 'hidden').text('');
			setLoading(true);
			$.ajax({
				url: cfg.ajaxUrl,
				method: 'POST',
				dataType: 'json',
				data: {
					action: 'amy_analytics_leads_list',
					nonce: cfg.nonce,
					status: '',
				},
			})
				.done(function (res) {
					setLoading(false);
					if (!res || !res.success) {
						var msg =
							(res && res.data && res.data.message) ||
							i18n.loadError ||
							'Could not load leads.';
						$error.removeAttr('hidden').text(msg);
						allLeads = [];
						paint();
						return;
					}
					var payload = res.data || {};
					allLeads = Array.isArray(payload.leads) ? payload.leads : [];
					lastUpdated = new Date();
					updateUpdatedLabel();
					paint();
				})
				.fail(function () {
					setLoading(false);
					$error.removeAttr('hidden').text(i18n.loadError || 'Could not load leads.');
					allLeads = [];
					paint();
				});
		}

		function savePrefs() {
			clearTimeout(savePrefsTimer);
			savePrefsTimer = setTimeout(function () {
				$.ajax({
					url: cfg.ajaxUrl,
					method: 'POST',
					dataType: 'json',
					data: {
						action: 'amy_analytics_save_prefs',
						nonce: cfg.nonce,
						view: state.view,
						sort: state.sort,
					},
				});
			}, 400);
		}

		function resetFilters() {
			state.search = '';
			state.status = '';
			state.country = '';
			state.seen = '';
			state.contact = '';
			$search.val('');
			$searchClear.attr('hidden', 'hidden');
			$country.val('');
			$seen.val('');
			$contact.val('');
			$statusChips.removeClass('is-active').attr('aria-pressed', 'false');
			$statusChips.filter('[data-amy-status=""]').addClass('is-active').attr('aria-pressed', 'true');
			paint();
		}

		function applyPrefsToUi() {
			state.view = prefs.view || 'table';
			state.sort = prefs.sort || 'newest';
			$sort.val(state.sort);
			if (state.view === 'board') {
				state.status = '';
				$statusChips.removeClass('is-active').attr('aria-pressed', 'false');
				$statusChips.filter('[data-amy-status=""]').addClass('is-active').attr('aria-pressed', 'true');
			}
			updateViewUi();
		}

		$search.on('input', function () {
			var val = String($search.val() || '');
			$searchClear.toggleAttr('hidden', !val);
			clearTimeout(searchTimer);
			searchTimer = setTimeout(function () {
				state.search = val.trim().toLowerCase();
				paint();
			}, 200);
		});

		$search.on('keydown', function (e) {
			if (e.key === 'Escape') {
				state.search = '';
				$search.val('');
				$searchClear.attr('hidden', 'hidden');
				paint();
			}
		});

		$searchClear.on('click', function () {
			state.search = '';
			$search.val('').focus();
			$searchClear.attr('hidden', 'hidden');
			paint();
		});

		$statusChips.on('click', function () {
			if (state.view === 'board') {
				return;
			}
			var next = String($(this).data('amy-status') || '');
			state.status = next;
			$statusChips.removeClass('is-active').attr('aria-pressed', 'false');
			$(this).addClass('is-active').attr('aria-pressed', 'true');
			paint();
		});

		$country.on('change', function () {
			state.country = String($country.val() || '');
			paint();
		});

		$seen.on('change', function () {
			state.seen = String($seen.val() || '');
			paint();
		});

		$contact.on('change', function () {
			state.contact = String($contact.val() || '');
			paint();
		});

		$sort.on('change', function () {
			state.sort = String($sort.val() || 'newest');
			savePrefs();
			paint();
		});

		$refresh.on('click', function () {
			if (!loading) {
				loadLeads();
			}
		});

		$reset.on('click', resetFilters);
		$('#amy-agent-analytics-clear-filters').on('click', resetFilters);

		$viewBtns.on('click', function () {
			state.view = String($(this).data('amy-view') || 'table');
			if (state.view === 'board') {
				state.status = '';
				$statusChips.removeClass('is-active').attr('aria-pressed', 'false');
				$statusChips.filter('[data-amy-status=""]').addClass('is-active').attr('aria-pressed', 'true');
			}
			savePrefs();
			paint();
		});

		$viewBtns.on('keydown', function (e) {
			var $btn = $(this);
			var idx = $viewBtns.index($btn);
			if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
				e.preventDefault();
				var next = $viewBtns.eq((idx + 1) % $viewBtns.length);
				next.focus().trigger('click');
			}
			if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
				e.preventDefault();
				var prev = $viewBtns.eq((idx - 1 + $viewBtns.length) % $viewBtns.length);
				prev.focus().trigger('click');
			}
		});

		$listInner.on('click', '.amy-agent-analytics__copy', function () {
			var text = String($(this).attr('data-amy-copy') || '');
			if (!text) {
				return;
			}
			copyToClipboard(text).then(function () {
				showToast(i18n.copied || 'Copied');
			});
		});

		$.fn.toggleAttr = function (attr, show) {
			if (show) {
				this.removeAttr(attr);
			} else {
				this.attr(attr, attr);
			}
			return this;
		};

		applyPrefsToUi();
		loadLeads();
	});
})(jQuery);
