/**
 * Amy Agent — SEO Tasks admin page (single-target check + approval).
 *
 * Proposed-fix fields start empty: this task only detects issues. Amy does not
 * generate suggested copy or images here. Full-site sweep is not in this page.
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentSeoTasks || {};
		var i18n = cfg.i18n || {};
		var metaKeys = cfg.metaKeys || {};
		var restUrl = cfg.restUrl || '';
		var searchTimer = null;
		var selected = null;
		var currentCheck = null;
		var historyStatus = '';
		var historyVerdict = '';
		var lastSnapshot = null;

		var $error = $('#amy-agent-seo-error');
		var $notice = $('#amy-agent-seo-notice');
		var $search = $('#amy-agent-seo-search');
		var $results = $('#amy-agent-seo-search-results');
		var $selected = $('#amy-agent-seo-selected');
		var $checkBtn = $('#amy-agent-seo-check');
		var $resultsPanel = $('#amy-agent-seo-results');
		var $historyBody = $('#amy-agent-seo-history-body');
		var $historyEmpty = $('#amy-agent-seo-history-empty');
		var $historyError = $('#amy-agent-seo-history-error');

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

		function restGet(path) {
			return $.ajax({
				url: restUrl + path,
				method: 'GET',
				dataType: 'json',
				beforeSend: function (xhr) {
					xhr.setRequestHeader('X-WP-Nonce', cfg.restNonce);
				},
			});
		}

		function restPost(path, body) {
			return $.ajax({
				url: restUrl + path,
				method: 'POST',
				contentType: 'application/json; charset=UTF-8',
				dataType: 'json',
				data: JSON.stringify(body),
				beforeSend: function (xhr) {
					xhr.setRequestHeader('X-WP-Nonce', cfg.restNonce);
				},
			});
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

		function restCollection(subtype) {
			return subtype === 'page' ? 'wp/v2/pages/' : 'wp/v2/posts/';
		}

		function titleFromPost(post) {
			if (post.title && post.title.raw) {
				return String(post.title.raw).trim();
			}
			if (post.title && post.title.rendered) {
				return stripHtml(post.title.rendered);
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

		function verdictLabel(verdict) {
			if (verdict === 'red') {
				return i18n.verdictRed || 'Needs work';
			}
			if (verdict === 'green') {
				return i18n.verdictGreen || 'Good';
			}
			return i18n.verdictOrange || 'Improvements';
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

		function setSelected(item) {
			selected = item;
			$results.attr('hidden', 'hidden').empty();
			$search.val('');
			if (!item) {
				$selected.attr('hidden', 'hidden').text('');
				$checkBtn.prop('disabled', true);
				return;
			}
			$selected.removeAttr('hidden').html(
				'<strong>' +
					escapeHtml(item.title) +
					'</strong> · ' +
					escapeHtml(item.subtype === 'page' ? i18n.page || 'Page' : i18n.post || 'Post') +
					' #' +
					escapeHtml(String(item.id))
			);
			$checkBtn.prop('disabled', false);
		}

		function renderSearchResults(items) {
			$results.empty();
			if (!items.length) {
				$results.removeAttr('hidden').html(
					'<li class="amy-agent-seo__search-empty">' +
						escapeHtml(i18n.noSearchResults || 'No published posts or pages matched.') +
						'</li>'
				);
				return;
			}
			items.forEach(function (item) {
				var li = document.createElement('li');
				var btn = document.createElement('button');
				btn.type = 'button';
				btn.className = 'amy-agent-seo__search-item';
				btn.textContent =
					(item.title || i18n.untitled || '(untitled)') +
					' · ' +
					(item.subtype === 'page' ? i18n.page || 'Page' : i18n.post || 'Post');
				$(btn).on('click', function () {
					setSelected({
						id: item.id,
						subtype: item.subtype === 'page' ? 'page' : 'post',
						title: item.title || '',
					});
				});
				li.appendChild(btn);
				$results.append(li);
			});
			$results.removeAttr('hidden');
		}

		function runSearch(query) {
			if (!query) {
				$results.attr('hidden', 'hidden').empty();
				return;
			}
			restGet(
				'wp/v2/search?search=' +
					encodeURIComponent(query) +
					'&type=post&subtype=post,page&per_page=10'
			)
				.done(function (items) {
					renderSearchResults(Array.isArray(items) ? items : []);
				})
				.fail(function () {
					showError(i18n.searchError || 'Could not search posts and pages.');
				});
		}

		function assembleSnapshot(post, media) {
			var meta = post.meta || {};
			var hasImage = !!(post.featured_media && post.featured_media > 0);
			var alt = '';
			if (hasImage && media) {
				alt = media.alt_text ? String(media.alt_text).trim() : '';
			}
			var cats = Array.isArray(post.categories) ? post.categories : [];
			return {
				wp_post_id: post.id,
				post_type: selected.subtype,
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
				category_count: cats.length,
				category_ids: cats,
			};
		}

		function fieldLabel(field) {
			var map = {
				focus_keyphrase: i18n.fieldKeyphrase || 'Focus keyphrase',
				seo_title: i18n.fieldSeoTitle || 'SEO title',
				meta_description: i18n.fieldMetaDesc || 'Meta description',
				featured_image: i18n.fieldFeatured || 'Featured image',
				featured_image_alt: i18n.fieldAlt || 'Featured image alt text',
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

		function fixFieldsForFinding(finding) {
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
				if (selected && selected.subtype === 'page') {
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
			if (field === 'meta_description') {
				return inputHtml(field, fieldLabel(field), '', true);
			}
			return inputHtml(field, fieldLabel(field), '', false);
		}

		function renderFindings(check, readonly) {
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
						html += '<div class="amy-agent-seo__fix">' + fixFieldsForFinding(finding) + '</div>';
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

		function collectApprovedFields() {
			var fields = {};
			$resultsPanel.find('.amy-agent-seo__input').each(function () {
				var name = this.name;
				var value = String($(this).val() || '').trim();
				if (name && value) {
					fields[name] = value;
				}
			});
			var ids = [];
			$resultsPanel.find('input[name="category_ids"]:checked').each(function () {
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

		function writeApprovedToWordPress(fields) {
			if (!selected) {
				return $.Deferred().resolve().promise();
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
			if (fields.category_ids && selected.subtype === 'post') {
				body.categories = fields.category_ids;
			}
			if (Object.keys(body).length) {
				writes.push(restPost(restCollection(selected.subtype) + selected.id, body));
			}
			if (fields.featured_image_alt && lastSnapshot && lastSnapshot.featured_media_id) {
				writes.push(
					restPost('wp/v2/media/' + lastSnapshot.featured_media_id, {
						alt_text: fields.featured_image_alt,
					})
				);
			}
			if (!writes.length) {
				return $.Deferred().resolve().promise();
			}
			return $.when.apply($, writes);
		}

		function renderResults(check, readonly) {
			currentCheck = check;
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
				renderFindings(check, readonly) +
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

			$resultsPanel.html(html).removeAttr('hidden');
			if (!readonly) {
				loadCategories($resultsPanel.find('[data-amy-seo-categories]'));
			}
		}

		function runCheck() {
			if (!selected) {
				return;
			}
			clearError();
			$checkBtn.prop('disabled', true).text(i18n.checking || 'Checking…');
			var path = restCollection(selected.subtype) + selected.id + '?context=edit';
			restGet(path)
				.done(function (post) {
					if (!post || post.status !== 'publish') {
						showError(i18n.notPublished || 'Please choose a published post or page.');
						$checkBtn.prop('disabled', false).text(i18n.checkSeo || 'Check SEO');
						return;
					}
					var mediaId = post.featured_media || 0;
					var continueWith = function (media) {
						lastSnapshot = assembleSnapshot(post, media);
						ajaxAction('amy_seo_check', { snapshot: JSON.stringify(lastSnapshot) })
							.done(function (res) {
								if (!res || !res.success) {
									showError(
										(res && res.data && res.data.message) ||
											i18n.checkError ||
											'Could not run the SEO check.'
									);
									return;
								}
								renderResults(res.data || {}, false);
								loadHistory();
							})
							.fail(function (xhr) {
								var msg =
									xhr.responseJSON &&
									xhr.responseJSON.data &&
									xhr.responseJSON.data.message;
								showError(msg || i18n.checkError || 'Could not run the SEO check.');
							})
							.always(function () {
								$checkBtn.prop('disabled', false).text(i18n.checkSeo || 'Check SEO');
							});
					};
					if (mediaId) {
						restGet('wp/v2/media/' + mediaId)
							.done(function (media) {
								continueWith(media);
							})
							.fail(function () {
								continueWith(null);
							});
					} else {
						continueWith(null);
					}
				})
				.fail(function () {
					showError(i18n.loadPostError || 'Could not load that post from WordPress.');
					$checkBtn.prop('disabled', false).text(i18n.checkSeo || 'Check SEO');
				});
		}

		function loadHistory() {
			$historyError.attr('hidden', 'hidden').text('');
			ajaxAction('amy_seo_checks_list', {
				status: historyStatus,
				verdict: historyVerdict,
			})
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
							escapeHtml(check.title || ('#' + check.wp_post_id)) +
							'</td>' +
							'<td>' +
							escapeHtml(check.post_type || '') +
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

		$search.on('input', function () {
			var q = String($(this).val() || '').trim();
			clearTimeout(searchTimer);
			searchTimer = setTimeout(function () {
				runSearch(q);
			}, 280);
		});

		$(document).on('click', function (e) {
			if (!$(e.target).closest('.amy-agent-seo__picker').length) {
				$results.attr('hidden', 'hidden');
			}
		});

		$checkBtn.on('click', runCheck);

		$resultsPanel.on('click', '#amy-agent-seo-approve', function () {
			if (!currentCheck) {
				return;
			}
			var $btn = $(this);
			var fields = collectApprovedFields();
			$btn.prop('disabled', true).text(i18n.saving || 'Saving…');
			writeApprovedToWordPress(fields)
				.done(function () {
					ajaxAction('amy_seo_check_approve', {
						check_id: currentCheck.check_id,
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
							renderResults(res.data || {}, true);
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
					showError(i18n.writeError || 'Could not write fields through the WordPress REST API.');
					$btn.prop('disabled', false).text(i18n.approve || 'Approve & write');
				});
		});

		$resultsPanel.on('click', '#amy-agent-seo-reject', function () {
			if (!currentCheck) {
				return;
			}
			var $btn = $(this);
			var reason = String($('#amy-agent-seo-reject-reason').val() || '').trim();
			$btn.prop('disabled', true);
			ajaxAction('amy_seo_check_reject', {
				check_id: currentCheck.check_id,
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
					renderResults(res.data || {}, true);
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
					selected = {
						id: check.wp_post_id,
						subtype: check.post_type === 'page' ? 'page' : 'post',
						title: check.title || '',
					};
					setSelected(selected);
					var readonly = check.status !== 'pending_approval';
					if (readonly) {
						lastSnapshot = null;
						renderResults(check, true);
						return;
					}
					restGet(restCollection(selected.subtype) + selected.id + '?context=edit')
						.done(function (post) {
							var mediaId = post.featured_media || 0;
							var finish = function (media) {
								lastSnapshot = assembleSnapshot(post, media);
								renderResults(check, false);
							};
							if (mediaId) {
								restGet('wp/v2/media/' + mediaId)
									.done(finish)
									.fail(function () {
										finish(null);
									});
							} else {
								finish(null);
							}
						})
						.fail(function () {
							lastSnapshot = null;
							renderResults(check, false);
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

		loadHistory();
	});
})(jQuery);
