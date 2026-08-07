/**
 * Amy Agent — Avatar landing interaction (Submit Your Idea Phase 1).
 * Real 3D scene (Three.js r128, already loaded site-wide by the theme
 * as `ogc-three`): a base head plane, an independently-moving eyes
 * plane, and a mouth plane that crossfades between a sad and a happy
 * texture. The whole group turns to face the pointer; the eyes get
 * extra travel on top of that. A CSS shadow beneath echoes the same
 * pointer offset.
 */
(function () {
	'use strict';

	document.addEventListener('DOMContentLoaded', function () {
		var mount = document.getElementById('amy-avatar-mount');
		if (!mount || typeof THREE === 'undefined') {
			return;
		}

		var cfg = window.amySubmitIdea || {};
		var startLabel = (cfg.i18n && cfg.i18n.startConversation) || 'Start';
		var imgBase = cfg.avatarBaseImage || '';
		var imgEyes = cfg.avatarEyesImage || '';
		var imgMouthHappy = cfg.avatarMouthHappyImage || '';
		var imgMouthSad = cfg.avatarMouthSadImage || '';

		function escapeHtml(str) {
			return String(str)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');
		}

		mount.innerHTML =
			'<div class="amy-avatar-wrap">' +
			'<div class="amy-avatar-stage">' +
			'<canvas id="amy-avatar-canvas" class="amy-avatar-canvas"></canvas>' +
			'<div id="amy-avatar-shadow" class="amy-avatar-shadow"></div>' +
			'</div>' +
			'<button type="button" class="amy-avatar-start-btn" id="amy-avatar-start">' +
			escapeHtml(startLabel) +
			'</button>' +
			'</div>';

		var wrap = mount.querySelector('.amy-avatar-wrap');
		var stage = mount.querySelector('.amy-avatar-stage');
		var canvas = document.getElementById('amy-avatar-canvas');
		var shadowEl = document.getElementById('amy-avatar-shadow');
		var startBtn = document.getElementById('amy-avatar-start');

		var finePointer = window.matchMedia('(pointer: fine)').matches;
		var reduceMotion = window.matchMedia(
			'(prefers-reduced-motion: reduce)'
		).matches;

		/* ── Three.js scene ──────────────────────────────────────── */
		var renderer = new THREE.WebGLRenderer({
			canvas: canvas,
			antialias: true,
			alpha: true,
			powerPreference: 'low-power'
		});
		renderer.setClearColor(0x000000, 0);

		var scene = new THREE.Scene();
		var camera = new THREE.PerspectiveCamera(40, 1, 0.1, 20);
		camera.position.set(0, 0, 6);

		scene.add(new THREE.AmbientLight(0x5a7090, 0.7));
		var keyLight = new THREE.DirectionalLight(0xffb000, 0.45);
		keyLight.position.set(3, 4, 5);
		scene.add(keyLight);
		var rimLight = new THREE.DirectionalLight(0xffe8b3, 0.3);
		rimLight.position.set(-3, 3, -4);
		scene.add(rimLight);

		var avatarGroup = new THREE.Group();
		scene.add(avatarGroup);

		var PLANE_SIZE = 3.2;

		function makeBaseMesh() {
			var geo = new THREE.PlaneGeometry(PLANE_SIZE, PLANE_SIZE);
			var mat = new THREE.MeshPhysicalMaterial({
				roughness: 0.32,
				metalness: 0.08,
				clearcoat: 0.4,
				clearcoatRoughness: 0.2
			});
			return new THREE.Mesh(geo, mat);
		}

		function makeOverlayMesh(z, opacity) {
			var geo = new THREE.PlaneGeometry(PLANE_SIZE, PLANE_SIZE);
			var mat = new THREE.MeshBasicMaterial({
				transparent: true,
				depthWrite: false,
				opacity: opacity
			});
			var mesh = new THREE.Mesh(geo, mat);
			mesh.position.z = z;
			return mesh;
		}

		var baseMesh = makeBaseMesh();
		avatarGroup.add(baseMesh);

		var eyesMesh = makeOverlayMesh(0.12, 1);
		avatarGroup.add(eyesMesh);

		var mouthHappyMesh = makeOverlayMesh(0.1, 0);
		avatarGroup.add(mouthHappyMesh);

		var mouthSadMesh = makeOverlayMesh(0.11, 1);
		avatarGroup.add(mouthSadMesh);

		var loader = new THREE.TextureLoader();
		loader.crossOrigin = 'anonymous';
		var texturesReady = 0;

		function onTextureLoaded() {
			texturesReady++;
			if (texturesReady === 4) {
				renderer.render(scene, camera);
			}
		}

		loader.load(imgBase, function (tex) {
			baseMesh.material.map = tex;
			baseMesh.material.needsUpdate = true;
			onTextureLoaded();
		});
		loader.load(imgEyes, function (tex) {
			eyesMesh.material.map = tex;
			eyesMesh.material.needsUpdate = true;
			onTextureLoaded();
		});
		loader.load(imgMouthHappy, function (tex) {
			mouthHappyMesh.material.map = tex;
			mouthHappyMesh.material.needsUpdate = true;
			onTextureLoaded();
		});
		loader.load(imgMouthSad, function (tex) {
			mouthSadMesh.material.map = tex;
			mouthSadMesh.material.needsUpdate = true;
			onTextureLoaded();
		});

		/* ── Pointer tracking / animation state ─────────────────── */
		var started = false;
		var rafId = 0;
		var targetX = 0;
		var targetY = 0;
		var currentX = 0;
		var currentY = 0;
		var mouthMix = 0; /* 0 = sad, 1 = happy */
		var tracking = false;

		function clamp(n, min, max) {
			return Math.max(min, Math.min(max, n));
		}

		function lerp(a, b, t) {
			return a + (b - a) * t;
		}

		function onPointerMove(e) {
			targetX = e.clientX;
			targetY = e.clientY;
		}

		function resize() {
			var w = stage.clientWidth || 240;
			var h = stage.clientHeight || 240;
			camera.aspect = w / h;
			camera.updateProjectionMatrix();
			renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
			renderer.setSize(w, h, false);
		}

		function tick() {
			if (!tracking) {
				return;
			}

			var rect = stage.getBoundingClientRect();
			var cx = rect.left + rect.width / 2;
			var cy = rect.top + rect.height / 2;
			var radius = 420;

			var nx = clamp((targetX - cx) / radius, -1, 1);
			var ny = clamp((targetY - cy) / radius, -1, 1);

			currentX = lerp(currentX, nx, 0.1);
			currentY = lerp(currentY, ny, 0.1);

			/* Head turns toward the pointer anywhere on the page. */
			avatarGroup.rotation.y = currentX * 0.32;
			avatarGroup.rotation.x = currentY * -0.26;

			/* Eyes get extra travel on top of the head turn. */
			eyesMesh.position.x = currentX * 0.22;
			eyesMesh.position.y = currentY * -0.18;

			/* Mouth crossfade: happy near the Start button, sad otherwise. */
			var desired = 0;
			if (startBtn) {
				var br = startBtn.getBoundingClientRect();
				var pad = 90;
				var near =
					targetX >= br.left - pad &&
					targetX <= br.right + pad &&
					targetY >= br.top - pad &&
					targetY <= br.bottom + pad;
				desired = near ? 1 : 0;
			}
			mouthMix = lerp(mouthMix, desired, 0.08);
			mouthHappyMesh.material.opacity = mouthMix;
			mouthSadMesh.material.opacity = 1 - mouthMix;

			/* Shadow follows the same offset, opposite direction. */
			shadowEl.style.transform =
				'translate(calc(-50% + ' +
				currentX * -14 +
				'px), ' +
				currentY * -6 +
				'px)';

			renderer.render(scene, camera);
			rafId = window.requestAnimationFrame(tick);
		}

		function stopTracking() {
			tracking = false;
			if (rafId) {
				window.cancelAnimationFrame(rafId);
				rafId = 0;
			}
			document.removeEventListener('mousemove', onPointerMove);
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

			mouthMix = 1;
			mouthHappyMesh.material.opacity = 1;
			mouthSadMesh.material.opacity = 0;
			renderer.render(scene, camera);

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

		resize();
		window.addEventListener('resize', resize, { passive: true });

		if (finePointer && !reduceMotion) {
			tracking = true;
			document.addEventListener('mousemove', onPointerMove);
			rafId = window.requestAnimationFrame(tick);
		} else {
			/* Static single frame: no pointer-follow, no crossfade. */
			renderer.render(scene, camera);
		}
	});
})();
