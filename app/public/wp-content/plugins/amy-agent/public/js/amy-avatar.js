/**
 * Amy Agent — Avatar landing interaction (Submit Your Idea Phase 1).
 */
(function () {
	'use strict';

	document.addEventListener('DOMContentLoaded', function () {
		var mount = document.getElementById('amy-avatar-mount');
		if (!mount) {
			return;
		}

		var cfg = window.amySubmitIdea || {};
		var startLabel =
			(cfg.i18n && cfg.i18n.startConversation) || 'Start';

		function escapeHtml(str) {
			return String(str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');
		}

		mount.innerHTML =
			'<div class="amy-avatar-wrap">' +
			'<svg class="amy-avatar-figure" viewBox="0 0 320 380" aria-hidden="true">' +
			'<defs>' +
			'<filter id="amy-avatar-shadow-blur" x="-50%" y="-50%" width="200%" height="200%">' +
			'<feGaussianBlur in="SourceGraphic" stdDeviation="8" />' +
			'</filter>' +
			'<filter id="amy-avatar-glow" x="-50%" y="-50%" width="200%" height="200%">' +
			'<feGaussianBlur in="SourceAlpha" stdDeviation="3.5" result="blur" />' +
			'<feFlood flood-color="#ffd27a" flood-opacity="0.55" result="color" />' +
			'<feComposite in="color" in2="blur" operator="in" result="glow" />' +
			'<feMerge>' +
			'<feMergeNode in="glow" />' +
			'<feMergeNode in="SourceGraphic" />' +
			'</feMerge>' +
			'</filter>' +
			'<filter id="amy-avatar-pupil-glow" x="-80%" y="-80%" width="260%" height="260%">' +
			'<feGaussianBlur in="SourceAlpha" stdDeviation="1.6" result="blur" />' +
			'<feFlood flood-color="#ffd27a" flood-opacity="0.7" result="color" />' +
			'<feComposite in="color" in2="blur" operator="in" result="glow" />' +
			'<feMerge>' +
			'<feMergeNode in="glow" />' +
			'<feMergeNode in="SourceGraphic" />' +
			'</feMerge>' +
			'</filter>' +
			'<linearGradient id="amy-avatar-hair-grad" x1="0%" y1="0%" x2="30%" y2="100%">' +
			'<stop offset="0%" stop-color="#141414" />' +
			'<stop offset="70%" stop-color="#1a1a1a" />' +
			'<stop offset="100%" stop-color="#ffd27a" stop-opacity="0.35" />' +
			'</linearGradient>' +
			'</defs>' +
			'<ellipse id="amy-avatar-shadow" class="amy-avatar-shadow" cx="160" cy="355" rx="78" ry="14" filter="url(#amy-avatar-shadow-blur)" />' +
			'<g id="amy-avatar-tilt-group">' +
			'<ellipse class="amy-orbit-ring" cx="160" cy="155" rx="118" ry="132" />' +
			'<ellipse class="amy-orbit-ring amy-orbit-ring--reverse" cx="160" cy="155" rx="102" ry="118" />' +
			'<path d="M78 348 C95 318 120 308 160 308 C200 308 225 318 242 348 L230 362 C210 340 185 332 160 332 C135 332 110 340 90 362 Z" fill="rgba(20,20,20,0.92)" stroke="var(--amy-accent)" stroke-width="1.25" />' +
			'<rect x="142" y="248" width="36" height="68" rx="10" ry="10" fill="rgba(20,20,20,0.92)" stroke="var(--amy-accent)" stroke-width="1.25" />' +
			'<ellipse cx="160" cy="168" rx="72" ry="86" fill="rgba(20,20,20,0.96)" stroke="var(--amy-accent)" stroke-width="2" filter="url(#amy-avatar-glow)" />' +
			'<path d="M95 145 C88 95 110 55 160 48 C195 44 225 68 235 110 C238 128 232 148 222 160 C230 120 210 78 168 72 C130 68 105 95 102 130 Z" fill="url(#amy-avatar-hair-grad)" opacity="0.95" />' +
			'<path d="M88 160 C72 175 68 210 78 250 C82 268 95 285 108 295 C100 270 96 245 100 220 C104 195 98 175 95 160 Z" fill="url(#amy-avatar-hair-grad)" opacity="0.9" />' +
			'<path d="M232 155 C248 168 255 205 248 248 C244 272 232 292 218 302 C226 278 230 252 226 226 C222 200 230 172 232 155 Z" fill="url(#amy-avatar-hair-grad)" opacity="0.88" />' +
			'<path d="M118 58 C105 78 98 105 102 128 C110 90 130 68 155 62 C140 58 128 56 118 58 Z" fill="url(#amy-avatar-hair-grad)" opacity="0.85" />' +
			'<path d="M198 55 C215 70 228 100 224 135 C218 100 205 75 185 62 C190 58 194 56 198 55 Z" fill="url(#amy-avatar-hair-grad)" opacity="0.8" />' +
			'<g class="amy-avatar-eye amy-avatar-eye--left">' +
			'<circle cx="132" cy="162" r="11" fill="none" stroke="var(--amy-accent)" stroke-width="1.25" />' +
			'<circle id="amy-avatar-pupil-left" class="amy-avatar-pupil" cx="132" cy="162" r="4.5" fill="var(--amy-accent)" filter="url(#amy-avatar-pupil-glow)" />' +
			'</g>' +
			'<g class="amy-avatar-eye amy-avatar-eye--right">' +
			'<circle cx="188" cy="162" r="11" fill="none" stroke="var(--amy-accent)" stroke-width="1.25" />' +
			'<circle id="amy-avatar-pupil-right" class="amy-avatar-pupil" cx="188" cy="162" r="4.5" fill="var(--amy-accent)" filter="url(#amy-avatar-pupil-glow)" />' +
			'</g>' +
			'<path class="amy-avatar-mouth-neutral" d="M142 210 Q160 216 178 210" fill="none" stroke="var(--amy-accent)" stroke-width="2.5" stroke-linecap="round" />' +
			'<path class="amy-avatar-mouth-smile" d="M140 208 Q160 228 180 208" fill="none" stroke="var(--amy-accent)" stroke-width="2.5" stroke-linecap="round" />' +
			'</g>' +
			'</svg>' +
			'<button type="button" class="amy-avatar-start-btn" id="amy-avatar-start">' +
			escapeHtml(startLabel) +
			'</button>' +
			'</div>';

		var wrap = mount.querySelector('.amy-avatar-wrap');
		var startBtn = document.getElementById('amy-avatar-start');
		var tiltGroup = document.getElementById('amy-avatar-tilt-group');
		var shadow = document.getElementById('amy-avatar-shadow');
		var pupilLeft = document.getElementById('amy-avatar-pupil-left');
		var pupilRight = document.getElementById('amy-avatar-pupil-right');

		var started = false;
		var rafId = 0;
		var targetX = 0;
		var targetY = 0;
		var currentX = 0;
		var currentY = 0;
		var tracking = false;

		function clamp(n, min, max) {
			return Math.max(min, Math.min(max, n));
		}

		function lerp(a, b, t) {
			return a + (b - a) * t;
		}

		function onMouseMove(e) {
			targetX = e.clientX;
			targetY = e.clientY;
		}

		function tick() {
			if (!tracking) {
				return;
			}

			var rect = wrap.getBoundingClientRect();
			var cx = rect.left + rect.width / 2;
			var cy = rect.top + rect.height / 2;
			var radius = 400;

			var nx = clamp((targetX - cx) / radius, -1, 1);
			var ny = clamp((targetY - cy) / radius, -1, 1);

			/* Bias tilt toward Start when pointer is near the button. */
			var btnBiasY = 0;
			if (startBtn) {
				var br = startBtn.getBoundingClientRect();
				var pad = 40;
				var near =
					targetX >= br.left - pad &&
					targetX <= br.right + pad &&
					targetY >= br.top - pad &&
					targetY <= br.bottom + pad;
				if (near) {
					btnBiasY = 4;
				}
			}

			currentX = lerp(currentX, nx, 0.12);
			currentY = lerp(currentY, ny, 0.12);

			var rotY = clamp(currentX * 8, -8, 8);
			var rotX = clamp(currentY * -8 + btnBiasY, -8, 12);

			/* Perspective is on #amy-avatar-mount — update tilt every frame only. */
			tiltGroup.style.transform =
				'rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg)';

			if (shadow) {
				shadow.style.transform =
					'translate(' +
					currentX * -6 +
					'px, ' +
					currentY * -3 +
					'px)';
			}

			var px = clamp(currentX * 4, -4, 4);
			var py = clamp(currentY * 4, -4, 4);
			if (pupilLeft) {
				pupilLeft.style.transform =
					'translate(' + px + 'px, ' + py + 'px)';
			}
			if (pupilRight) {
				pupilRight.style.transform =
					'translate(' + px + 'px, ' + py + 'px)';
			}

			rafId = window.requestAnimationFrame(tick);
		}

		function stopTracking() {
			tracking = false;
			if (rafId) {
				window.cancelAnimationFrame(rafId);
				rafId = 0;
			}
			document.removeEventListener('mousemove', onMouseMove);
		}

		function finishLeave() {
			document.dispatchEvent(
				new CustomEvent('amySubmitIdea:avatarStarted')
			);
		}

		function onStartClick() {
			if (started) {
				return;
			}
			started = true;
			startBtn.disabled = true;
			stopTracking();

			wrap.classList.add('is-smiling');

			window.setTimeout(function () {
				wrap.classList.add('is-leaving');

				var done = false;
				function complete() {
					if (done) {
						return;
					}
					done = true;
					wrap.removeEventListener('transitionend', onTransitionEnd);
					finishLeave();
				}

				function onTransitionEnd(event) {
					if (event.propertyName === 'opacity') {
						complete();
					}
				}

				wrap.addEventListener('transitionend', onTransitionEnd);
				window.setTimeout(complete, 500);
			}, 250);
		}

		startBtn.addEventListener('click', onStartClick);

		var finePointer = window.matchMedia('(pointer: fine)').matches;
		var reduceMotion = window.matchMedia(
			'(prefers-reduced-motion: reduce)'
		).matches;

		if (finePointer && !reduceMotion) {
			tracking = true;
			document.addEventListener('mousemove', onMouseMove);
			rafId = window.requestAnimationFrame(tick);
		}
	});
})();
