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
		var avatarSrc = cfg.avatarImage || '';

		function escapeHtml(str) {
			return String(str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');
		}

		mount.innerHTML =
			'<div class="amy-avatar-wrap">' +
			'<div id="amy-avatar-tilt-group" class="amy-avatar-tilt-group">' +
			'<img id="amy-avatar-image" class="amy-avatar-figure" src="' +
			escapeHtml(avatarSrc) +
			'" alt="Amy" />' +
			'</div>' +
			'<button type="button" class="amy-avatar-start-btn" id="amy-avatar-start">' +
			escapeHtml(startLabel) +
			'</button>' +
			'</div>';

		var wrap = mount.querySelector('.amy-avatar-wrap');
		var startBtn = document.getElementById('amy-avatar-start');
		var tiltGroup = document.getElementById('amy-avatar-tilt-group');

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

			tiltGroup.style.transform =
				'rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg)';

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

			wrap.classList.add('is-pulsing');

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
			}, 350);
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
