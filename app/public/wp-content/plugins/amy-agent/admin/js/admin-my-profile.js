/**
 * Amy Agent — My Profile page (edit modal + media picker).
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentMyProfile || {};
		var $modal = $('#amy-agent-edit-profile-modal');
		var $form = $('#amy-agent-edit-profile-form');
		var $error = $('#amy-agent-edit-profile-error');
		var $nameInput = $('#amy-agent-edit-display-name');
		var $emailInput = $('#amy-agent-edit-email');
		var $avatarUrl = $('#amy-agent-edit-avatar-url');
		var $avatarPreview = $('#amy-agent-edit-avatar-preview');
		var $saveBtn = $('#amy-agent-edit-profile-save');
		var frame;
		var gravatarUrl = cfg.gravatarUrl || '';

		function openModal() {
			$error.prop('hidden', true).text('');
			$emailInput.removeClass('is-invalid');
			$modal.prop('hidden', false);
			$nameInput.trigger('focus');
		}

		function closeModal() {
			$modal.prop('hidden', true);
		}

		function showError(message) {
			$error.text(message || (cfg.i18n && cfg.i18n.error) || 'Error').prop('hidden', false);
		}

		function isValidEmail(value) {
			return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
		}

		$('#amy-agent-edit-profile-open').on('click', function (event) {
			event.preventDefault();
			openModal();
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

		$('#amy-agent-edit-avatar-select').on('click', function (event) {
			event.preventDefault();

			if (frame) {
				frame.open();
				return;
			}

			frame = wp.media({
				title: cfg.i18n && cfg.i18n.mediaTitle ? cfg.i18n.mediaTitle : 'Select profile photo',
				button: {
					text: cfg.i18n && cfg.i18n.mediaButton ? cfg.i18n.mediaButton : 'Use this image',
				},
				library: {
					type: ['image/jpeg', 'image/png', 'image/webp'],
				},
				multiple: false,
			});

			frame.on('select', function () {
				var attachment = frame.state().get('selection').first().toJSON();
				var mime = attachment.mime || '';
				var allowed = {
					'image/jpeg': true,
					'image/png': true,
					'image/webp': true,
				};

				if (!allowed[mime]) {
					window.alert(
						cfg.i18n && cfg.i18n.invalidType
							? cfg.i18n.invalidType
							: 'Please choose a JPG, PNG, or WebP image.'
					);
					return;
				}

				$avatarUrl.val(attachment.url || '');
				if (attachment.url) {
					$avatarPreview.attr('src', attachment.url);
				}
			});

			frame.open();
		});

		$('#amy-agent-edit-avatar-reset').on('click', function (event) {
			event.preventDefault();
			$avatarUrl.val('');
			if (gravatarUrl) {
				$avatarPreview.attr('src', gravatarUrl);
			}
		});

		$form.on('submit', function (event) {
			event.preventDefault();

			var displayName = String($nameInput.val() || '').trim();
			var email = String($emailInput.val() || '').trim();

			$error.prop('hidden', true).text('');
			$emailInput.removeClass('is-invalid');

			if (!isValidEmail(email)) {
				$emailInput.addClass('is-invalid');
				showError(cfg.i18n && cfg.i18n.invalidEmail ? cfg.i18n.invalidEmail : 'Invalid email');
				$emailInput.trigger('focus');
				return;
			}

			$saveBtn.prop('disabled', true).text((cfg.i18n && cfg.i18n.saving) || 'Saving…');

			$.post(cfg.ajaxUrl, {
				action: 'amy_agent_save_my_profile',
				nonce: cfg.nonce,
				display_name: displayName,
				email: email,
				avatar_url: $avatarUrl.val() || '',
			})
				.done(function (response) {
					if (!response || !response.success || !response.data) {
						var msg =
							response && response.data && response.data.message
								? response.data.message
								: cfg.i18n && cfg.i18n.error
									? cfg.i18n.error
									: 'Error';
						if (response && response.data && response.data.message && /email/i.test(response.data.message)) {
							$emailInput.addClass('is-invalid');
						}
						showError(msg);
						return;
					}

					var data = response.data;
					$('#amy-agent-my-profile-name').text(data.displayName || '');
					$('#amy-agent-my-profile-email').text(data.email || '');
					$('#amy-agent-my-profile-joined').text(data.joined || '');
					$('#amy-agent-my-profile-role').text(data.roleLabel || '');
					if (data.avatarUrl) {
						$('#amy-agent-my-profile-avatar').attr('src', data.avatarUrl);
						$avatarPreview.attr('src', data.avatarUrl);
					}
					$('#amy-agent-my-profile-avatar').attr('alt', data.displayName || '');
					if (data.gravatarUrl) {
						gravatarUrl = data.gravatarUrl;
					}
					closeModal();
				})
				.fail(function (xhr) {
					var msg = cfg.i18n && cfg.i18n.error ? cfg.i18n.error : 'Error';
					if (xhr.responseJSON && xhr.responseJSON.data && xhr.responseJSON.data.message) {
						msg = xhr.responseJSON.data.message;
						if (/email/i.test(msg)) {
							$emailInput.addClass('is-invalid');
						}
					}
					showError(msg);
				})
				.always(function () {
					$saveBtn.prop('disabled', false).text((cfg.i18n && cfg.i18n.save) || 'Save changes');
				});
		});

		var $tgLink = $('#amy-my-profile-tg-link');
		var $tgUnlink = $('#amy-my-profile-tg-unlink');
		var $tgStatus = $('#amy-my-profile-tg-status');
		var $tgDeep = $('#amy-my-profile-tg-deep');
		var tgNonce = cfg.telegramNonce || '';

		$tgLink.on('click', function (event) {
			event.preventDefault();
			var $btn = $(this);
			$btn.prop('disabled', true).text((cfg.i18n && cfg.i18n.tgLinking) || 'Generating link…');
			$.post(cfg.ajaxUrl, {
				action: 'amy_telegram_user_link_start',
				nonce: tgNonce,
			})
				.done(function (response) {
					if (!response || !response.success || !response.data) {
						var fail =
							response && response.data && response.data.message
								? response.data.message
								: cfg.i18n && cfg.i18n.error
									? cfg.i18n.error
									: 'Error';
						if ($tgStatus.length) {
							$tgStatus.text(fail);
						}
						return;
					}
					var data = response.data;
					if ($tgDeep.length && data.deep_link) {
						$tgDeep
							.prop('hidden', false)
							.html(
								'<a href="' +
									String(data.deep_link).replace(/"/g, '&quot;') +
									'" target="_blank" rel="noopener noreferrer">' +
									((cfg.i18n && cfg.i18n.tgOpenBot) || 'Open bot & tap Start') +
									'</a>' +
									(data.code
										? ' <code>/start connect_' + String(data.code) + '</code>'
										: '')
							);
					}
					if ($tgStatus.length) {
						$tgStatus.text(data.message || '');
					}
				})
				.fail(function (xhr) {
					var msg = cfg.i18n && cfg.i18n.error ? cfg.i18n.error : 'Error';
					if (xhr.responseJSON && xhr.responseJSON.data && xhr.responseJSON.data.message) {
						msg = xhr.responseJSON.data.message;
					}
					if ($tgStatus.length) {
						$tgStatus.text(msg);
					}
				})
				.always(function () {
					$btn.prop('disabled', false).text((cfg.i18n && cfg.i18n.tgLink) || 'Connect Telegram');
				});
		});

		$tgUnlink.on('click', function (event) {
			event.preventDefault();
			var $btn = $(this);
			$btn.prop('disabled', true).text((cfg.i18n && cfg.i18n.tgUnlinking) || 'Unlinking…');
			$.post(cfg.ajaxUrl, {
				action: 'amy_telegram_user_unlink',
				nonce: tgNonce,
			})
				.done(function () {
					window.location.reload();
				})
				.fail(function (xhr) {
					var msg = cfg.i18n && cfg.i18n.error ? cfg.i18n.error : 'Error';
					if (xhr.responseJSON && xhr.responseJSON.data && xhr.responseJSON.data.message) {
						msg = xhr.responseJSON.data.message;
					}
					if ($tgStatus.length) {
						$tgStatus.text(msg);
					}
					$btn.prop('disabled', false).text((cfg.i18n && cfg.i18n.tgUnlink) || 'Unlink Telegram');
				});
		});

		var $backupSelect = $('#amy-my-profile-task-backup');
		var $backupSave = $('#amy-my-profile-backup-save');
		var $backupStatus = $('#amy-my-profile-backup-status');
		$backupSave.on('click', function (event) {
			event.preventDefault();
			var $btn = $(this);
			$btn.prop('disabled', true).text((cfg.i18n && cfg.i18n.backupSaving) || 'Saving backup…');
			$backupStatus.prop('hidden', true).text('');
			$.post(cfg.ajaxUrl, {
				action: 'amy_agent_save_task_backup',
				nonce: cfg.nonce,
				backup_wp_user_id: $backupSelect.val() || '0',
			})
				.done(function (response) {
					if (!response || !response.success) {
						var fail =
							response && response.data && response.data.message
								? response.data.message
								: (cfg.i18n && cfg.i18n.backupError) || 'Could not save backup.';
						$backupStatus.text(fail).prop('hidden', false);
						return;
					}
					$backupStatus
						.text((cfg.i18n && cfg.i18n.backupSaved) || 'Backup saved.')
						.prop('hidden', false);
				})
				.fail(function (xhr) {
					var msg = (cfg.i18n && cfg.i18n.backupError) || 'Could not save backup.';
					if (xhr.responseJSON && xhr.responseJSON.data && xhr.responseJSON.data.message) {
						msg = xhr.responseJSON.data.message;
					}
					$backupStatus.text(msg).prop('hidden', false);
				})
				.always(function () {
					$btn.prop('disabled', false).text((cfg.i18n && cfg.i18n.backupSave) || 'Save backup');
				});
		});
	});
})(jQuery);
