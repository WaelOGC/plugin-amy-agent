/**
 * Amy Agent — Submit Your Idea conversational UI (vanilla JS).
 */
(function () {
	'use strict';

	var cfg = window.amySubmitIdea;
	if (!cfg || !cfg.restBase) {
		return;
	}

	document.addEventListener('DOMContentLoaded', function () {
		var root = document.getElementById('amy-submit-idea-root');
		if (!root) {
			return;
		}

		var SERVICES = [
			{ slug: 'software-app', label: 'Software & App Development', icon: '</>' },
			{ slug: 'wordpress', label: 'Custom WordPress Development', icon: 'W' },
			{ slug: 'ui-ux', label: 'UI/UX Design', icon: '◇' },
			{ slug: 'marketing', label: 'Marketing & Strategy Consulting', icon: '◎' },
			{ slug: 'cybersecurity', label: 'Cybersecurity', icon: '⬡' },
			{ slug: 'ai-solutions', label: 'AI Solutions', icon: '✦' },
		];

		// Intentionally NOT persisted — a refresh must restart the flow.
		var sessionId = uuid();
		var step = 'service-select';
		var template = null;
		var answers = {};
		var attachments = [];
		var busy = false;

		root.innerHTML =
			'<section class="amy-si-section is-active" data-si-step="service-select">' +
			'<h2 class="amy-si-heading">' +
			escapeHtml(cfg.i18n.chooseService) +
			'</h2>' +
			'<div class="amy-si-services" data-si-services></div>' +
			'</section>' +
			'<section class="amy-si-section" data-si-step="question-form">' +
			'<h2 class="amy-si-heading" data-si-service-title></h2>' +
			'<p class="amy-si-sub" data-si-service-sub></p>' +
			'<form class="amy-si-form" data-si-form novalidate></form>' +
			'</section>' +
			'<section class="amy-si-section" data-si-step="summary-confirm">' +
			'<div class="amy-si-chat" data-si-summary-chat></div>' +
			'<div class="amy-si-actions" data-si-summary-actions></div>' +
			'</section>' +
			'<section class="amy-si-section" data-si-step="deep-dive">' +
			'<div class="amy-si-chat" data-si-deep-chat></div>' +
			'<form class="amy-si-composer" data-si-deep-form>' +
			'<input class="amy-si-input" type="text" maxlength="4000" autocomplete="off" data-si-deep-input placeholder="' +
			escapeHtml(cfg.i18n.deepDivePlaceholder) +
			'" />' +
			'<button class="amy-si-btn amy-si-btn--primary" type="submit" data-si-deep-send>' +
			escapeHtml(cfg.i18n.send) +
			'</button>' +
			'</form>' +
			'</section>' +
			'<section class="amy-si-section" data-si-step="contact-form">' +
			'<h2 class="amy-si-heading">' +
			escapeHtml(cfg.i18n.emailLabel) +
			'</h2>' +
			'<form class="amy-si-form" data-si-contact-form novalidate>' +
			'<div class="amy-si-field">' +
			'<label class="amy-si-field__label" for="amy-si-email">' +
			escapeHtml(cfg.i18n.emailLabel) +
			'</label>' +
			'<input class="amy-si-input" id="amy-si-email" type="email" name="email" required autocomplete="email" data-si-email />' +
			'</div>' +
			'<div class="amy-si-field">' +
			'<label class="amy-si-field__label" for="amy-si-whatsapp">' +
			escapeHtml(cfg.i18n.whatsappLabel) +
			'</label>' +
			'<input class="amy-si-input" id="amy-si-whatsapp" type="text" name="whatsapp" autocomplete="tel" data-si-whatsapp />' +
			'</div>' +
			'<p class="amy-si-error" data-si-contact-error hidden></p>' +
			'<div class="amy-si-actions">' +
			'<button class="amy-si-btn amy-si-btn--primary" type="submit">' +
			escapeHtml(cfg.i18n.contactSubmit) +
			'</button>' +
			'</div>' +
			'</form>' +
			'</section>' +
			'<section class="amy-si-section" data-si-step="thank-you">' +
			'<div class="amy-si-thanks">' +
			'<p class="amy-si-thanks__title">✓</p>' +
			'<p class="amy-si-thanks__body">' +
			escapeHtml(cfg.i18n.thankYou) +
			'</p>' +
			'</div>' +
			'</section>';

		var servicesEl = root.querySelector('[data-si-services]');
		var formEl = root.querySelector('[data-si-form]');
		var serviceTitleEl = root.querySelector('[data-si-service-title]');
		var summaryChat = root.querySelector('[data-si-summary-chat]');
		var summaryActions = root.querySelector('[data-si-summary-actions]');
		var deepChat = root.querySelector('[data-si-deep-chat]');
		var deepForm = root.querySelector('[data-si-deep-form]');
		var deepInput = root.querySelector('[data-si-deep-input]');
		var contactForm = root.querySelector('[data-si-contact-form]');
		var contactError = root.querySelector('[data-si-contact-error]');

		SERVICES.forEach(function (svc) {
			var btn = document.createElement('button');
			btn.type = 'button';
			btn.className = 'amy-si-service';
			btn.setAttribute('data-slug', svc.slug);
			btn.innerHTML =
				'<span class="amy-si-service__icon" aria-hidden="true">' +
				escapeHtml(svc.icon) +
				'</span><span class="amy-si-service__label">' +
				escapeHtml(svc.label) +
				'</span>';
			btn.addEventListener('click', function () {
				if (busy) {
					return;
				}
				startService(svc);
			});
			servicesEl.appendChild(btn);
		});

		deepForm.addEventListener('submit', function (event) {
			event.preventDefault();
			var text = (deepInput.value || '').trim();
			if (!text || busy) {
				return;
			}
			deepInput.value = '';
			sendDeepDive(text);
		});

		contactForm.addEventListener('submit', function (event) {
			event.preventDefault();
			if (busy) {
				return;
			}
			var email = (root.querySelector('[data-si-email]').value || '').trim();
			var whatsapp = (root.querySelector('[data-si-whatsapp]').value || '').trim();
			contactError.hidden = true;
			if (!isValidEmail(email)) {
				contactError.textContent = cfg.i18n.emailRequired;
				contactError.hidden = false;
				return;
			}
			submitContact(email, whatsapp);
		});

		function uuid() {
			if (window.crypto && typeof window.crypto.randomUUID === 'function') {
				return window.crypto.randomUUID();
			}
			return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
				var r = (Math.random() * 16) | 0;
				var v = c === 'x' ? r : (r & 0x3) | 0x8;
				return v.toString(16);
			});
		}

		function escapeHtml(str) {
			return String(str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');
		}

		/**
		 * Safe Markdown → HTML for assistant bubbles.
		 * Supports http(s) links and choice: links (rendered as pill buttons by caller).
		 */
		function renderMarkdown(text, choiceHandler) {
			var escaped = escapeHtml(String(text || ''));
			var lines = escaped.split(/\r?\n/);
			var html = [];
			var i = 0;
			var choices = [];

			function formatInline(line) {
				var out = '';
				var rest = line;
				var mdLinkRe = /\[([^\]]+)\]\(([^)\s]+)\)/;
				var boldRe = /\*\*(.+?)\*\*/;
				var urlRe = /(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"]?)/;

				while (rest.length) {
					var mdLinkMatch = rest.match(mdLinkRe);
					var boldMatch = rest.match(boldRe);
					var urlMatch = rest.match(urlRe);
					var nextIndex = rest.length;
					var kind = null;
					var match = null;

					if (mdLinkMatch && mdLinkMatch.index < nextIndex) {
						nextIndex = mdLinkMatch.index;
						kind = 'mdlink';
						match = mdLinkMatch;
					}
					if (boldMatch && boldMatch.index < nextIndex) {
						nextIndex = boldMatch.index;
						kind = 'bold';
						match = boldMatch;
					}
					if (urlMatch && urlMatch.index < nextIndex) {
						nextIndex = urlMatch.index;
						kind = 'url';
						match = urlMatch;
					}

					if (!kind) {
						out += rest;
						break;
					}

					out += rest.slice(0, nextIndex);
					if (kind === 'mdlink') {
						var href = match[2];
						var label = match[1];
						if (/^choice:/i.test(href)) {
							choices.push({ label: decodeHtml(label), value: href.replace(/^choice:/i, '') });
							// Choice pills rendered outside the bubble prose.
						} else if (/^https?:\/\//i.test(href)) {
							out +=
								'<a href="' +
								href +
								'" target="_blank" rel="noopener noreferrer">' +
								label +
								'</a>';
						} else {
							out += label;
						}
					} else if (kind === 'bold') {
						out += '<strong>' + match[1] + '</strong>';
					} else {
						var u = match[1];
						out +=
							'<a href="' +
							u +
							'" target="_blank" rel="noopener noreferrer">' +
							u +
							'</a>';
					}
					rest = rest.slice(nextIndex + match[0].length);
				}

				return out;
			}

			while (i < lines.length) {
				var line = lines[i];

				if (/^\s*$/.test(line)) {
					i += 1;
					continue;
				}

				var ulMatch = line.match(/^[\-\*]\s+(.+)$/);
				var olMatch = line.match(/^\d+\.\s+(.+)$/);

				if (ulMatch) {
					html.push('<ul>');
					while (i < lines.length) {
						var uItem = lines[i].match(/^[\-\*]\s+(.+)$/);
						if (!uItem) {
							break;
						}
						html.push('<li>' + formatInline(uItem[1]) + '</li>');
						i += 1;
					}
					html.push('</ul>');
					continue;
				}

				if (olMatch) {
					html.push('<ol>');
					while (i < lines.length) {
						var oItem = lines[i].match(/^\d+\.\s+(.+)$/);
						if (!oItem) {
							break;
						}
						html.push('<li>' + formatInline(oItem[1]) + '</li>');
						i += 1;
					}
					html.push('</ol>');
					continue;
				}

				var para = [formatInline(line)];
				i += 1;
				while (i < lines.length) {
					var next = lines[i];
					if (/^\s*$/.test(next)) {
						break;
					}
					if (/^[\-\*]\s+/.test(next) || /^\d+\.\s+/.test(next)) {
						break;
					}
					para.push(formatInline(next));
					i += 1;
				}
				html.push('<p>' + para.join('<br>') + '</p>');
			}

			var result = { html: html.join('') || '<p></p>', choices: choices };
			if (typeof choiceHandler === 'function' && choices.length) {
				choiceHandler(choices);
			}
			return result;
		}

		function decodeHtml(str) {
			var t = document.createElement('textarea');
			t.innerHTML = str;
			return t.value;
		}

		function showStep(name) {
			step = name;
			root.querySelectorAll('[data-si-step]').forEach(function (el) {
				el.classList.toggle('is-active', el.getAttribute('data-si-step') === name);
			});
		}

		function setBusy(next) {
			busy = next;
			var senders = root.querySelectorAll(
				'[data-si-form] button[type="submit"], [data-si-contact-form] button[type="submit"], [data-si-deep-send], [data-si-summary-actions] button, .amy-si-service'
			);
			senders.forEach(function (el) {
				el.disabled = next;
			});
			if (deepInput) {
				deepInput.disabled = next;
			}
		}

		function apiUrl(path) {
			return String(cfg.restBase).replace(/\/$/, '') + '/' + String(path).replace(/^\//, '');
		}

		function apiPost(path, body) {
			return fetch(apiUrl(path), {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-WP-Nonce': cfg.restNonce,
				},
				body: JSON.stringify(body),
			}).then(function (res) {
				return res.json().then(function (data) {
					return { ok: res.ok, status: res.status, data: data };
				}).catch(function () {
					return { ok: false, status: res.status, data: null };
				});
			});
		}

		function apiUpload(file) {
			var fd = new FormData();
			fd.append('session_id', sessionId);
			fd.append('file', file);
			return fetch(apiUrl('upload'), {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					Accept: 'application/json',
					'X-WP-Nonce': cfg.restNonce,
				},
				body: fd,
			}).then(function (res) {
				return res.json().then(function (data) {
					return { ok: res.ok, status: res.status, data: data };
				}).catch(function () {
					return { ok: false, status: res.status, data: null };
				});
			});
		}

		function startService(svc) {
			setBusy(true);
			apiPost('start', { session_id: sessionId, service_slug: svc.slug })
				.then(function (result) {
					if (!result.ok || !result.data || !result.data.template) {
						window.alert(cfg.i18n.unavailable);
						return;
					}
					template = result.data.template;
					answers = {};
					attachments = [];
					serviceTitleEl.textContent = template.label || svc.label;
					renderQuestionForm();
					showStep('question-form');
				})
				.catch(function () {
					window.alert(cfg.i18n.unavailable);
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function renderQuestionForm() {
			formEl.innerHTML = '';
			var questions = (template && template.questions) || [];

			questions.forEach(function (q) {
				var field = document.createElement('div');
				field.className = 'amy-si-field';
				field.setAttribute('data-qid', q.id);

				var label = document.createElement('div');
				label.className = 'amy-si-field__label';
				label.innerHTML =
					escapeHtml(q.text) +
					(q.required
						? ''
						: ' <span class="amy-si-optional">(' + escapeHtml('optional') + ')</span>');
				field.appendChild(label);

				if (q.type === 'textarea') {
					var ta = document.createElement('textarea');
					ta.className = 'amy-si-textarea';
					ta.name = q.id;
					ta.setAttribute('data-si-answer', q.id);
					if (q.required) {
						ta.required = true;
					}
					field.appendChild(ta);
				} else if (q.type === 'single_choice' || q.type === 'multi_choice') {
					var pills = document.createElement('div');
					pills.className = 'amy-si-pills';
					pills.setAttribute('data-si-choice-group', q.id);
					pills.setAttribute('data-si-choice-mode', q.type);
					(q.options || []).forEach(function (opt) {
						var pill = document.createElement('button');
						pill.type = 'button';
						pill.className = 'amy-si-pill';
						pill.textContent = opt;
						pill.setAttribute('data-value', opt);
						pill.addEventListener('click', function () {
							if (q.type === 'single_choice') {
								pills.querySelectorAll('.amy-si-pill').forEach(function (p) {
									p.classList.remove('is-active');
								});
								pill.classList.add('is-active');
							} else {
								pill.classList.toggle('is-active');
							}
						});
						pills.appendChild(pill);
					});
					field.appendChild(pills);
				} else {
					var input = document.createElement('input');
					input.className = 'amy-si-input';
					input.type = 'text';
					input.name = q.id;
					input.setAttribute('data-si-answer', q.id);
					if (q.required) {
						input.required = true;
					}
					field.appendChild(input);
				}

				formEl.appendChild(field);
			});

			// Attachments dropzone (universal optional field).
			var uploadField = document.createElement('div');
			uploadField.className = 'amy-si-field';
			uploadField.innerHTML =
				'<div class="amy-si-field__label">Attachments <span class="amy-si-optional">(optional)</span></div>';
			var drop = document.createElement('div');
			drop.className = 'amy-si-dropzone';
			drop.innerHTML =
				'<span>' +
				escapeHtml(cfg.i18n.uploadHint) +
				'</span><input type="file" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,image/*,application/pdf" data-si-file-input />';
			var fileInput = drop.querySelector('input');
			drop.addEventListener('click', function () {
				fileInput.click();
			});
			drop.addEventListener('dragover', function (e) {
				e.preventDefault();
				drop.classList.add('is-dragover');
			});
			drop.addEventListener('dragleave', function () {
				drop.classList.remove('is-dragover');
			});
			drop.addEventListener('drop', function (e) {
				e.preventDefault();
				drop.classList.remove('is-dragover');
				if (e.dataTransfer && e.dataTransfer.files) {
					uploadFiles(e.dataTransfer.files);
				}
			});
			fileInput.addEventListener('change', function () {
				if (fileInput.files && fileInput.files.length) {
					uploadFiles(fileInput.files);
					fileInput.value = '';
				}
			});
			uploadField.appendChild(drop);
			var chips = document.createElement('div');
			chips.className = 'amy-si-files';
			chips.setAttribute('data-si-file-chips');
			uploadField.appendChild(chips);
			formEl.appendChild(uploadField);

			var err = document.createElement('p');
			err.className = 'amy-si-error';
			err.setAttribute('data-si-form-error');
			err.hidden = true;
			formEl.appendChild(err);

			var actions = document.createElement('div');
			actions.className = 'amy-si-actions';
			var submitBtn = document.createElement('button');
			submitBtn.type = 'submit';
			submitBtn.className = 'amy-si-btn amy-si-btn--primary';
			submitBtn.textContent = cfg.i18n.submitAnswers;
			actions.appendChild(submitBtn);
			formEl.appendChild(actions);

			formEl.onsubmit = function (event) {
				event.preventDefault();
				submitAnswers();
			};
		}

		function collectAnswers() {
			var collected = {};
			var questions = (template && template.questions) || [];
			questions.forEach(function (q) {
				if (q.type === 'single_choice' || q.type === 'multi_choice') {
					var group = formEl.querySelector('[data-si-choice-group="' + q.id + '"]');
					var active = group
						? Array.prototype.slice.call(group.querySelectorAll('.amy-si-pill.is-active'))
						: [];
					if (q.type === 'single_choice') {
						collected[q.id] = active.length ? active[0].getAttribute('data-value') : '';
					} else {
						collected[q.id] = active.map(function (p) {
							return p.getAttribute('data-value');
						});
					}
				} else {
					var el = formEl.querySelector('[data-si-answer="' + q.id + '"]');
					collected[q.id] = el ? String(el.value || '').trim() : '';
				}
			});
			return collected;
		}

		function validateRequired(collected) {
			var questions = (template && template.questions) || [];
			for (var i = 0; i < questions.length; i++) {
				var q = questions[i];
				if (!q.required) {
					continue;
				}
				var v = collected[q.id];
				if (v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)) {
					return false;
				}
			}
			return true;
		}

		function submitAnswers() {
			var collected = collectAnswers();
			var errEl = formEl.querySelector('[data-si-form-error]');
			if (!validateRequired(collected)) {
				errEl.textContent = cfg.i18n.required;
				errEl.hidden = false;
				return;
			}
			errEl.hidden = true;
			answers = collected;
			setBusy(true);

			apiPost('answers', { session_id: sessionId, answers: answers })
				.then(function (result) {
					if (!result.ok || !result.data) {
						errEl.textContent = cfg.i18n.unavailable;
						errEl.hidden = false;
						return;
					}
					renderSummary(result.data);
					showStep('summary-confirm');
				})
				.catch(function () {
					errEl.textContent = cfg.i18n.unavailable;
					errEl.hidden = false;
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function renderSummary(data) {
			summaryChat.innerHTML = '';
			var bubble = document.createElement('div');
			bubble.className = 'amy-si-bubble amy-si-bubble--assistant';
			var text = data.summary_text || '';
			var items = data.numbered_items || [];
			if (items.length) {
				text += (text ? '\n\n' : '') + items.join('\n');
			}
			text += (text ? '\n\n' : '') + cfg.i18n.summaryPrompt;
			var rendered = renderMarkdown(text);
			bubble.innerHTML = rendered.html;
			summaryChat.appendChild(bubble);

			summaryActions.innerHTML = '';
			var yesBtn = document.createElement('button');
			yesBtn.type = 'button';
			yesBtn.className = 'amy-si-btn amy-si-btn--primary amy-si-pill';
			yesBtn.textContent = cfg.i18n.yes;
			yesBtn.addEventListener('click', function () {
				confirmSummary(true);
			});
			var noBtn = document.createElement('button');
			noBtn.type = 'button';
			noBtn.className = 'amy-si-btn amy-si-pill';
			noBtn.textContent = cfg.i18n.no;
			noBtn.addEventListener('click', function () {
				confirmSummary(false);
			});
			summaryActions.appendChild(yesBtn);
			summaryActions.appendChild(noBtn);
		}

		function confirmSummary(confirmed) {
			if (busy) {
				return;
			}
			setBusy(true);
			apiPost('confirm', { session_id: sessionId, confirmed: confirmed })
				.then(function (result) {
					if (!result.ok || !result.data) {
						window.alert(cfg.i18n.unavailable);
						return;
					}
					if (confirmed) {
						showStep('contact-form');
					} else {
						deepChat.innerHTML = '';
						appendDeepBubble(result.data.message || '', 'assistant');
						showStep('deep-dive');
						deepInput.focus();
					}
				})
				.catch(function () {
					window.alert(cfg.i18n.unavailable);
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function appendDeepBubble(text, kind) {
			var el = document.createElement('div');
			el.className = 'amy-si-bubble amy-si-bubble--' + kind;
			if (kind === 'assistant') {
				var rendered = renderMarkdown(text);
				el.innerHTML = rendered.html;
				deepChat.appendChild(el);
				if (rendered.choices && rendered.choices.length) {
					var wrap = document.createElement('div');
					wrap.className = 'amy-si-choices';
					rendered.choices.forEach(function (c) {
						var btn = document.createElement('button');
						btn.type = 'button';
						btn.className = 'amy-si-pill';
						btn.textContent = c.label;
						btn.addEventListener('click', function () {
							if (busy) {
								return;
							}
							sendDeepDive(c.label);
						});
						wrap.appendChild(btn);
					});
					deepChat.appendChild(wrap);
				}
			} else {
				el.textContent = text;
				deepChat.appendChild(el);
			}
			deepChat.scrollTop = deepChat.scrollHeight;
			return el;
		}

		function sendDeepDive(text) {
			appendDeepBubble(text, 'user');
			var thinking = appendDeepBubble(cfg.i18n.thinking, 'status');
			setBusy(true);

			apiPost('deep-dive-message', { session_id: sessionId, message: text })
				.then(function (result) {
					thinking.remove();
					if (!result.ok || !result.data) {
						appendDeepBubble(cfg.i18n.unavailable, 'status');
						return;
					}
					appendDeepBubble(result.data.reply || '', 'assistant');
					if (result.data.status === 'awaiting_contact') {
						showStep('contact-form');
					}
				})
				.catch(function () {
					thinking.remove();
					appendDeepBubble(cfg.i18n.unavailable, 'status');
				})
				.finally(function () {
					setBusy(false);
					if (step === 'deep-dive') {
						deepInput.focus();
					}
				});
		}

		function uploadFiles(fileList) {
			var files = Array.prototype.slice.call(fileList || []);
			files.forEach(function (file) {
				apiUpload(file)
					.then(function (result) {
						if (!result.ok || !result.data) {
							window.alert(cfg.i18n.uploadError);
							return;
						}
						attachments.push({
							filename: result.data.filename || file.name,
							url: result.data.url || '',
						});
						renderFileChips();
					})
					.catch(function () {
						window.alert(cfg.i18n.uploadError);
					});
			});
		}

		function renderFileChips() {
			var chips = formEl.querySelector('[data-si-file-chips]');
			if (!chips) {
				return;
			}
			chips.innerHTML = '';
			attachments.forEach(function (att, index) {
				var chip = document.createElement('span');
				chip.className = 'amy-si-file-chip';
				chip.appendChild(document.createTextNode(att.filename));
				var rm = document.createElement('button');
				rm.type = 'button';
				rm.setAttribute('aria-label', 'Remove');
				rm.textContent = '×';
				rm.addEventListener('click', function () {
					attachments.splice(index, 1);
					renderFileChips();
				});
				chip.appendChild(rm);
				chips.appendChild(chip);
			});
		}

		function isValidEmail(email) {
			return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
		}

		function submitContact(email, whatsapp) {
			setBusy(true);
			apiPost('contact', {
				session_id: sessionId,
				email: email,
				whatsapp: whatsapp || null,
			})
				.then(function (result) {
					if (!result.ok || !result.data || !result.data.brief) {
						contactError.textContent = cfg.i18n.unavailable;
						contactError.hidden = false;
						return null;
					}
					return notifyWordPress(result.data.brief).then(function () {
						showStep('thank-you');
					});
				})
				.catch(function () {
					contactError.textContent = cfg.i18n.unavailable;
					contactError.hidden = false;
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function notifyWordPress(brief) {
			var body = new FormData();
			body.append('action', 'amy_submit_idea_notify');
			body.append('nonce', cfg.ajaxNonce);
			body.append('brief', JSON.stringify(brief));

			return fetch(cfg.ajaxUrl, {
				method: 'POST',
				credentials: 'same-origin',
				body: body,
			})
				.then(function (res) {
					return res.json().catch(function () {
						return null;
					});
				})
				.catch(function () {
					// Email failure must not block the thank-you screen.
					return null;
				});
		}
	});
})();
