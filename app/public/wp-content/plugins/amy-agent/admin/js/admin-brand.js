/**
 * Amy Agent — Brand & Avatar media picker.
 */
(function ($) {
	'use strict';

	$(function () {
		var cfg = window.amyAgentBrand || {};
		var $url = $('#amy_agent_avatar_url');
		var $preview = $('#amy-agent-avatar-preview');
		var frame;

		$('#amy-agent-select-avatar').on('click', function (event) {
			event.preventDefault();

			if (frame) {
				frame.open();
				return;
			}

			frame = wp.media({
				title: cfg.i18n && cfg.i18n.title ? cfg.i18n.title : 'Select Amy avatar',
				button: {
					text: cfg.i18n && cfg.i18n.button ? cfg.i18n.button : 'Use this image',
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

				$url.val(attachment.url || '');
				if (attachment.url) {
					$preview.attr('src', attachment.url);
				}
			});

			frame.open();
		});

		$('#amy-agent-reset-avatar').on('click', function (event) {
			event.preventDefault();
			$url.val('');
			if (cfg.defaultAvatarUrl) {
				$preview.attr('src', cfg.defaultAvatarUrl);
			}
		});
	});
})(jQuery);
