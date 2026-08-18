/**
 * Amy Agent — SEO Tasks admin page (type buttons, cards, batch checks).
 *
 * Fix fields start empty. Amy does not generate suggested copy or images.
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentSeoTasks || {};
		var i18n = cfg.i18n || {};
		var metaKeys = cfg.metaKeys || {};
		var restUrl = cfg.restUrl || '';

		var currentType = null;
		var items = [];
		var selected = {};
		var resultsById = {};
		var snapshotsById = {};
		var phase = 'idle';
		var countChoice = null;
		var modeChoice = null;
		var batchRun = null;
		var activeItem = null;
		var historyStatus = '';
		var historyVerdict = '';
		var runBusy = false;

		var $error = $('#amy-agent-seo-error');
		var $notice = $('#amy-agent-seo-notice');
		var $empty = $('#amy-agent-seo-empty');
		var $workspace = $('#amy-agent-seo-workspace');
		var $log = $('#amy-agent-seo-log');
		var $selection = $('#amy-agent-seo-selection');
		var $grid = $('#amy-agent-seo-grid');
		var $historyBody = $('#amy-agent-seo-history-body');
		var $historyEmpty = $('#amy-agent-seo-history-empty');
		var $historyError = $('#amy-agent-seo-history-error');
		var $modal = $('#amy-agent-seo-modal');
		var $modalTitle = $('#amy-agent-seo-modal-title');
		var $modalBody = $('#amy-agent-seo-modal-body');

		function escapeHtml(str) {
			return String(str == null ? '' : str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;')
				.replace(/'/g, '&#39;');
		}

		function showError(msg) {
			$error.removeAttr('hidden').text(msg || i18n.error || 'Something went wrong.');
			$notice.attr('hidden', 'hidden').text('');
		}

		function clearError() {
			$error.attr('hidden', 'hidden').text('');
		}

		function showNotice(msg) {
			clearError();
			$notice.removeAttr('hidden').text(msg);
		}

		function stripHtml(html) {
			var tmp = document.createElement('div');
			tmp.innerHTML = html || '';
			return String(tmp.textContent || tmp.innerText || '').replace(/\s+/g, ' ').trim();
		}

		function metaVal(meta, key) {
			if (!meta || typeof meta !== 'object' || !key) {
				return '';
			}
			var value = meta[key];
			if (value == null) {
				return '';
			}
			return String(value).trim();
		}

		function renderedText(value) {
			if (value == null) {
				return '';
			}
			if (typeof value === 'string') {
				return stripHtml(value);
			}
			if (typeof value === 'object') {
				if (value.raw) {
					return String(value.raw).trim();
				}
				if (value.rendered) {
					return stripHtml(value.rendered);
				}
			}
			return String(value).trim();
		}

		function fmt(template, values) {
			var list = Array.isArray(values) ? values.slice() : [values];
			return String(template || '')
				.replace(/%(\d+)\$s/g, function (_, n) {
					var idx = parseInt(n, 10) - 1;
					return list[idx] != null ? String(list[idx]) : '';
				})
				.replace(/%s/g, function () {
					return list.length ? String(list.shift()) : '';
				});
		}

		function restAjax(path, method, body) {
			var opts = {
				url: restUrl + path,
				method: method || 'GET',
				dataType: 'json',
				beforeSend: function (xhr) {
					xhr.setRequestHeader('X-WP-Nonce', cfg.restNonce);
				},
			};
			if (body != null) {
				opts.contentType = 'application/json; charset=UTF-8';
				opts.data = JSON.stringify(body);
			}
			return $.ajax(opts);
		}

		function restGet(path) {
			return restAjax(path, 'GET');
		}

		function restPost(path, body) {
			return restAjax(path, 'POST', body);
		}

		function ajaxAction(action, data) {
			var payload = $.extend(
				{
					action: action,
					nonce: cfg.nonce,
				},
				data || {}
			);
			return $.ajax({
				url: cfg.ajaxUrl,
				method: 'POST',
				dataType: 'json',
				data: payload,
			});
		}

		function restCollection(type) {
			if (type === 'page') {
				return 'wp/v2/pages/';
			}
			if (type === 'media') {
				return 'wp/v2/media/';
			}
			return 'wp/v2/posts/';
		}

		function restPaged(path) {
			var all = [];
			function page(n) {
				var joiner = path.indexOf('?') === -1 ? '?' : '&';
				return $.ajax({
					url: restUrl + path + joiner + 'page=' + n,
					method: 'GET',
					dataType: 'json',
					beforeSend: function (xhr) {
						xhr.setRequestHeader('X-WP-Nonce', cfg.restNonce);
					},
				}).then(function (chunk, _status, xhr) {
					all = all.concat(Array.isArray(chunk) ? chunk : []);
					var pages = parseInt(xhr.getResponseHeader('X-WP-TotalPages') || '1', 10);
					if (!pages || pages < 1) {
						pages = 1;
					}
					if (n < pages) {
						return page(n + 1);
					}
					return all;
				});
			}
			return page(1);
		}

		function restTotal(path) {
			return $.ajax({
				url: restUrl + path,
				method: 'GET',
				dataType: 'json',
				beforeSend: function (xhr) {
					xhr.setRequestHeader('X-WP-Nonce', cfg.restNonce);
				},
			}).then(function (_chunk, _status, xhr) {
				return parseInt(xhr.getResponseHeader('X-WP-Total') || '0', 10) || 0;
			});
		}

		function titleFromPost(post) {
			if (post.title && post.title.raw) {
				return String(post.title.raw).trim();
			}
			if (post.title && post.title.rendered) {
				return stripHtml(post.title.rendered);
			}
			if (post.name) {
				return String(post.name).trim();
			}
			return '';
		}

		function excerptFromPost(post) {
			if (post.excerpt && post.excerpt.raw) {
				return String(post.excerpt.raw).trim();
			}
			if (post.content && post.content.raw) {
				return stripHtml(post.content.raw).slice(0, 500);
			}
			if (post.excerpt && post.excerpt.rendered) {
				return stripHtml(post.excerpt.rendered);
			}
			return '';
		}

		function filenameFromUrl(url) {
			if (!url) {
				return '';
			}
			var clean = String(url).split('?')[0].split('#')[0];
			var parts = clean.split('/');
			return parts.length ? decodeURIComponent(parts[parts.length - 1]) : '';
		}

		function verdictLabel(verdict) {
			if (verdict === 'red') {
				return i18n.verdictRed || 'Needs work';
			}
			if (verdict === 'green') {
				return i18n.verdictGreen || 'Good';
			}
			if (verdict === 'orange') {
				return i18n.verdictOrange || 'Improvements';
			}
			return i18n.notChecked || 'Not checked yet';
		}

		function statusLabel(status) {
			if (status === 'approved') {
				return i18n.statusApproved || 'Approved';
			}
			if (status === 'rejected') {
				return i18n.statusRejected || 'Rejected';
			}
			return i18n.statusPending || 'Pending approval';
		}

		function typeLabel(type) {
			if (type === 'page') {
				return i18n.page || 'Page';
			}
			if (type === 'category') {
				return i18n.category || 'Category';
			}
			if (type === 'tag') {
				return i18n.tag || 'Tag';
			}
			if (type === 'media') {
				return i18n.media || 'Media';
			}
			return i18n.post || 'Post';
		}

		function formatWhen(ts) {
			var seconds = parseFloat(ts);
			if (!seconds) {
				return '—';
			}
			var date = new Date(seconds * 1000);
			if (isNaN(date.getTime())) {
				return '—';
			}
			return date.toLocaleString();
		}

		function verdictRank(verdict) {
			if (verdict === 'red') {
				return 0;
			}
			if (verdict === 'orange') {
				return 1;
			}
			if (verdict === 'green') {
				return 3;
			}
			return 2;
		}

		function sortItems(list) {
			return list.slice().sort(function (a, b) {
				var ra = verdictRank(a.verdict);
				var rb = verdictRank(b.verdict);
				if (ra !== rb) {
					return ra - rb;
				}
				return String(a.title || '').localeCompare(String(b.title || ''));
			});
		}

		function selectedCount() {
			return Object.keys(selected).filter(function (id) {
				return selected[id];
			}).length;
		}

		function selectedItems() {
			return items.filter(function (item) {
				return selected[item.id];
			});
		}

		function listPathForType(type) {
			if (type === 'page') {
				return 'wp/v2/pages?status=publish&per_page=100&_fields=id,title';
			}
			if (type === 'post') {
				return 'wp/v2/posts?status=publish&per_page=100&_fields=id,title';
			}
			if (type === 'category') {
				return 'wp/v2/categories?per_page=100&_fields=id,name,count';
			}
			if (type === 'tag') {
				return 'wp/v2/tags?per_page=100&_fields=id,name,count';
			}
			return 'wp/v2/media?media_type=image&per_page=100&_fields=id,title,alt_text,caption,description,source_url';
		}

		function countPathForType(type) {
			if (type === 'page') {
				return 'wp/v2/pages?status=publish&per_page=1';
			}
			if (type === 'post') {
				return 'wp/v2/posts?status=publish&per_page=1';
			}
			if (type === 'category') {
				return 'wp/v2/categories?per_page=1';
			}
			if (type === 'tag') {
				return 'wp/v2/tags?per_page=1';
			}
			return 'wp/v2/media?media_type=image&per_page=1';
		}

		function loadTypeCounts() {
			['page', 'post', 'category', 'tag', 'media'].forEach(function (type) {
				restTotal(countPathForType(type))
					.done(function (total) {
						$('[data-amy-seo-type-count="' + type + '"]').text(String(total));
					})
					.fail(function () {
						$('[data-amy-seo-type-count="' + type + '"]').text('?');
					});
			});
		}

		function mapListItem(type, raw) {
			var title = titleFromPost(raw) || i18n.untitled || '(untitled)';
			var item = {
				id: raw.id,
				title: title,
				type: type,
				verdict: null,
				checkId: null,
				pending: false,
			};
			if (type === 'media') {
				item.alt_text = raw.alt_text ? String(raw.alt_text).trim() : '';
				item.media_title = title;
				item.caption = renderedText(raw.caption);
				item.description = renderedText(raw.description);
				item.filename = filenameFromUrl(raw.source_url);
			}
			return item;
		}

		function mergeLastVerdicts(list, checks) {
			var latest = {};
			(checks || []).forEach(function (check) {
				var id = check.wp_post_id;
				if (!latest[id]) {
					latest[id] = check;
				}
			});
			list.forEach(function (item) {
				var check = latest[item.id];
				if (check) {
					item.verdict = check.verdict || null;
					item.checkId = check.check_id || null;
					item.status = check.status || null;
				}
			});
			return list;
		}

		function fieldLabel(field) {
			var map = {
				focus_keyphrase: i18n.fieldKeyphrase || 'Focus keyphrase',
				seo_title: i18n.fieldSeoTitle || 'SEO title',
				meta_description: i18n.fieldMetaDesc || 'Meta description',
				featured_image: i18n.fieldFeatured || 'Featured image',
				featured_image_alt: i18n.fieldAlt || 'Featured image alt text',
				alt_text: i18n.fieldMediaAlt || 'Alt text',
				title: i18n.fieldMediaTitle || 'Title',
				caption: i18n.fieldCaption || 'Caption',
				description: i18n.fieldDescription || 'Description',
				term_description: i18n.fieldTermDesc || 'Term description',
				og_social: i18n.fieldOg || 'Facebook / Open Graph',
				twitter_social: i18n.fieldTwitter || 'X / Twitter',
				categories: i18n.fieldCategories || 'Categories',
			};
			return map[field] || field;
		}

		function inputHtml(name, label, value, multiline) {
			var id = 'amy-seo-field-' + name;
			var current = value == null ? '' : String(value);
			if (multiline) {
				return (
					'<label class="amy-agent-seo__label" for="' +
					id +
					'">' +
					escapeHtml(label) +
					'</label>' +
					'<textarea class="amy-agent-seo__input" id="' +
					id +
					'" name="' +
					escapeHtml(name) +
					'" rows="3">' +
					escapeHtml(current) +
					'</textarea>'
				);
			}
			return (
				'<label class="amy-agent-seo__label" for="' +
				id +
				'">' +
				escapeHtml(label) +
				'</label>' +
				'<input class="amy-agent-seo__input" id="' +
				id +
				'" name="' +
				escapeHtml(name) +
				'" type="text" value="' +
				escapeHtml(current) +
				'" />'
			);
		}

		function fixFieldsForFinding(finding, type) {
			var field = finding.field;
			if (field === 'featured_image') {
				return (
					'<p class="amy-agent-seo__deferred">' +
					escapeHtml(
						i18n.noImageGen ||
							'Amy can report a missing featured image, but image generation is not in this version.'
					) +
					'</p>'
				);
			}
			if (field === 'categories') {
				if (type === 'page') {
					return (
						'<p class="amy-agent-seo__deferred">' +
						escapeHtml(
							i18n.pageCategories ||
								'Pages do not use categories in WordPress. This finding is informational.'
						) +
						'</p>'
					);
				}
				return (
					'<p class="amy-agent-seo__deferred">' +
					escapeHtml(
						i18n.categoriesHint ||
							'Assign categories in the post editor, or pick them below if the list loads.'
					) +
					'</p>' +
					'<div class="amy-agent-seo__categories" data-amy-seo-categories></div>'
				);
			}
			if (field === 'og_social') {
				return (
					inputHtml('og_title', i18n.fieldOgTitle || 'Facebook title', '', false) +
					inputHtml('og_description', i18n.fieldOgDesc || 'Facebook description', '', true) +
					inputHtml('og_image', i18n.fieldOgImage || 'Facebook image URL', '', false)
				);
			}
			if (field === 'twitter_social') {
				return (
					inputHtml('twitter_title', i18n.fieldTwTitle || 'X title', '', false) +
					inputHtml('twitter_description', i18n.fieldTwDesc || 'X description', '', true) +
					inputHtml('twitter_image', i18n.fieldTwImage || 'X image URL', '', false)
				);
			}
			if (
				field === 'meta_description' ||
				field === 'caption' ||
				field === 'description' ||
				field === 'term_description'
			) {
				return inputHtml(field, fieldLabel(field), '', true);
			}
			return inputHtml(field, fieldLabel(field), '', false);
		}

		function renderFindings(check, readonly, type) {
			var findings = Array.isArray(check.findings) ? check.findings : [];
			var html = '';
			if (!findings.length) {
				html =
					'<p class="amy-agent-seo__empty-findings">' +
					escapeHtml(i18n.noFindings || 'No issues found on the fields Amy checks in this version.') +
					'</p>';
			} else {
				findings.forEach(function (finding) {
					html +=
						'<article class="amy-agent-seo__finding">' +
						'<header class="amy-agent-seo__finding-head">' +
						'<span class="amy-agent-seo__finding-field">' +
						escapeHtml(fieldLabel(finding.field)) +
						'</span>' +
						'<span class="amy-agent-seo__pill amy-agent-seo__pill--' +
						escapeHtml(finding.severity || 'missing') +
						'">' +
						escapeHtml(
							finding.severity === 'weak'
								? i18n.severityWeak || 'Weak'
								: i18n.severityMissing || 'Missing'
						) +
						'</span>' +
						'</header>' +
						'<p class="amy-agent-seo__finding-msg">' +
						escapeHtml(finding.message || '') +
						'</p>';
					if (!readonly) {
						html += '<div class="amy-agent-seo__fix">' + fixFieldsForFinding(finding, type) + '</div>';
					}
					html += '</article>';
				});
			}
			return html;
		}

		function loadCategories($mount) {
			if (!$mount.length) {
				return;
			}
			restGet('wp/v2/categories?per_page=100')
				.done(function (cats) {
					if (!Array.isArray(cats) || !cats.length) {
						$mount.html(
							'<p class="amy-agent-seo__deferred">' +
								escapeHtml(i18n.noCategories || 'No categories exist on this site yet.') +
								'</p>'
						);
						return;
					}
					var html = '';
					cats.forEach(function (cat) {
						html +=
							'<label class="amy-agent-seo__check">' +
							'<input type="checkbox" name="category_ids" value="' +
							escapeHtml(String(cat.id)) +
							'" /> ' +
							escapeHtml(cat.name || '') +
							'</label>';
					});
					$mount.html(html);
				})
				.fail(function () {
					$mount.html(
						'<p class="amy-agent-seo__deferred">' +
							escapeHtml(i18n.categoriesLoadError || 'Could not load categories.') +
							'</p>'
					);
				});
		}

		function collectApprovedFields($root) {
			var fields = {};
			$root.find('.amy-agent-seo__input').each(function () {
				var name = this.name;
				var value = String($(this).val() || '').trim();
				if (name && value) {
					fields[name] = value;
				}
			});
			var ids = [];
			$root.find('input[name="category_ids"]:checked').each(function () {
				var id = parseInt($(this).val(), 10);
				if (id > 0) {
					ids.push(id);
				}
			});
			if (ids.length) {
				fields.category_ids = ids;
			}
			return fields;
		}

		function writeApprovedToWordPress(fields, item) {
			var type = item.type || currentType;
			if (type === 'category' || type === 'tag') {
				var termPayload = {
					taxonomy: type,
					term_id: item.id,
				};
				if (fields.seo_title) {
					termPayload.seo_title = fields.seo_title;
				}
				if (fields.meta_description) {
					termPayload.meta_description = fields.meta_description;
				}
				if (!termPayload.seo_title && !termPayload.meta_description) {
					return $.Deferred().resolve().promise();
				}
				return ajaxAction('amy_seo_term_write', termPayload).then(function (res) {
					if (!res || !res.success) {
						return $.Deferred()
							.reject()
							.promise();
					}
					return res;
				});
			}
			if (type === 'media') {
				var mediaBody = {};
				if (fields.alt_text) {
					mediaBody.alt_text = fields.alt_text;
				}
				if (fields.title) {
					mediaBody.title = { raw: fields.title };
				}
				if (fields.caption) {
					mediaBody.caption = { raw: fields.caption };
				}
				if (fields.description) {
					mediaBody.description = { raw: fields.description };
				}
				if (!Object.keys(mediaBody).length) {
					return $.Deferred().resolve().promise();
				}
				return restPost('wp/v2/media/' + item.id, mediaBody);
			}
			var writes = [];
			var meta = {};
			Object.keys(metaKeys).forEach(function (field) {
				if (fields[field]) {
					meta[metaKeys[field]] = fields[field];
				}
			});
			var body = {};
			if (Object.keys(meta).length) {
				body.meta = meta;
			}
			if (fields.category_ids && type === 'post') {
				body.categories = fields.category_ids;
			}
			if (Object.keys(body).length) {
				writes.push(restPost(restCollection(type) + item.id, body));
			}
			var snap = snapshotsById[item.id];
			if (fields.featured_image_alt && snap && snap.featured_media_id) {
				writes.push(
					restPost('wp/v2/media/' + snap.featured_media_id, {
						alt_text: fields.featured_image_alt,
					})
				);
			}
			if (!writes.length) {
				return $.Deferred().resolve().promise();
			}
			return $.when.apply($, writes);
		}

		function assemblePostSnapshot(post, media, type) {
			var meta = post.meta || {};
			var hasImage = !!(post.featured_media && post.featured_media > 0);
			var alt = '';
			if (hasImage && media) {
				alt = media.alt_text ? String(media.alt_text).trim() : '';
			}
			var cats = Array.isArray(post.categories) ? post.categories : [];
			return {
				title: titleFromPost(post),
				content_excerpt: excerptFromPost(post),
				focus_keyphrase: metaVal(meta, metaKeys.focus_keyphrase),
				seo_title: metaVal(meta, metaKeys.seo_title),
				meta_description: metaVal(meta, metaKeys.meta_description),
				has_featured_image: hasImage,
				featured_image_alt: alt,
				featured_media_id: hasImage ? post.featured_media : 0,
				og_title: metaVal(meta, metaKeys.og_title),
				og_description: metaVal(meta, metaKeys.og_description),
				og_image: metaVal(meta, metaKeys.og_image),
				twitter_title: metaVal(meta, metaKeys.twitter_title),
				twitter_description: metaVal(meta, metaKeys.twitter_description),
				twitter_image: metaVal(meta, metaKeys.twitter_image),
				category_count: type === 'page' ? 0 : cats.length,
				category_ids: cats,
			};
		}

		function snapshotForItem(item) {
			if (item.type === 'media') {
				var mediaSnap = {
					alt_text: item.alt_text || '',
					title: item.media_title || item.title || '',
					caption: item.caption || '',
					description: item.description || '',
					filename: item.filename || '',
				};
				return $.Deferred().resolve(mediaSnap).promise();
			}
			if (item.type === 'category' || item.type === 'tag') {
				return ajaxAction('amy_seo_term_get', {
					taxonomy: item.type,
					term_id: item.id,
				}).then(function (res) {
					var data = (res && res.success && res.data) || {};
					return {
						seo_title: data.seo_title || '',
						meta_description: data.meta_description || '',
						term_description: data.term_description || '',
					};
				});
			}
			var path = restCollection(item.type) + item.id + '?context=edit';
			return restGet(path).then(function (post) {
				var mediaId = post.featured_media || 0;
				if (!mediaId) {
					return assemblePostSnapshot(post, null, item.type);
				}
				return restGet('wp/v2/media/' + mediaId).then(
					function (media) {
						return assemblePostSnapshot(post, media, item.type);
					},
					function () {
						return assemblePostSnapshot(post, null, item.type);
					}
				);
			});
		}

		function buildBatchItems(chosen) {
			var d = $.Deferred();
			var out = [];
			var idx = 0;
			function step() {
				if (idx >= chosen.length) {
					d.resolve(out);
					return;
				}
				var item = chosen[idx++];
				item.pending = true;
				updateCard(item);
				snapshotForItem(item)
					.done(function (snapshot) {
						snapshotsById[item.id] = snapshot;
						out.push({
							item_id: item.id,
							title: item.title,
							snapshot: snapshot,
						});
						step();
					})
					.fail(function () {
						out.push({
							item_id: item.id,
							title: item.title,
							snapshot: {},
						});
						step();
					});
			}
			step();
			return d.promise();
		}

		function cardBadge(item) {
			var result = resultsById[item.id];
			if (result && result.error) {
				return (
					'<span class="amy-agent-seo__pill amy-agent-seo__pill--red">' +
					escapeHtml(i18n.itemError || 'Error') +
					'</span>'
				);
			}
			var verdict = (result && result.verdict) || item.verdict;
			if (!verdict) {
				return (
					'<span class="amy-agent-seo__pill amy-agent-seo__pill--muted">' +
					escapeHtml(i18n.notChecked || 'Not checked yet') +
					'</span>'
				);
			}
			return (
				'<span class="amy-agent-seo__pill amy-agent-seo__pill--' +
				escapeHtml(verdict) +
				'">' +
				escapeHtml(verdictLabel(verdict)) +
				'</span>'
			);
		}

		function renderGrid() {
			if (!items.length) {
				$grid.html(
					'<p class="amy-agent-seo__empty-list">' +
						escapeHtml(i18n.emptyList || 'Nothing published in this type yet.') +
						'</p>'
				);
				return;
			}
			var html = '';
			items.forEach(function (item) {
				var classes = 'amy-agent-seo__card';
				if (selected[item.id]) {
					classes += ' is-selected';
				}
				if (item.pending) {
					classes += ' is-pending';
				}
				if (resultsById[item.id]) {
					classes += ' is-checked';
				}
				html +=
					'<button type="button" class="' +
					classes +
					'" data-item-id="' +
					escapeHtml(String(item.id)) +
					'">' +
					'<span class="amy-agent-seo__card-spinner" aria-hidden="true"></span>' +
					'<span class="amy-agent-seo__card-title">' +
					escapeHtml(item.title || i18n.untitled || '(untitled)') +
					'</span>' +
					cardBadge(item) +
					'</button>';
			});
			$grid.html(html);
			updateSelectionLabel();
		}

		function updateCard(item) {
			var $card = $grid.find('[data-item-id="' + item.id + '"]');
			if (!$card.length) {
				return;
			}
			$card.toggleClass('is-selected', !!selected[item.id]);
			$card.toggleClass('is-pending', !!item.pending);
			$card.toggleClass('is-checked', !!resultsById[item.id]);
			$card.find('.amy-agent-seo__pill, .amy-agent-seo__card-title').remove();
			$card.append(
				'<span class="amy-agent-seo__card-title">' +
					escapeHtml(item.title || i18n.untitled || '(untitled)') +
					'</span>'
			);
			$card.append(cardBadge(item));
		}

		function updateSelectionLabel() {
			var n = selectedCount();
			if (n && (phase === 'pick' || phase === 'hand')) {
				$selection
					.removeAttr('hidden')
					.text(fmt(i18n.selectedCount || '%s selected', [n]));
			} else {
				$selection.attr('hidden', 'hidden').text('');
			}
		}

		function appendBubble(text, actions) {
			var html =
				'<div class="amy-agent-seo__bubble">' +
				'<p class="amy-agent-seo__bubble-text">' +
				escapeHtml(text) +
				'</p>';
			if (actions && actions.length) {
				html += '<div class="amy-agent-seo__choices">';
				actions.forEach(function (action) {
					html +=
						'<button type="button" class="amy-agent-seo__btn ' +
						(action.accent ? 'amy-agent-seo__btn--accent' : 'amy-agent-seo__btn--ghost') +
						'" data-amy-choice="' +
						escapeHtml(action.id) +
						'">' +
						escapeHtml(action.label) +
						'</button>';
				});
				html += '</div>';
			}
			html += '</div>';
			$log.append(html);
			var el = $log.get(0);
			if (el) {
				el.scrollTop = el.scrollHeight;
			}
		}

		function disableLogChoices() {
			$log.find('[data-amy-choice]').prop('disabled', true);
		}

		function showCountPrompt() {
			phase = 'pick';
			countChoice = null;
			modeChoice = null;
			appendBubble(i18n.promptLoaded || 'Here they are. Check all, 5, or 10 — or click cards to pick exactly which ones.', [
				{ id: 'count:all', label: i18n.choiceAll || 'All' },
				{ id: 'count:5', label: i18n.choice5 || '5' },
				{ id: 'count:10', label: i18n.choice10 || '10' },
			]);
		}

		function showHandStart() {
			phase = 'hand';
			modeChoice = 'manual';
			disableLogChoices();
			appendBubble(i18n.promptHand || 'Start with the cards you picked. Amy will check just those.', [
				{
					id: 'start',
					label: fmt(i18n.startSelected || 'Start (%s selected)', [selectedCount()]),
					accent: true,
				},
			]);
		}

		function showModePrompt() {
			phase = 'count';
			appendBubble(i18n.promptCount || 'Manual (one batch at a time) or automatic (everything in this run)?', [
				{ id: 'mode:manual', label: i18n.choiceManual || 'Manual' },
				{ id: 'mode:auto', label: i18n.choiceAuto || 'Automatic' },
			]);
		}

		function showModeStart() {
			appendBubble(
				(modeChoice === 'auto' ? i18n.choiceAuto : i18n.choiceManual) + '.',
				[{ id: 'start', label: i18n.startRun || 'Start', accent: true }]
			);
		}

		function itemsForRun() {
			if (countChoice === 5) {
				return items.slice(0, 5);
			}
			if (countChoice === 10) {
				return items.slice(0, 10);
			}
			if (countChoice === 'all') {
				return items.slice();
			}
			return selectedItems();
		}

		function applyResult(result) {
			var id = result.item_id;
			var item = items.filter(function (row) {
				return row.id === id;
			})[0];
			resultsById[id] = result;
			if (item) {
				item.pending = false;
				if (result.error) {
					item.verdict = null;
				} else {
					item.verdict = result.verdict || item.verdict;
					item.checkId = result.check_id || item.checkId;
				}
				updateCard(item);
			}
		}

		function applyReport(report) {
			var results = (report && report.results) || [];
			results.forEach(applyResult);
		}

		function summarize(run) {
			var reports = run.reports || [];
			var red = 0;
			var orange = 0;
			var green = 0;
			var errors = 0;
			var checked = 0;
			reports.forEach(function (report) {
				(report.results || []).forEach(function (result) {
					checked += 1;
					if (result.error) {
						errors += 1;
					} else if (result.verdict === 'red') {
						red += 1;
					} else if (result.verdict === 'green') {
						green += 1;
					} else {
						orange += 1;
					}
				});
			});
			var line = fmt(i18n.summaryLine || 'Checked %1$s of %2$s. %3$s need work, %4$s have improvements, %5$s are good.', [
				checked,
				run.total_items || checked,
				red,
				orange,
				green,
			]);
			if (errors) {
				line += ' ' + fmt(i18n.summaryErrors || '%s had errors.', [errors]);
			}
			appendBubble(line);
			loadHistory();
		}

		function revealAuto(run) {
			var reports = run.reports || [];
			var i = 0;
			function next() {
				if (i >= reports.length) {
					phase = 'done';
					runBusy = false;
					summarize(run);
					return;
				}
				applyReport(reports[i]);
				i += 1;
				if (i < reports.length) {
					window.setTimeout(next, 400);
				} else {
					phase = 'done';
					runBusy = false;
					summarize(run);
				}
			}
			if (!reports.length) {
				phase = 'done';
				runBusy = false;
				summarize(run);
				return;
			}
			next();
		}

		function afterManualBatch(run) {
			var reports = run.reports || [];
			if (reports.length) {
				applyReport(reports[reports.length - 1]);
			}
			loadHistory();
			if (run.status === 'completed') {
				phase = 'done';
				runBusy = false;
				summarize(run);
				return;
			}
			phase = 'await-continue';
			runBusy = false;
			appendBubble(i18n.promptContinue || 'That batch is done. Continue, or stop here?', [
				{ id: 'continue', label: i18n.continue || 'Continue', accent: true },
				{ id: 'stop', label: i18n.stop || 'Stop' },
			]);
		}

		function markPending(chosen) {
			chosen.forEach(function (item) {
				item.pending = true;
				updateCard(item);
			});
		}

		function startRun() {
			if (runBusy) {
				return;
			}
			var chosen = itemsForRun();
			if (!chosen.length) {
				return;
			}
			var isHand = countChoice == null;
			var mode = isHand ? 'manual' : modeChoice || 'manual';
			var batchSize = 5;
			if (countChoice === 5 || countChoice === 10 || isHand) {
				batchSize = chosen.length;
			}
			runBusy = true;
			phase = 'busy';
			disableLogChoices();
			clearError();
			appendBubble(i18n.buildingSnapshots || 'Gathering live fields…');
			markPending(chosen);
			buildBatchItems(chosen).done(function (payload) {
				appendBubble(i18n.promptWorking || 'Working through this batch…');
				ajaxAction('amy_seo_batch_start', {
					content_type: currentType,
					mode: mode,
					batch_size: batchSize,
					items: JSON.stringify(payload),
				})
					.done(function (res) {
						if (!res || !res.success) {
							showError(
								(res && res.data && res.data.message) ||
									i18n.checkError ||
									'Could not run the SEO check.'
							);
							chosen.forEach(function (item) {
								item.pending = false;
								updateCard(item);
							});
							runBusy = false;
							phase = 'done';
							return;
						}
						batchRun = res.data || {};
						if (batchRun.mode === 'auto') {
							revealAuto(batchRun);
						} else {
							afterManualBatch(batchRun);
						}
					})
					.fail(function (xhr) {
						var msg =
							xhr.responseJSON &&
							xhr.responseJSON.data &&
							xhr.responseJSON.data.message;
						showError(msg || i18n.checkError || 'Could not run the SEO check.');
						chosen.forEach(function (item) {
							item.pending = false;
							updateCard(item);
						});
						runBusy = false;
						phase = 'done';
					});
			});
		}

		function continueRun() {
			if (!batchRun || runBusy) {
				return;
			}
			runBusy = true;
			disableLogChoices();
			appendBubble(i18n.promptWorking || 'Working through this batch…');
			ajaxAction('amy_seo_batch_continue', { batch_run_id: batchRun.batch_run_id })
				.done(function (res) {
					if (!res || !res.success) {
						showError(
							(res && res.data && res.data.message) ||
								i18n.checkError ||
								'Could not run the SEO check.'
						);
						runBusy = false;
						return;
					}
					batchRun = res.data || {};
					afterManualBatch(batchRun);
				})
				.fail(function (xhr) {
					var msg =
						xhr.responseJSON &&
						xhr.responseJSON.data &&
						xhr.responseJSON.data.message;
					showError(msg || i18n.checkError || 'Could not run the SEO check.');
					runBusy = false;
				});
		}

		function stopRun() {
			if (!batchRun || runBusy) {
				return;
			}
			runBusy = true;
			disableLogChoices();
			ajaxAction('amy_seo_batch_stop', { batch_run_id: batchRun.batch_run_id })
				.done(function (res) {
					runBusy = false;
					phase = 'done';
					if (res && res.success) {
						batchRun = res.data || batchRun;
					}
					items.forEach(function (item) {
						item.pending = false;
						updateCard(item);
					});
					appendBubble(i18n.promptStopped || 'Stopped. Already-checked cards stay as they are.');
					loadHistory();
				})
				.fail(function (xhr) {
					runBusy = false;
					var msg =
						xhr.responseJSON &&
						xhr.responseJSON.data &&
						xhr.responseJSON.data.message;
					showError(msg || i18n.error || 'Something went wrong.');
				});
		}

		function renderModalCheck(check, item, readonly) {
			var verdict = check.verdict || 'orange';
			var html =
				'<div class="amy-agent-seo__verdict amy-agent-seo__verdict--' +
				escapeHtml(verdict) +
				'">' +
				'<span class="amy-agent-seo__verdict-label">' +
				escapeHtml(verdictLabel(verdict)) +
				'</span>' +
				'<span class="amy-agent-seo__verdict-status">' +
				escapeHtml(statusLabel(check.status)) +
				'</span>' +
				'</div>' +
				'<p class="amy-agent-seo__suggest-note">' +
				escapeHtml(
					i18n.noAiCopy ||
						'Amy is reporting what is missing. Suggested copy is not generated in this version — fill in the fields yourself before approving.'
				) +
				'</p>' +
				'<div class="amy-agent-seo__findings">' +
				renderFindings(check, readonly, item.type || currentType) +
				'</div>';
			if (!readonly && check.status === 'pending_approval') {
				html +=
					'<div class="amy-agent-seo__actions">' +
					'<label class="amy-agent-seo__label" for="amy-agent-seo-reject-reason">' +
					escapeHtml(i18n.rejectReason || 'Reject reason (optional)') +
					'</label>' +
					'<textarea class="amy-agent-seo__input" id="amy-agent-seo-reject-reason" rows="2"></textarea>' +
					'<div class="amy-agent-seo__action-row">' +
					'<button type="button" class="amy-agent-seo__btn amy-agent-seo__btn--accent" id="amy-agent-seo-approve">' +
					escapeHtml(i18n.approve || 'Approve & write') +
					'</button>' +
					'<button type="button" class="amy-agent-seo__btn amy-agent-seo__btn--ghost" id="amy-agent-seo-reject">' +
					escapeHtml(i18n.reject || 'Reject') +
					'</button>' +
					'</div></div>';
			}
			$modalBody.html(html);
			if (!readonly) {
				loadCategories($modalBody.find('[data-amy-seo-categories]'));
			}
		}

		function openModal(check, item) {
			activeItem = item;
			$modalTitle.text(item.title || i18n.untitled || '(untitled)');
			var readonly = check.status !== 'pending_approval';
			var type = item.type || check.content_type || currentType;
			item.type = type;
			if (readonly || snapshotsById[item.id] || type === 'media' || type === 'category' || type === 'tag') {
				if (!snapshotsById[item.id] && (type === 'category' || type === 'tag' || type === 'media')) {
					snapshotForItem(item).done(function (snap) {
						snapshotsById[item.id] = snap;
					});
				}
				renderModalCheck(check, item, readonly);
				$modal.prop('hidden', false);
				return;
			}
			snapshotForItem(item)
				.done(function (snap) {
					snapshotsById[item.id] = snap;
					renderModalCheck(check, item, readonly);
					$modal.prop('hidden', false);
				})
				.fail(function () {
					renderModalCheck(check, item, readonly);
					$modal.prop('hidden', false);
				});
		}

		function closeModal() {
			$modal.prop('hidden', true);
			activeItem = null;
			$modalBody.empty();
		}

		function openResultForItem(item) {
			var local = resultsById[item.id];
			if (local && local.error) {
				showError(local.error);
				return;
			}
			var checkId = (local && local.check_id) || item.checkId;
			if (!checkId) {
				return;
			}
			ajaxAction('amy_seo_check_get', { check_id: checkId })
				.done(function (res) {
					if (!res || !res.success) {
						showError(
							(res && res.data && res.data.message) ||
								i18n.loadCheckError ||
								'Could not load that check.'
						);
						return;
					}
					openModal(res.data || {}, item);
				})
				.fail(function () {
					showError(i18n.loadCheckError || 'Could not load that check.');
				});
		}

		function onCardClick(item) {
			if (runBusy || phase === 'busy') {
				return;
			}
			if (resultsById[item.id] || (item.checkId && (phase === 'done' || phase === 'await-continue' || phase === 'count'))) {
				openResultForItem(item);
				return;
			}
			if (phase === 'count' || phase === 'await-continue' || phase === 'done') {
				if (item.checkId) {
					openResultForItem(item);
				}
				return;
			}
			if (phase !== 'pick' && phase !== 'hand') {
				return;
			}
			if (selected[item.id]) {
				delete selected[item.id];
			} else {
				selected[item.id] = true;
			}
			if (selectedCount()) {
				if (phase !== 'hand') {
					showHandStart();
				} else {
					$log.find('[data-amy-choice="start"]').text(
						fmt(i18n.startSelected || 'Start (%s selected)', [selectedCount()])
					);
				}
			} else {
				phase = 'pick';
				disableLogChoices();
				showCountPrompt();
			}
			updateCard(item);
			updateSelectionLabel();
		}

		function loadType(type) {
			if (runBusy) {
				return;
			}
			currentType = type;
			selected = {};
			resultsById = {};
			snapshotsById = {};
			batchRun = null;
			countChoice = null;
			modeChoice = null;
			items = [];
			$('.amy-agent-seo__type').removeClass('is-active');
			$('.amy-agent-seo__type[data-amy-seo-type="' + type + '"]').addClass('is-active');
			$empty.attr('hidden', 'hidden');
			$workspace.removeAttr('hidden');
			$log.empty();
			$grid.empty();
			clearError();
			appendBubble(i18n.checking || 'Checking…');
			restPaged(listPathForType(type))
				.then(function (raw) {
					var mapped = (Array.isArray(raw) ? raw : []).map(function (row) {
						return mapListItem(type, row);
					});
					return ajaxAction('amy_seo_checks_list', { content_type: type }).then(
						function (checkRes) {
							var checks =
								checkRes && checkRes.success && checkRes.data && checkRes.data.checks
									? checkRes.data.checks
									: [];
							return mergeLastVerdicts(mapped, checks);
						},
						function () {
							return mapped;
						}
					);
				})
				.then(function (list) {
					items = sortItems(list || []);
					$log.empty();
					renderGrid();
					if (!items.length) {
						phase = 'idle';
						appendBubble(i18n.emptyList || 'Nothing published in this type yet.');
					} else {
						showCountPrompt();
					}
					loadHistory();
				})
				.fail(function () {
					$log.empty();
					showError(i18n.loadListError || 'Could not load that content list from WordPress.');
				});
		}

		function loadHistory() {
			$historyError.attr('hidden', 'hidden').text('');
			var payload = {
				status: historyStatus,
				verdict: historyVerdict,
			};
			if (currentType) {
				payload.content_type = currentType;
			}
			ajaxAction('amy_seo_checks_list', payload)
				.done(function (res) {
					if (!res || !res.success) {
						$historyBody.empty();
						$historyEmpty.attr('hidden', 'hidden');
						$historyError
							.removeAttr('hidden')
							.text(
								(res && res.data && res.data.message) ||
									i18n.historyError ||
									'Could not load previous checks.'
							);
						return;
					}
					var checks = (res.data && res.data.checks) || [];
					$historyBody.empty();
					if (!checks.length) {
						$historyEmpty.removeAttr('hidden');
						return;
					}
					$historyEmpty.attr('hidden', 'hidden');
					checks.forEach(function (check) {
						var tr = document.createElement('tr');
						tr.className = 'amy-agent-seo__history-row';
						tr.setAttribute('data-check-id', check.check_id);
						tr.innerHTML =
							'<td>' +
							escapeHtml(check.title || '#' + check.wp_post_id) +
							'</td>' +
							'<td>' +
							escapeHtml(check.content_type || check.post_type || '') +
							' #' +
							escapeHtml(String(check.wp_post_id)) +
							'</td>' +
							'<td><span class="amy-agent-seo__pill amy-agent-seo__pill--' +
							escapeHtml(check.verdict || 'orange') +
							'">' +
							escapeHtml(verdictLabel(check.verdict)) +
							'</span></td>' +
							'<td>' +
							escapeHtml(statusLabel(check.status)) +
							'</td>' +
							'<td>' +
							escapeHtml(formatWhen(check.checked_at)) +
							'</td>';
						$historyBody.append(tr);
					});
				})
				.fail(function () {
					$historyBody.empty();
					$historyEmpty.attr('hidden', 'hidden');
					$historyError
						.removeAttr('hidden')
						.text(i18n.historyError || 'Could not load previous checks.');
				});
		}

		$('.amy-agent-seo__type').on('click', function () {
			var type = String($(this).data('amy-seo-type') || '');
			if (!type || runBusy) {
				return;
			}
			loadType(type);
		});

		$grid.on('click', '.amy-agent-seo__card', function () {
			var id = parseInt($(this).attr('data-item-id'), 10);
			var item = items.filter(function (row) {
				return row.id === id;
			})[0];
			if (item) {
				onCardClick(item);
			}
		});

		$log.on('click', '[data-amy-choice]', function () {
			var choice = String($(this).data('amy-choice') || '');
			if (!choice || $(this).prop('disabled')) {
				return;
			}
			if (choice.indexOf('count:') === 0) {
				if (phase === 'hand') {
					return;
				}
				disableLogChoices();
				var raw = choice.split(':')[1];
				countChoice = raw === 'all' ? 'all' : parseInt(raw, 10);
				selected = {};
				renderGrid();
				showModePrompt();
				return;
			}
			if (choice.indexOf('mode:') === 0) {
				disableLogChoices();
				modeChoice = choice.split(':')[1] === 'auto' ? 'auto' : 'manual';
				showModeStart();
				return;
			}
			if (choice === 'start') {
				startRun();
				return;
			}
			if (choice === 'continue') {
				continueRun();
				return;
			}
			if (choice === 'stop') {
				stopRun();
			}
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

		$modalBody.on('click', '#amy-agent-seo-approve', function () {
			if (!activeItem) {
				return;
			}
			var local = resultsById[activeItem.id];
			var checkId = (local && local.check_id) || activeItem.checkId;
			if (!checkId) {
				return;
			}
			var $btn = $(this);
			var fields = collectApprovedFields($modalBody);
			$btn.prop('disabled', true).text(i18n.saving || 'Saving…');
			writeApprovedToWordPress(fields, activeItem)
				.done(function () {
					ajaxAction('amy_seo_check_approve', {
						check_id: checkId,
						approved_fields: JSON.stringify(fields),
					})
						.done(function (res) {
							if (!res || !res.success) {
								showError(
									(res && res.data && res.data.message) ||
										i18n.approveError ||
										'WordPress was updated, but recording approval failed.'
								);
								return;
							}
							showNotice(i18n.approveSuccess || 'Approved. Fields were written to WordPress.');
							renderModalCheck(res.data || {}, activeItem, true);
							loadHistory();
						})
						.fail(function (xhr) {
							var msg =
								xhr.responseJSON &&
								xhr.responseJSON.data &&
								xhr.responseJSON.data.message;
							showError(
								msg ||
									i18n.approveError ||
									'WordPress was updated, but recording approval failed.'
							);
						})
						.always(function () {
							$btn.prop('disabled', false).text(i18n.approve || 'Approve & write');
						});
				})
				.fail(function () {
					var type = activeItem.type || currentType;
					showError(
						type === 'category' || type === 'tag'
							? i18n.termWriteError || 'Could not write Yoast fields for this category or tag.'
							: i18n.writeError || 'Could not write fields through the WordPress REST API.'
					);
					$btn.prop('disabled', false).text(i18n.approve || 'Approve & write');
				});
		});

		$modalBody.on('click', '#amy-agent-seo-reject', function () {
			if (!activeItem) {
				return;
			}
			var local = resultsById[activeItem.id];
			var checkId = (local && local.check_id) || activeItem.checkId;
			if (!checkId) {
				return;
			}
			var $btn = $(this);
			var reason = String($('#amy-agent-seo-reject-reason').val() || '').trim();
			$btn.prop('disabled', true);
			ajaxAction('amy_seo_check_reject', {
				check_id: checkId,
				reason: reason,
			})
				.done(function (res) {
					if (!res || !res.success) {
						showError(
							(res && res.data && res.data.message) ||
								i18n.rejectError ||
								'Could not reject this check.'
						);
						return;
					}
					showNotice(i18n.rejectSuccess || 'Check rejected. Nothing was written to WordPress.');
					renderModalCheck(res.data || {}, activeItem, true);
					loadHistory();
				})
				.fail(function (xhr) {
					var msg =
						xhr.responseJSON &&
						xhr.responseJSON.data &&
						xhr.responseJSON.data.message;
					showError(msg || i18n.rejectError || 'Could not reject this check.');
				})
				.always(function () {
					$btn.prop('disabled', false);
				});
		});

		$historyBody.on('click', 'tr[data-check-id]', function () {
			var id = $(this).attr('data-check-id');
			if (!id) {
				return;
			}
			clearError();
			ajaxAction('amy_seo_check_get', { check_id: id })
				.done(function (res) {
					if (!res || !res.success) {
						showError(
							(res && res.data && res.data.message) ||
								i18n.loadCheckError ||
								'Could not load that check.'
						);
						return;
					}
					var check = res.data || {};
					openModal(check, {
						id: check.wp_post_id,
						title: check.title || '',
						type: check.content_type || check.post_type || currentType || 'post',
						checkId: check.check_id,
					});
				})
				.fail(function () {
					showError(i18n.loadCheckError || 'Could not load that check.');
				});
		});

		$('[data-amy-seo-history-status]').on('click', function () {
			historyStatus = String($(this).data('amy-seo-history-status') || '');
			$('[data-amy-seo-history-status]').removeClass('is-active').attr('aria-selected', 'false');
			$(this).addClass('is-active').attr('aria-selected', 'true');
			loadHistory();
		});

		$('[data-amy-seo-history-verdict]').on('click', function () {
			historyVerdict = String($(this).data('amy-seo-history-verdict') || '');
			$('[data-amy-seo-history-verdict]').removeClass('is-active').attr('aria-selected', 'false');
			$(this).addClass('is-active').attr('aria-selected', 'true');
			loadHistory();
		});

		loadTypeCounts();
		loadHistory();
	});
})(jQuery);
