/**
 * Amy Agent — Submit Your Idea conversational UI (vanilla JS).
 * Unified scrolling chat tray after avatar Start; contact/thank-you stay separate steps.
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
		var step = 'avatar-landing';
		var template = null;
		var answers = {};
		var attachments = [];
		var busy = false;
		/** @type {'services'|'questions'|'summary'|'deep-dive'} */
		var chatPhase = 'services';
		var questionIndex = 0;
		var servicesBlock = null;
		var activeChoiceWrap = null;

		root.innerHTML =
			'<section class="amy-si-section is-active" data-si-step="avatar-landing">' +
			'<div id="amy-avatar-mount"></div>' +
			'</section>' +
			'<section class="amy-si-section" data-si-step="chat">' +
			'<div class="amy-si-tray">' +
			'<div class="amy-si-ticker" aria-hidden="true">' +
			'<div class="amy-si-ticker__track" data-si-ticker-track></div>' +
			'</div>' +
			'<div class="amy-si-chat" data-si-chat></div>' +
			'<form class="amy-si-composer" data-si-composer>' +
			'<button type="button" class="amy-si-attach" data-si-attach aria-label="Attach file">📎</button>' +
			'<input type="file" multiple hidden data-si-file-input' +
			' accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,image/*,application/pdf" />' +
			'<input class="amy-si-input" type="text" maxlength="4000" autocomplete="off"' +
			' data-si-composer-input placeholder="' +
			escapeHtml(cfg.i18n.deepDivePlaceholder) +
			'" />' +
			'<button class="amy-si-btn amy-si-btn--primary" type="submit" data-si-composer-send>' +
			escapeHtml(cfg.i18n.send) +
			'</button>' +
			'</form>' +
			'<div class="amy-si-files" data-si-file-chips></div>' +
			'</div>' +
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

		var chatEl = root.querySelector('[data-si-chat]');
		var tickerTrack = root.querySelector('[data-si-ticker-track]');
		var composerForm = root.querySelector('[data-si-composer]');
		var composerInput = root.querySelector('[data-si-composer-input]');
		var composerSend = root.querySelector('[data-si-composer-send]');
		var attachBtn = root.querySelector('[data-si-attach]');
		var fileInput = root.querySelector('[data-si-file-input]');
		var fileChipsEl = root.querySelector('[data-si-file-chips]');
		var contactForm = root.querySelector('[data-si-contact-form]');
		var contactError = root.querySelector('[data-si-contact-error]');

		populateTicker();
		setComposerMode('disabled');

		attachBtn.addEventListener('click', function () {
			if (busy) {
				return;
			}
			fileInput.click();
		});

		fileInput.addEventListener('change', function () {
			if (fileInput.files && fileInput.files.length) {
				uploadFiles(fileInput.files);
				fileInput.value = '';
			}
		});

		composerForm.addEventListener('submit', function (event) {
			event.preventDefault();
			var text = (composerInput.value || '').trim();
			if (!text || busy) {
				return;
			}
			if (chatPhase === 'questions') {
				composerInput.value = '';
				answerTextQuestion(text);
			} else if (chatPhase === 'deep-dive') {
				composerInput.value = '';
				sendDeepDive(text);
			}
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

		document.addEventListener('amySubmitIdea:avatarStarted', function () {
			beginChat();
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

		function setTrustCardsVisible(visible) {
			var aside = document.querySelector('.ogc-contact-layout__aside');
			if (!aside) {
				return;
			}
			aside.classList.toggle('is-visible', !!visible);
		}

		function populateTicker() {
			var sep = ' · ';
			var line = SERVICES.map(function (s) {
				return s.label;
			}).join(sep) + sep;
			tickerTrack.textContent = line + line;
		}

		function scrollChat() {
			chatEl.scrollTop = chatEl.scrollHeight;
		}

		function appendBubble(text, kind) {
			var el = document.createElement('div');
			el.className = 'amy-si-bubble amy-si-bubble--' + kind;
			if (kind === 'assistant') {
				var rendered = renderMarkdown(text);
				el.innerHTML = rendered.html;
				chatEl.appendChild(el);
				if (rendered.choices && rendered.choices.length) {
					var wrap = document.createElement('div');
					wrap.className = 'amy-si-choices';
					rendered.choices.forEach(function (c) {
						var btn = document.createElement('button');
						btn.type = 'button';
						btn.className = 'amy-si-pill';
						btn.textContent = c.label;
						btn.addEventListener('click', function () {
							if (busy || chatPhase !== 'deep-dive') {
								return;
							}
							sendDeepDive(c.label);
						});
						wrap.appendChild(btn);
					});
					chatEl.appendChild(wrap);
				}
			} else {
				el.textContent = text;
				chatEl.appendChild(el);
			}
			scrollChat();
			return el;
		}

		function appendCustomBubble(node, kind) {
			if (kind) {
				node.classList.add('amy-si-custom', 'amy-si-custom--' + kind);
			}
			chatEl.appendChild(node);
			scrollChat();
			return node;
		}

		function setComposerMode(mode) {
			var isChoice = mode === 'choice';
			var isDisabled = mode === 'disabled' || mode === 'choice';
			composerForm.classList.toggle('is-choice-mode', isChoice);
			composerInput.disabled = isDisabled || busy;
			composerInput.hidden = isChoice;
			composerSend.hidden = isChoice;
			composerSend.disabled = isDisabled || busy;
		}

		function setBusy(next) {
			busy = next;
			var senders = root.querySelectorAll(
				'[data-si-composer-send], [data-si-contact-form] button[type="submit"], .amy-si-service-pill, [data-si-summary-actions] .amy-si-pill, [data-si-q-continue]'
			);
			senders.forEach(function (el) {
				el.disabled = next;
			});
			attachBtn.disabled = next;
			if (!composerInput) {
				return;
			}
			var inputActive =
				!composerForm.classList.contains('is-choice-mode') &&
				(chatPhase === 'questions' || chatPhase === 'deep-dive');
			composerInput.disabled = next || !inputActive;
			if (composerSend && !composerForm.classList.contains('is-choice-mode')) {
				composerSend.disabled = next || !inputActive;
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

		function beginChat() {
			showStep('chat');
			chatPhase = 'services';
			chatEl.innerHTML = '';
			servicesBlock = null;
			activeChoiceWrap = null;
			appendBubble(cfg.i18n.chooseService, 'assistant');
			renderServiceCards();
			setTrustCardsVisible(true);
			setComposerMode('disabled');
		}

		function renderServiceCards() {
			var grid = document.createElement('div');
			grid.className = 'amy-si-service-grid';
			grid.setAttribute('data-si-services', '');

			SERVICES.forEach(function (svc) {
				var btn = document.createElement('button');
				btn.type = 'button';
				btn.className = 'amy-si-service-pill';
				btn.setAttribute('data-slug', svc.slug);
				btn.innerHTML =
					'<span class="amy-si-service-pill__icon" aria-hidden="true">' +
					escapeHtml(svc.icon) +
					'</span><span class="amy-si-service-pill__label">' +
					escapeHtml(svc.label) +
					'</span>';
				btn.addEventListener('click', function () {
					if (busy) {
						return;
					}
					startService(svc);
				});
				grid.appendChild(btn);
			});

			servicesBlock = appendCustomBubble(grid, 'services');
		}

		function startService(svc) {
			setTrustCardsVisible(false);
			if (servicesBlock) {
				servicesBlock.remove();
				servicesBlock = null;
			}

			setBusy(true);
			apiPost('start', { session_id: sessionId, service_slug: svc.slug })
				.then(function (result) {
					if (!result.ok || !result.data || !result.data.template) {
						window.alert(cfg.i18n.unavailable);
						renderServiceCards();
						setTrustCardsVisible(true);
						return;
					}
					template = result.data.template;
					answers = {};
					attachments = [];
					renderFileChips();
					questionIndex = 0;
					chatPhase = 'questions';
					askCurrentQuestion();
				})
				.catch(function () {
					window.alert(cfg.i18n.unavailable);
					renderServiceCards();
					setTrustCardsVisible(true);
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function currentQuestion() {
			var questions = (template && template.questions) || [];
			return questions[questionIndex] || null;
		}

		function askCurrentQuestion() {
			var q = currentQuestion();
			if (!q) {
				submitAnswers();
				return;
			}

			appendBubble(q.text, 'assistant');
			activeChoiceWrap = null;

			if (q.type === 'single_choice' || q.type === 'multi_choice') {
				setComposerMode('choice');
				renderChoicePills(q);
			} else {
				setComposerMode('text');
				composerInput.focus();
			}
		}

		function renderChoicePills(q) {
			var wrap = document.createElement('div');
			wrap.className = 'amy-si-q-choices';
			wrap.setAttribute('data-qid', q.id);

			var pills = document.createElement('div');
			pills.className = 'amy-si-pills';
			pills.setAttribute('data-si-choice-group', q.id);
			pills.setAttribute('data-si-choice-mode', q.type);

			var continueBtn = null;
			if (q.type === 'multi_choice') {
				continueBtn = document.createElement('button');
				continueBtn.type = 'button';
				continueBtn.className = 'amy-si-btn amy-si-btn--primary amy-si-q-continue';
				continueBtn.setAttribute('data-si-q-continue', '');
				continueBtn.textContent = 'Continue →';
				continueBtn.hidden = true;
				continueBtn.addEventListener('click', function () {
					if (busy) {
						return;
					}
					var selected = getActivePillValues(pills);
					if (!selected.length) {
						return;
					}
					lockChoiceWrap(wrap);
					answers[q.id] = selected;
					appendBubble(selected.join(', '), 'user');
					advanceQuestion();
				});
			}

			(q.options || []).forEach(function (opt) {
				var pill = document.createElement('button');
				pill.type = 'button';
				pill.className = 'amy-si-pill';
				pill.textContent = opt;
				pill.setAttribute('data-value', opt);
				pill.addEventListener('click', function () {
					if (busy || wrap.classList.contains('is-locked')) {
						return;
					}
					if (q.type === 'single_choice') {
						pills.querySelectorAll('.amy-si-pill').forEach(function (p) {
							p.classList.remove('is-active');
						});
						pill.classList.add('is-active');
						lockChoiceWrap(wrap);
						answers[q.id] = opt;
						appendBubble(opt, 'user');
						advanceQuestion();
					} else {
						pill.classList.toggle('is-active');
						if (continueBtn) {
							continueBtn.hidden = getActivePillValues(pills).length === 0;
						}
					}
				});
				pills.appendChild(pill);
			});

			wrap.appendChild(pills);
			if (continueBtn) {
				wrap.appendChild(continueBtn);
			}
			activeChoiceWrap = appendCustomBubble(wrap, 'choices');
		}

		function getActivePillValues(pills) {
			return Array.prototype.slice
				.call(pills.querySelectorAll('.amy-si-pill.is-active'))
				.map(function (p) {
					return p.getAttribute('data-value');
				});
		}

		function lockChoiceWrap(wrap) {
			wrap.classList.add('is-locked');
			wrap.querySelectorAll('button').forEach(function (b) {
				b.disabled = true;
			});
		}

		function answerTextQuestion(text) {
			var q = currentQuestion();
			if (!q || q.type === 'single_choice' || q.type === 'multi_choice') {
				return;
			}
			answers[q.id] = text;
			appendBubble(text, 'user');
			advanceQuestion();
		}

		function advanceQuestion() {
			questionIndex += 1;
			activeChoiceWrap = null;
			var questions = (template && template.questions) || [];
			if (questionIndex >= questions.length) {
				submitAnswers();
				return;
			}
			askCurrentQuestion();
		}

		/**
		 * Same shape as the former collectAnswers(): object keyed by question id;
		 * string for text/textarea/single_choice, array for multi_choice.
		 */
		function collectAnswers() {
			var collected = {};
			var questions = (template && template.questions) || [];
			questions.forEach(function (q) {
				if (Object.prototype.hasOwnProperty.call(answers, q.id)) {
					collected[q.id] = answers[q.id];
				} else if (q.type === 'multi_choice') {
					collected[q.id] = [];
				} else {
					collected[q.id] = '';
				}
			});
			return collected;
		}

		function submitAnswers() {
			var collected = collectAnswers();
			answers = collected;
			chatPhase = 'summary';
			setComposerMode('disabled');
			setBusy(true);

			apiPost('answers', { session_id: sessionId, answers: answers })
				.then(function (result) {
					if (!result.ok || !result.data) {
						appendBubble(cfg.i18n.unavailable, 'status');
						return;
					}
					renderSummary(result.data);
				})
				.catch(function () {
					appendBubble(cfg.i18n.unavailable, 'status');
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function renderSummary(data) {
			var text = data.summary_text || '';
			var items = data.numbered_items || [];
			if (items.length) {
				text += (text ? '\n\n' : '') + items.join('\n');
			}
			text += (text ? '\n\n' : '') + cfg.i18n.summaryPrompt;
			appendBubble(text, 'assistant');

			var actions = document.createElement('div');
			actions.className = 'amy-si-pills amy-si-summary-actions';
			actions.setAttribute('data-si-summary-actions', '');

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

			actions.appendChild(yesBtn);
			actions.appendChild(noBtn);
			appendCustomBubble(actions, 'summary');
		}

		function confirmSummary(confirmed) {
			if (busy) {
				return;
			}
			var actions = chatEl.querySelector('[data-si-summary-actions]');
			if (actions) {
				actions.querySelectorAll('button').forEach(function (b) {
					b.disabled = true;
				});
			}
			appendBubble(confirmed ? cfg.i18n.yes : cfg.i18n.no, 'user');
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
						chatPhase = 'deep-dive';
						appendBubble(result.data.message || '', 'assistant');
						setComposerMode('text');
						composerInput.focus();
					}
				})
				.catch(function () {
					window.alert(cfg.i18n.unavailable);
				})
				.finally(function () {
					setBusy(false);
				});
		}

		function sendDeepDive(text) {
			appendBubble(text, 'user');
			var thinking = appendBubble(cfg.i18n.thinking, 'status');
			setBusy(true);

			apiPost('deep-dive-message', { session_id: sessionId, message: text })
				.then(function (result) {
					thinking.remove();
					if (!result.ok || !result.data) {
						appendBubble(cfg.i18n.unavailable, 'status');
						return;
					}
					appendBubble(result.data.reply || '', 'assistant');
					if (result.data.status === 'awaiting_contact') {
						showStep('contact-form');
					}
				})
				.catch(function () {
					thinking.remove();
					appendBubble(cfg.i18n.unavailable, 'status');
				})
				.finally(function () {
					setBusy(false);
					if (step === 'chat' && chatPhase === 'deep-dive') {
						composerInput.focus();
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
			if (!fileChipsEl) {
				return;
			}
			fileChipsEl.innerHTML = '';
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
				fileChipsEl.appendChild(chip);
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
