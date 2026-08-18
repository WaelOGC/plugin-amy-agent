/**
 * Amy Agent — Submit Your Idea conversational UI (vanilla JS).
 * Unified scrolling chat tray after avatar Start; contact + confirmation stay in-chat.
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

		(function renderBuildWatermark() {
			var tag = document.createElement('div');
			tag.textContent = 'AMY BUILD ' + (cfg.buildVersion || 'unknown');
			tag.style.cssText =
				'position:fixed;bottom:6px;right:6px;z-index:999999;' +
				'background:#000;color:#FFD27A;font:11px monospace;' +
				'padding:3px 6px;border-radius:4px;opacity:0.85;pointer-events:none;';
			document.body.appendChild(tag);
		})();

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
		/** @type {'services'|'questions'|'summary'|'deep-dive'|'contact'|'done'} */
		var chatPhase = 'services';
		var questionIndex = 0;
		var servicesBlock = null;
		var activeChoiceWrap = null;
		var contactForm = null;
		var contactError = null;
		var COMPOSER_MAX_HEIGHT_PX = 7.5 * 16;
		var siStarted = false;
		var siAbandoned = false;
		var siCompleted = false;

		function trackAmy(eventType, data) {
			if (typeof window.amyTrack === 'function') {
				window.amyTrack(eventType, data);
			}
		}

		function maybeAbandonSubmitIdea() {
			if (siAbandoned || siCompleted || !siStarted) {
				return;
			}
			siAbandoned = true;
			trackAmy('submit_idea_abandoned', { last_step: chatPhase || 'services' });
		}

		document.addEventListener('visibilitychange', function () {
			if (document.visibilityState === 'hidden') {
				maybeAbandonSubmitIdea();
			}
		});
		window.addEventListener('pagehide', maybeAbandonSubmitIdea);

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
			'<div class="amy-si-files" data-si-file-chips></div>' +
			'<form class="amy-si-composer" data-si-composer>' +
			'<button type="button" class="amy-si-attach" data-si-attach aria-label="Attach file">📎</button>' +
			'<input type="file" multiple hidden data-si-file-input' +
			' accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,image/*,application/pdf" />' +
			'<textarea class="amy-si-input" rows="1" maxlength="4000" autocomplete="off"' +
			' data-si-composer-input placeholder="' +
			escapeHtml(cfg.i18n.deepDivePlaceholder) +
			'"></textarea>' +
			'<button class="amy-si-btn amy-si-btn--primary" type="submit" data-si-composer-send>' +
			escapeHtml(cfg.i18n.send) +
			'</button>' +
			'</form>' +
			'</div>' +
			'</section>';

		var chatSection = root.querySelector('[data-si-step="chat"]');
		var trayEl = root.querySelector('.amy-si-tray');
		var chatEl = root.querySelector('[data-si-chat]');
		var tickerTrack = root.querySelector('[data-si-ticker-track]');
		var composerForm = root.querySelector('[data-si-composer]');
		var composerInput = root.querySelector('[data-si-composer-input]');
		var composerSend = root.querySelector('[data-si-composer-send]');
		var attachBtn = root.querySelector('[data-si-attach]');
		var fileInput = root.querySelector('[data-si-file-input]');
		var fileChipsEl = root.querySelector('[data-si-file-chips]');

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

		composerInput.addEventListener('input', function () {
			resizeComposer();
		});

		composerInput.addEventListener('keydown', function (event) {
			if (event.key === 'Enter' && !event.shiftKey) {
				event.preventDefault();
				if (typeof composerForm.requestSubmit === 'function') {
					composerForm.requestSubmit();
				} else {
					handleComposerSubmit();
				}
			}
		});

		composerForm.addEventListener('submit', function (event) {
			event.preventDefault();
			handleComposerSubmit();
		});

		document.addEventListener('amySubmitIdea:avatarStarted', function () {
			beginChat();
		});

		function handleComposerSubmit() {
			var text = (composerInput.value || '').trim();
			var staged = attachments.slice();
			if (busy) {
				return;
			}
			if (chatPhase === 'questions') {
				if (!text) {
					return;
				}
				composerInput.value = '';
				resetComposerHeight();
				answerTextQuestion(text, takeStagedAttachments());
			} else if (chatPhase === 'deep-dive') {
				if (!text && !staged.length) {
					return;
				}
				composerInput.value = '';
				resetComposerHeight();
				sendDeepDive(text, takeStagedAttachments());
			}
		}

		function takeStagedAttachments() {
			var staged = attachments.slice();
			attachments = [];
			renderFileChips();
			return staged;
		}

		function resizeComposer() {
			composerInput.style.height = 'auto';
			var scroll = composerInput.scrollHeight;
			composerInput.style.height = Math.min(scroll, COMPOSER_MAX_HEIGHT_PX) + 'px';
			composerInput.style.overflowY = scroll > COMPOSER_MAX_HEIGHT_PX ? 'auto' : 'hidden';
		}

		function resetComposerHeight() {
			composerInput.style.height = '';
			composerInput.style.overflowY = 'hidden';
		}

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

		function appendBubble(text, kind, files) {
			var el = document.createElement('div');
			el.className = 'amy-si-bubble amy-si-bubble--' + kind;

			if (kind === 'assistant' || kind === 'user') {
				var sender = document.createElement('div');
				sender.className = 'amy-si-bubble__sender';
				var name = document.createElement('span');
				name.className = 'amy-si-bubble__sender-name';
				name.textContent = kind === 'assistant' ? 'Amy' : 'You';
				var dot = document.createElement('span');
				dot.className = 'amy-si-bubble__dot';
				dot.setAttribute('aria-hidden', 'true');
				if (kind === 'assistant') {
					sender.appendChild(dot);
					sender.appendChild(name);
				} else {
					sender.appendChild(name);
					sender.appendChild(dot);
				}
				el.appendChild(sender);
			}

			if (kind === 'assistant') {
				var body = document.createElement('div');
				body.className = 'amy-si-bubble__body';
				var rendered = renderMarkdown(text);
				body.innerHTML = rendered.html;
				el.appendChild(body);
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
			} else if (kind === 'user') {
				if (text) {
					var userBody = document.createElement('div');
					userBody.className = 'amy-si-bubble__body';
					userBody.textContent = text;
					el.appendChild(userBody);
				}
				if (files && files.length) {
					el.appendChild(buildAttachmentRow(files, false));
				}
				chatEl.appendChild(el);
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
			attachBtn.disabled = next || chatPhase === 'done' || chatPhase === 'contact';
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
			if (!siStarted) {
				siStarted = true;
				trackAmy('submit_idea_started');
				trackAmy('submit_idea_step_reached', { step: 'services' });
			}
			if (trayEl) {
				trayEl.hidden = false;
				trayEl.classList.remove('is-success');
			}
			var ticker = root.querySelector('.amy-si-ticker');
			if (ticker) {
				ticker.hidden = false;
			}
			if (fileChipsEl) {
				fileChipsEl.hidden = false;
			}
			if (composerForm) {
				composerForm.hidden = false;
			}
			var priorSuccess = trayEl && trayEl.querySelector('.amy-si-success');
			if (priorSuccess) {
				priorSuccess.remove();
			}
			chatEl.innerHTML = '';
			servicesBlock = null;
			activeChoiceWrap = null;
			contactForm = null;
			contactError = null;
			attachments = [];
			renderFileChips();
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
					trackAmy('submit_idea_step_reached', { step: 'questions' });
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

		function answerTextQuestion(text, files) {
			var q = currentQuestion();
			if (!q || q.type === 'single_choice' || q.type === 'multi_choice') {
				return;
			}
			answers[q.id] = text;
			appendBubble(text, 'user', files);
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
			trackAmy('submit_idea_step_reached', { step: 'summary' });
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
						renderContactBubble();
					} else {
						chatPhase = 'deep-dive';
						trackAmy('submit_idea_step_reached', { step: 'deep-dive' });
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

		function buildWhatsappCountrySelect() {
			var countries = [
				{ code: '+93', name: 'Afghanistan', iso: 'af' },
				{ code: '+355', name: 'Albania', iso: 'al' },
				{ code: '+213', name: 'Algeria', iso: 'dz' },
				{ code: '+376', name: 'Andorra', iso: 'ad' },
				{ code: '+244', name: 'Angola', iso: 'ao' },
				{ code: '+54', name: 'Argentina', iso: 'ar' },
				{ code: '+374', name: 'Armenia', iso: 'am' },
				{ code: '+61', name: 'Australia', iso: 'au' },
				{ code: '+43', name: 'Austria', iso: 'at' },
				{ code: '+994', name: 'Azerbaijan', iso: 'az' },
				{ code: '+973', name: 'Bahrain', iso: 'bh' },
				{ code: '+880', name: 'Bangladesh', iso: 'bd' },
				{ code: '+32', name: 'Belgium', iso: 'be' },
				{ code: '+501', name: 'Belize', iso: 'bz' },
				{ code: '+229', name: 'Benin', iso: 'bj' },
				{ code: '+975', name: 'Bhutan', iso: 'bt' },
				{ code: '+591', name: 'Bolivia', iso: 'bo' },
				{ code: '+387', name: 'Bosnia & Herzegovina', iso: 'ba' },
				{ code: '+267', name: 'Botswana', iso: 'bw' },
				{ code: '+55', name: 'Brazil', iso: 'br' },
				{ code: '+673', name: 'Brunei', iso: 'bn' },
				{ code: '+359', name: 'Bulgaria', iso: 'bg' },
				{ code: '+226', name: 'Burkina Faso', iso: 'bf' },
				{ code: '+257', name: 'Burundi', iso: 'bi' },
				{ code: '+855', name: 'Cambodia', iso: 'kh' },
				{ code: '+237', name: 'Cameroon', iso: 'cm' },
				{ code: '+1', name: 'Canada', iso: 'ca' },
				{ code: '+238', name: 'Cape Verde', iso: 'cv' },
				{ code: '+236', name: 'Central African Republic', iso: 'cf' },
				{ code: '+235', name: 'Chad', iso: 'td' },
				{ code: '+56', name: 'Chile', iso: 'cl' },
				{ code: '+86', name: 'China', iso: 'cn' },
				{ code: '+57', name: 'Colombia', iso: 'co' },
				{ code: '+269', name: 'Comoros', iso: 'km' },
				{ code: '+242', name: 'Congo', iso: 'cg' },
				{ code: '+243', name: 'Congo (DRC)', iso: 'cd' },
				{ code: '+506', name: 'Costa Rica', iso: 'cr' },
				{ code: '+385', name: 'Croatia', iso: 'hr' },
				{ code: '+53', name: 'Cuba', iso: 'cu' },
				{ code: '+357', name: 'Cyprus', iso: 'cy' },
				{ code: '+420', name: 'Czechia', iso: 'cz' },
				{ code: '+45', name: 'Denmark', iso: 'dk' },
				{ code: '+253', name: 'Djibouti', iso: 'dj' },
				{ code: '+1', name: 'Dominican Republic', iso: 'do' },
				{ code: '+593', name: 'Ecuador', iso: 'ec' },
				{ code: '+20', name: 'Egypt', iso: 'eg' },
				{ code: '+503', name: 'El Salvador', iso: 'sv' },
				{ code: '+372', name: 'Estonia', iso: 'ee' },
				{ code: '+268', name: 'Eswatini', iso: 'sz' },
				{ code: '+251', name: 'Ethiopia', iso: 'et' },
				{ code: '+679', name: 'Fiji', iso: 'fj' },
				{ code: '+358', name: 'Finland', iso: 'fi' },
				{ code: '+33', name: 'France', iso: 'fr' },
				{ code: '+241', name: 'Gabon', iso: 'ga' },
				{ code: '+220', name: 'Gambia', iso: 'gm' },
				{ code: '+995', name: 'Georgia', iso: 'ge' },
				{ code: '+49', name: 'Germany', iso: 'de' },
				{ code: '+233', name: 'Ghana', iso: 'gh' },
				{ code: '+30', name: 'Greece', iso: 'gr' },
				{ code: '+502', name: 'Guatemala', iso: 'gt' },
				{ code: '+224', name: 'Guinea', iso: 'gn' },
				{ code: '+592', name: 'Guyana', iso: 'gy' },
				{ code: '+509', name: 'Haiti', iso: 'ht' },
				{ code: '+504', name: 'Honduras', iso: 'hn' },
				{ code: '+852', name: 'Hong Kong', iso: 'hk' },
				{ code: '+36', name: 'Hungary', iso: 'hu' },
				{ code: '+354', name: 'Iceland', iso: 'is' },
				{ code: '+91', name: 'India', iso: 'in' },
				{ code: '+62', name: 'Indonesia', iso: 'id' },
				{ code: '+98', name: 'Iran', iso: 'ir' },
				{ code: '+964', name: 'Iraq', iso: 'iq' },
				{ code: '+353', name: 'Ireland', iso: 'ie' },
				{ code: '+972', name: 'Israel', iso: 'il' },
				{ code: '+39', name: 'Italy', iso: 'it' },
				{ code: '+225', name: 'Ivory Coast', iso: 'ci' },
				{ code: '+1', name: 'Jamaica', iso: 'jm' },
				{ code: '+81', name: 'Japan', iso: 'jp' },
				{ code: '+962', name: 'Jordan', iso: 'jo' },
				{ code: '+7', name: 'Kazakhstan', iso: 'kz' },
				{ code: '+254', name: 'Kenya', iso: 'ke' },
				{ code: '+965', name: 'Kuwait', iso: 'kw' },
				{ code: '+996', name: 'Kyrgyzstan', iso: 'kg' },
				{ code: '+856', name: 'Laos', iso: 'la' },
				{ code: '+371', name: 'Latvia', iso: 'lv' },
				{ code: '+961', name: 'Lebanon', iso: 'lb' },
				{ code: '+231', name: 'Liberia', iso: 'lr' },
				{ code: '+218', name: 'Libya', iso: 'ly' },
				{ code: '+423', name: 'Liechtenstein', iso: 'li' },
				{ code: '+370', name: 'Lithuania', iso: 'lt' },
				{ code: '+352', name: 'Luxembourg', iso: 'lu' },
				{ code: '+853', name: 'Macau', iso: 'mo' },
				{ code: '+261', name: 'Madagascar', iso: 'mg' },
				{ code: '+265', name: 'Malawi', iso: 'mw' },
				{ code: '+60', name: 'Malaysia', iso: 'my' },
				{ code: '+960', name: 'Maldives', iso: 'mv' },
				{ code: '+223', name: 'Mali', iso: 'ml' },
				{ code: '+356', name: 'Malta', iso: 'mt' },
				{ code: '+222', name: 'Mauritania', iso: 'mr' },
				{ code: '+230', name: 'Mauritius', iso: 'mu' },
				{ code: '+52', name: 'Mexico', iso: 'mx' },
				{ code: '+373', name: 'Moldova', iso: 'md' },
				{ code: '+377', name: 'Monaco', iso: 'mc' },
				{ code: '+976', name: 'Mongolia', iso: 'mn' },
				{ code: '+382', name: 'Montenegro', iso: 'me' },
				{ code: '+212', name: 'Morocco', iso: 'ma' },
				{ code: '+258', name: 'Mozambique', iso: 'mz' },
				{ code: '+95', name: 'Myanmar', iso: 'mm' },
				{ code: '+264', name: 'Namibia', iso: 'na' },
				{ code: '+977', name: 'Nepal', iso: 'np' },
				{ code: '+31', name: 'Netherlands', iso: 'nl' },
				{ code: '+64', name: 'New Zealand', iso: 'nz' },
				{ code: '+505', name: 'Nicaragua', iso: 'ni' },
				{ code: '+227', name: 'Niger', iso: 'ne' },
				{ code: '+234', name: 'Nigeria', iso: 'ng' },
				{ code: '+389', name: 'North Macedonia', iso: 'mk' },
				{ code: '+47', name: 'Norway', iso: 'no' },
				{ code: '+968', name: 'Oman', iso: 'om' },
				{ code: '+92', name: 'Pakistan', iso: 'pk' },
				{ code: '+970', name: 'Palestine', iso: 'ps' },
				{ code: '+507', name: 'Panama', iso: 'pa' },
				{ code: '+675', name: 'Papua New Guinea', iso: 'pg' },
				{ code: '+595', name: 'Paraguay', iso: 'py' },
				{ code: '+51', name: 'Peru', iso: 'pe' },
				{ code: '+63', name: 'Philippines', iso: 'ph' },
				{ code: '+48', name: 'Poland', iso: 'pl' },
				{ code: '+351', name: 'Portugal', iso: 'pt' },
				{ code: '+974', name: 'Qatar', iso: 'qa' },
				{ code: '+40', name: 'Romania', iso: 'ro' },
				{ code: '+7', name: 'Russia', iso: 'ru' },
				{ code: '+250', name: 'Rwanda', iso: 'rw' },
				{ code: '+966', name: 'Saudi Arabia', iso: 'sa' },
				{ code: '+221', name: 'Senegal', iso: 'sn' },
				{ code: '+381', name: 'Serbia', iso: 'rs' },
				{ code: '+248', name: 'Seychelles', iso: 'sc' },
				{ code: '+232', name: 'Sierra Leone', iso: 'sl' },
				{ code: '+65', name: 'Singapore', iso: 'sg' },
				{ code: '+421', name: 'Slovakia', iso: 'sk' },
				{ code: '+386', name: 'Slovenia', iso: 'si' },
				{ code: '+27', name: 'South Africa', iso: 'za' },
				{ code: '+82', name: 'South Korea', iso: 'kr' },
				{ code: '+34', name: 'Spain', iso: 'es' },
				{ code: '+94', name: 'Sri Lanka', iso: 'lk' },
				{ code: '+249', name: 'Sudan', iso: 'sd' },
				{ code: '+597', name: 'Suriname', iso: 'sr' },
				{ code: '+46', name: 'Sweden', iso: 'se' },
				{ code: '+41', name: 'Switzerland', iso: 'ch' },
				{ code: '+963', name: 'Syria', iso: 'sy' },
				{ code: '+886', name: 'Taiwan', iso: 'tw' },
				{ code: '+992', name: 'Tajikistan', iso: 'tj' },
				{ code: '+255', name: 'Tanzania', iso: 'tz' },
				{ code: '+66', name: 'Thailand', iso: 'th' },
				{ code: '+228', name: 'Togo', iso: 'tg' },
				{ code: '+216', name: 'Tunisia', iso: 'tn' },
				{ code: '+90', name: 'Turkey', iso: 'tr' },
				{ code: '+993', name: 'Turkmenistan', iso: 'tm' },
				{ code: '+256', name: 'Uganda', iso: 'ug' },
				{ code: '+380', name: 'Ukraine', iso: 'ua' },
				{ code: '+971', name: 'United Arab Emirates', iso: 'ae' },
				{ code: '+44', name: 'United Kingdom', iso: 'gb' },
				{ code: '+1', name: 'United States', iso: 'us' },
				{ code: '+598', name: 'Uruguay', iso: 'uy' },
				{ code: '+998', name: 'Uzbekistan', iso: 'uz' },
				{ code: '+58', name: 'Venezuela', iso: 've' },
				{ code: '+84', name: 'Vietnam', iso: 'vn' },
				{ code: '+967', name: 'Yemen', iso: 'ye' },
				{ code: '+260', name: 'Zambia', iso: 'zm' },
				{ code: '+263', name: 'Zimbabwe', iso: 'zw' },
			];

			var wrap = document.createElement('div');
			wrap.className = 'amy-si-country-dd';
			wrap.setAttribute('data-si-whatsapp-country-wrap', '');

			var hidden = document.createElement('input');
			hidden.type = 'hidden';
			hidden.setAttribute('data-si-whatsapp-country', '');
			hidden.value = '+31';

			var btn = document.createElement('button');
			btn.type = 'button';
			btn.className = 'amy-si-country-dd__btn';
			btn.setAttribute('aria-haspopup', 'listbox');
			btn.setAttribute('aria-expanded', 'false');
			btn.setAttribute('aria-label', 'Country code');

			var list = document.createElement('ul');
			list.className = 'amy-si-country-dd__list';
			list.setAttribute('role', 'listbox');
			list.hidden = true;

			var activeIndex = -1;
			countries.forEach(function (c, idx) {
				if (c.code === '+31' && c.name === 'Netherlands') {
					activeIndex = idx;
				}
			});
			if (activeIndex < 0) {
				activeIndex = 0;
			}

			function flagHtml(iso) {
				return (
					'<img class="amy-si-flag" src="https://flagcdn.com/' +
					String(iso).toLowerCase() +
					'.svg" width="20" height="15" alt="" loading="lazy" decoding="async" />'
				);
			}

			function renderButton(c) {
				btn.innerHTML =
					flagHtml(c.iso) +
					'<span class="amy-si-country-dd__code">' +
					escapeHtml(c.code) +
					'</span>' +
					'<span class="amy-si-country-dd__chevron" aria-hidden="true"></span>';
				hidden.value = c.code;
			}

			function setOpen(open) {
				list.hidden = !open;
				btn.setAttribute('aria-expanded', open ? 'true' : 'false');
				wrap.classList.toggle('is-open', open);
				if (open) {
					var selected = list.querySelector('[aria-selected="true"]');
					if (selected) {
						selected.scrollIntoView({ block: 'nearest' });
					}
				}
			}

			function selectIndex(idx) {
				if (idx < 0 || idx >= countries.length) {
					return;
				}
				activeIndex = idx;
				var options = list.querySelectorAll('[role="option"]');
				options.forEach(function (opt, i) {
					opt.setAttribute('aria-selected', i === idx ? 'true' : 'false');
					opt.classList.toggle('is-active', i === idx);
				});
				renderButton(countries[idx]);
				setOpen(false);
				btn.focus();
			}

			countries.forEach(function (c, idx) {
				var li = document.createElement('li');
				li.className = 'amy-si-country-dd__option';
				li.setAttribute('role', 'option');
				li.setAttribute('data-index', String(idx));
				li.setAttribute('aria-selected', idx === activeIndex ? 'true' : 'false');
				if (idx === activeIndex) {
					li.classList.add('is-active');
				}
				li.innerHTML =
					flagHtml(c.iso) +
					'<span class="amy-si-country-dd__label">' +
					escapeHtml(c.name) +
					'</span>' +
					'<span class="amy-si-country-dd__dial">' +
					escapeHtml(c.code) +
					'</span>';
				li.addEventListener('click', function (event) {
					event.preventDefault();
					event.stopPropagation();
					selectIndex(idx);
				});
				list.appendChild(li);
			});

			renderButton(countries[activeIndex]);

			btn.addEventListener('click', function (event) {
				event.preventDefault();
				event.stopPropagation();
				setOpen(list.hidden);
			});

			btn.addEventListener('keydown', function (event) {
				if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
					event.preventDefault();
					if (list.hidden) {
						setOpen(true);
						return;
					}
					var next =
						event.key === 'ArrowDown'
							? Math.min(activeIndex + 1, countries.length - 1)
							: Math.max(activeIndex - 1, 0);
					activeIndex = next;
					var options = list.querySelectorAll('[role="option"]');
					options.forEach(function (opt, i) {
						opt.classList.toggle('is-active', i === next);
						opt.setAttribute('aria-selected', i === next ? 'true' : 'false');
					});
					if (options[next]) {
						options[next].scrollIntoView({ block: 'nearest' });
					}
				} else if (event.key === 'Enter' || event.key === ' ') {
					event.preventDefault();
					if (list.hidden) {
						setOpen(true);
					} else {
						selectIndex(activeIndex);
					}
				} else if (event.key === 'Escape') {
					if (!list.hidden) {
						event.preventDefault();
						setOpen(false);
					}
				} else if (event.key === 'Home' && !list.hidden) {
					event.preventDefault();
					selectIndex(0);
					setOpen(true);
				} else if (event.key === 'End' && !list.hidden) {
					event.preventDefault();
					selectIndex(countries.length - 1);
					setOpen(true);
				}
			});

			document.addEventListener('click', function (event) {
				if (!wrap.contains(event.target)) {
					setOpen(false);
				}
			});

			wrap.appendChild(hidden);
			wrap.appendChild(btn);
			wrap.appendChild(list);
			return wrap;
		}

		function assembleWhatsapp(form) {
			var phone = (form.querySelector('[data-si-whatsapp]').value || '').trim();
			if (!phone) {
				return '';
			}
			if (phone.charAt(0) === '+') {
				return phone;
			}
			var dialEl = form.querySelector('[data-si-whatsapp-country]');
			var dial = dialEl ? String(dialEl.value || '').trim() : '';
			return dial ? dial + ' ' + phone : phone;
		}

		function renderContactBubble() {
			chatPhase = 'contact';
			trackAmy('submit_idea_step_reached', { step: 'contact' });
			setComposerMode('disabled');

			var form = document.createElement('form');
			form.className = 'amy-si-form amy-si-contact-bubble';
			form.setAttribute('data-si-contact-form', '');
			form.setAttribute('novalidate', '');

			var emailField = document.createElement('div');
			emailField.className = 'amy-si-field';
			emailField.innerHTML =
				'<label class="amy-si-field__label" for="amy-si-email">' +
				escapeHtml(cfg.i18n.emailLabel) +
				'</label>' +
				'<input class="amy-si-input" id="amy-si-email" type="email" name="email" required autocomplete="email" data-si-email />';

			var waField = document.createElement('div');
			waField.className = 'amy-si-field';
			var waLabel = document.createElement('label');
			waLabel.className = 'amy-si-field__label';
			waLabel.setAttribute('for', 'amy-si-whatsapp');
			waLabel.textContent = cfg.i18n.whatsappLabel;
			var waRow = document.createElement('div');
			waRow.className = 'amy-si-phone-row';
			waRow.appendChild(buildWhatsappCountrySelect());
			var waInput = document.createElement('input');
			waInput.className = 'amy-si-input';
			waInput.id = 'amy-si-whatsapp';
			waInput.type = 'text';
			waInput.name = 'whatsapp';
			waInput.setAttribute('autocomplete', 'tel');
			waInput.setAttribute('data-si-whatsapp', '');
			waRow.appendChild(waInput);
			waField.appendChild(waLabel);
			waField.appendChild(waRow);

			var err = document.createElement('p');
			err.className = 'amy-si-error';
			err.setAttribute('data-si-contact-error', '');
			err.hidden = true;

			var actions = document.createElement('div');
			actions.className = 'amy-si-actions';
			var submitBtn = document.createElement('button');
			submitBtn.className = 'amy-si-btn amy-si-btn--primary';
			submitBtn.type = 'submit';
			submitBtn.textContent = cfg.i18n.contactSubmit;
			actions.appendChild(submitBtn);

			form.appendChild(emailField);
			form.appendChild(waField);
			form.appendChild(err);
			form.appendChild(actions);

			contactForm = form;
			contactError = err;

			form.addEventListener('submit', function (event) {
				event.preventDefault();
				if (busy) {
					return;
				}
				var email = (form.querySelector('[data-si-email]').value || '').trim();
				var whatsapp = assembleWhatsapp(form);
				contactError.hidden = true;
				if (!isValidEmail(email)) {
					contactError.textContent = cfg.i18n.emailRequired;
					contactError.hidden = false;
					return;
				}
				submitContact(email, whatsapp);
			});

			appendCustomBubble(form, 'contact');
			var emailInput = form.querySelector('[data-si-email]');
			if (emailInput) {
				emailInput.focus();
			}
		}

		function showConfirmation() {
			chatPhase = 'done';
			siCompleted = true;
			setComposerMode('disabled');
			attachBtn.disabled = true;
			contactForm = null;
			contactError = null;
			attachments = [];
			renderFileChips();

			chatEl.innerHTML = '';

			var ticker = root.querySelector('.amy-si-ticker');
			if (ticker) {
				ticker.hidden = true;
			}
			if (fileChipsEl) {
				fileChipsEl.hidden = true;
			}
			if (composerForm) {
				composerForm.hidden = true;
			}

			if (trayEl) {
				trayEl.classList.add('is-success');
				var existing = trayEl.querySelector('.amy-si-success');
				if (existing) {
					existing.remove();
				}
				var card = document.createElement('div');
				card.className = 'amy-si-success';
				card.innerHTML =
					'<div class="amy-si-success__badge" aria-hidden="true">🎉</div>' +
					'<p class="amy-si-success__text">' +
					escapeHtml(cfg.i18n.thankYouChat || cfg.i18n.thankYou) +
					'</p>';
				trayEl.appendChild(card);
			}
		}

		function sendDeepDive(text, files) {
			files = files || [];
			var apiText = (text || '').trim();
			if (!apiText && files.length) {
				apiText = files
					.map(function (f) {
						return f.filename;
					})
					.join(', ');
			}
			appendBubble(text || '', 'user', files);
			var thinking = appendBubble(cfg.i18n.thinking, 'status');
			setBusy(true);

			apiPost('deep-dive-message', { session_id: sessionId, message: apiText })
				.then(function (result) {
					thinking.remove();
					if (!result.ok || !result.data) {
						appendBubble(cfg.i18n.unavailable, 'status');
						return;
					}
					appendBubble(result.data.reply || '', 'assistant');
					if (result.data.status === 'awaiting_contact') {
						renderContactBubble();
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

		function isImageAttachment(att) {
			if (att.isImage) {
				return true;
			}
			return /\.(jpe?g|png|gif|webp)$/i.test(att.filename || '');
		}

		function formatFileSize(bytes) {
			var n = Number(bytes);
			if (!isFinite(n) || n < 0) {
				return '';
			}
			if (n < 1024) {
				return Math.round(n) + ' B';
			}
			if (n < 1024 * 1024) {
				return (n / 1024).toFixed(n < 10 * 1024 ? 1 : 0) + ' KB';
			}
			return (n / (1024 * 1024)).toFixed(1) + ' MB';
		}

		function fileTypeIconSvg() {
			return (
				'<svg class="amy-si-file-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
				'<path fill="currentColor" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm1 7V3.5L19.5 9H15z"/>' +
				'</svg>'
			);
		}

		function buildAttachmentRow(fileList, removable) {
			var row = document.createElement('div');
			row.className = 'amy-si-bubble-files' + (removable ? ' amy-si-bubble-files--staged' : '');
			fileList.forEach(function (att, index) {
				row.appendChild(buildFileChip(att, removable ? index : -1));
			});
			return row;
		}

		function buildFileChip(att, removeIndex) {
			var chip = document.createElement('span');
			var isImage = isImageAttachment(att);
			chip.className =
				'amy-si-file-chip' +
				(isImage ? ' amy-si-file-chip--image' : '') +
				(removeIndex < 0 ? ' amy-si-file-chip--sent' : '');

			if (isImage) {
				var thumb = document.createElement('img');
				thumb.className = 'amy-si-file-thumb' + (removeIndex < 0 ? ' amy-si-file-thumb--sent' : '');
				thumb.alt = att.filename || '';
				thumb.src = att.previewUrl || att.url || '';
				chip.appendChild(thumb);
				if (removeIndex >= 0) {
					var name = document.createElement('span');
					name.className = 'amy-si-file-chip__name';
					name.textContent = att.filename || 'image';
					chip.appendChild(name);
				}
			} else {
				var iconWrap = document.createElement('span');
				iconWrap.className = 'amy-si-file-chip__icon';
				iconWrap.innerHTML = fileTypeIconSvg();
				chip.appendChild(iconWrap);
				var meta = document.createElement('span');
				meta.className = 'amy-si-file-chip__meta';
				var nameEl = document.createElement('span');
				nameEl.className = 'amy-si-file-chip__name';
				nameEl.textContent = att.filename || 'file';
				meta.appendChild(nameEl);
				if (removeIndex >= 0 && att.size) {
					var sizeEl = document.createElement('span');
					sizeEl.className = 'amy-si-file-chip__size';
					sizeEl.textContent = formatFileSize(att.size);
					meta.appendChild(sizeEl);
				}
				chip.appendChild(meta);
			}

			if (removeIndex >= 0) {
				var rm = document.createElement('button');
				rm.type = 'button';
				rm.className = 'amy-si-file-chip__remove';
				rm.setAttribute('aria-label', 'Remove');
				rm.textContent = '✕';
				rm.addEventListener('click', function () {
					var removed = attachments.splice(removeIndex, 1)[0];
					if (removed && removed.previewUrl) {
						try {
							URL.revokeObjectURL(removed.previewUrl);
						} catch (e) {
							/* ignore */
						}
					}
					renderFileChips();
				});
				chip.appendChild(rm);
			}

			return chip;
		}

		function uploadFiles(fileList) {
			var files = Array.prototype.slice.call(fileList || []);
			files.forEach(function (file) {
				var previewUrl = '';
				var isImage = /^image\//i.test(file.type) || /\.(jpe?g|png|gif|webp)$/i.test(file.name);
				if (isImage) {
					try {
						previewUrl = URL.createObjectURL(file);
					} catch (e) {
						previewUrl = '';
					}
				}
				apiUpload(file)
					.then(function (result) {
						if (!result.ok || !result.data) {
							if (previewUrl) {
								try {
									URL.revokeObjectURL(previewUrl);
								} catch (e2) {
									/* ignore */
								}
							}
							window.alert(cfg.i18n.uploadError);
							return;
						}
						attachments.push({
							filename: result.data.filename || file.name,
							url: result.data.url || '',
							size: file.size || 0,
							isImage: isImage,
							previewUrl: previewUrl,
						});
						renderFileChips();
					})
					.catch(function () {
						if (previewUrl) {
							try {
								URL.revokeObjectURL(previewUrl);
							} catch (e3) {
								/* ignore */
							}
						}
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
				fileChipsEl.appendChild(buildFileChip(att, index));
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
						if (contactError) {
							contactError.textContent = cfg.i18n.unavailable;
							contactError.hidden = false;
						}
						return null;
					}
					return notifyWordPress(result.data.brief).then(function () {
						trackAmy('submit_idea_completed', { email: email });
						showConfirmation();
					});
				})
				.catch(function () {
					if (contactError) {
						contactError.textContent = cfg.i18n.unavailable;
						contactError.hidden = false;
					}
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
