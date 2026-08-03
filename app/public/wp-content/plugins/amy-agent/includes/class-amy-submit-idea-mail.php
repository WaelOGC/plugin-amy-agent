<?php
/**
 * Submit Your Idea — email notifications via admin-ajax.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Sends admin + client confirmation emails after a finalized brief.
 */
class Amy_Submit_Idea_Mail {

	/**
	 * Register AJAX actions (logged-in and anonymous).
	 */
	public function register() {
		add_action( 'wp_ajax_amy_submit_idea_notify', array( $this, 'handle_notify' ) );
		add_action( 'wp_ajax_nopriv_amy_submit_idea_notify', array( $this, 'handle_notify' ) );
	}

	/**
	 * AJAX: accept finalized brief JSON and send two emails.
	 */
	public function handle_notify() {
		$nonce = isset( $_REQUEST['nonce'] ) ? sanitize_text_field( wp_unslash( $_REQUEST['nonce'] ) ) : '';
		if ( ! $nonce || ! wp_verify_nonce( $nonce, 'amy_submit_idea_notify' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Invalid security token.', 'amy-agent' ) ),
				403
			);
		}

		$raw = isset( $_POST['brief'] ) ? wp_unslash( $_POST['brief'] ) : '';
		if ( is_array( $raw ) ) {
			$brief = $raw;
		} else {
			$brief = json_decode( (string) $raw, true );
		}

		if ( ! is_array( $brief ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Invalid brief payload.', 'amy-agent' ) ),
				400
			);
		}

		$service_label = isset( $brief['service_label'] ) ? sanitize_text_field( (string) $brief['service_label'] ) : '';
		$contact       = isset( $brief['contact'] ) && is_array( $brief['contact'] ) ? $brief['contact'] : array();
		$client_email  = isset( $contact['email'] ) ? sanitize_email( (string) $contact['email'] ) : '';

		if ( ! $client_email || ! is_email( $client_email ) ) {
			wp_send_json_error(
				array( 'message' => __( 'A valid client email is required.', 'amy-agent' ) ),
				400
			);
		}

		$admin_email = (string) get_option( 'admin_email' );
		$admin_ok    = $this->send_admin_email( $admin_email, $service_label, $brief );
		$client_ok   = $this->send_client_email( $client_email, $service_label );

		if ( ! $admin_ok ) {
			wp_send_json_error(
				array( 'message' => __( 'Could not notify the team. Please try again.', 'amy-agent' ) ),
				500
			);
		}

		if ( ! $client_ok ) {
			// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
			error_log( '[amy-agent] Submit Idea client confirmation email failed for ' . $client_email );
		}

		wp_send_json_success(
			array(
				'admin_sent'  => true,
				'client_sent' => (bool) $client_ok,
			)
		);
	}

	/**
	 * @param string $to            Admin address.
	 * @param string $service_label Service display name.
	 * @param array  $brief         Finalized brief.
	 * @return bool
	 */
	private function send_admin_email( $to, $service_label, array $brief ) {
		$subject = sprintf(
			/* translators: %s: service label */
			__( 'New Project Idea Submitted — %s', 'amy-agent' ),
			$service_label ? $service_label : __( 'Project', 'amy-agent' )
		);

		$body = $this->build_admin_body( $brief, $service_label );

		add_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );
		$sent = wp_mail( $to, $subject, $body );
		remove_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );

		return (bool) $sent;
	}

	/**
	 * @param string $to            Client address.
	 * @param string $service_label Service display name.
	 * @return bool
	 */
	private function send_client_email( $to, $service_label ) {
		$subject = __( "We've received your project idea — OGC NewFinity", 'amy-agent' );
		$body    = $this->build_client_body( $service_label );

		add_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );
		$sent = wp_mail( $to, $subject, $body );
		remove_filter( 'wp_mail_content_type', array( $this, 'html_content_type' ) );

		return (bool) $sent;
	}

	/**
	 * @return string
	 */
	public function html_content_type() {
		return 'text/html';
	}

	/**
	 * @param array  $brief         Brief payload.
	 * @param string $service_label Label.
	 * @return string
	 */
	private function build_admin_body( array $brief, $service_label ) {
		$slug       = isset( $brief['service_slug'] ) ? sanitize_text_field( (string) $brief['service_slug'] ) : '';
		$answers    = isset( $brief['answers'] ) && is_array( $brief['answers'] ) ? $brief['answers'] : array();
		$deep       = isset( $brief['free_conversation_summary'] ) ? (string) $brief['free_conversation_summary'] : '';
		$contact    = isset( $brief['contact'] ) && is_array( $brief['contact'] ) ? $brief['contact'] : array();
		$attachments = isset( $brief['attachments'] ) && is_array( $brief['attachments'] ) ? $brief['attachments'] : array();

		$email    = isset( $contact['email'] ) ? sanitize_email( (string) $contact['email'] ) : '';
		$whatsapp = isset( $contact['whatsapp'] ) ? sanitize_text_field( (string) $contact['whatsapp'] ) : '';

		$rows = '';
		foreach ( $answers as $key => $value ) {
			$label = esc_html( (string) $key );
			if ( is_array( $value ) ) {
				$display = esc_html( implode( ', ', array_map( 'strval', $value ) ) );
			} else {
				$display = nl2br( esc_html( (string) $value ) );
			}
			$rows .= '<tr><td style="padding:8px 12px;border-bottom:1px solid #333;color:#ffd27a;vertical-align:top;"><strong>'
				. $label . '</strong></td><td style="padding:8px 12px;border-bottom:1px solid #333;color:#f5f5f5;">'
				. $display . '</td></tr>';
		}

		$attach_html = '';
		if ( ! empty( $attachments ) ) {
			$attach_html .= '<ul style="margin:0;padding-left:1.2em;color:#f5f5f5;">';
			foreach ( $attachments as $path ) {
				$path = (string) $path;
				$attach_html .= '<li><a href="' . esc_url( $path ) . '" style="color:#ffd27a;">'
					. esc_html( $path ) . '</a></li>';
			}
			$attach_html .= '</ul>';
		} else {
			$attach_html = '<p style="color:#c9c9c9;margin:0;">—</p>';
		}

		$deep_html = $deep
			? '<p style="color:#f5f5f5;line-height:1.5;">' . esc_html( $deep ) . '</p>'
			: '<p style="color:#c9c9c9;margin:0;">—</p>';

		return '<div style="font-family:Inter,Arial,sans-serif;background:#0a0a0a;color:#f5f5f5;padding:24px;">'
			. '<div style="max-width:640px;margin:0 auto;border:1px solid rgba(255,210,122,0.35);border-radius:12px;padding:24px;background:#141414;">'
			. '<h1 style="margin:0 0 8px;font-size:20px;color:#ffd27a;">New Project Idea</h1>'
			. '<p style="margin:0 0 20px;color:#c9c9c9;">A visitor submitted a project brief via Amy.</p>'
			. '<p style="margin:0 0 4px;color:#c9c9c9;font-size:13px;">Service</p>'
			. '<p style="margin:0 0 16px;font-size:16px;color:#ffeac2;"><strong>'
			. esc_html( $service_label ) . '</strong> <span style="color:#c9c9c9;">('
			. esc_html( $slug ) . ')</span></p>'
			. '<h2 style="margin:24px 0 8px;font-size:15px;color:#ffd27a;">Answers</h2>'
			. '<table style="width:100%;border-collapse:collapse;font-size:14px;">' . $rows . '</table>'
			. '<h2 style="margin:24px 0 8px;font-size:15px;color:#ffd27a;">Deep-dive summary</h2>'
			. $deep_html
			. '<h2 style="margin:24px 0 8px;font-size:15px;color:#ffd27a;">Attachments</h2>'
			. $attach_html
			. '<h2 style="margin:24px 0 8px;font-size:15px;color:#ffd27a;">Contact</h2>'
			. '<p style="margin:0;color:#f5f5f5;">Email: <a href="mailto:' . esc_attr( $email ) . '" style="color:#ffd27a;">'
			. esc_html( $email ) . '</a></p>'
			. ( $whatsapp
				? '<p style="margin:8px 0 0;color:#f5f5f5;">WhatsApp: ' . esc_html( $whatsapp ) . '</p>'
				: '' )
			. '</div></div>';
	}

	/**
	 * @param string $service_label Service display name.
	 * @return string
	 */
	private function build_client_body( $service_label ) {
		$label = $service_label ? $service_label : __( 'your project', 'amy-agent' );

		return '<div style="font-family:Inter,Arial,sans-serif;background:#0a0a0a;color:#f5f5f5;padding:24px;">'
			. '<div style="max-width:560px;margin:0 auto;border:1px solid rgba(255,210,122,0.35);border-radius:12px;padding:28px;background:#141414;">'
			. '<p style="margin:0 0 4px;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#ffd27a;">OGC NewFinity</p>'
			. '<h1 style="margin:0 0 16px;font-size:22px;color:#ffeac2;">We\'ve received your idea</h1>'
			. '<p style="margin:0 0 12px;line-height:1.55;color:#f5f5f5;">Thank you for submitting your project idea'
			. ( $service_label ? ' for <strong style="color:#ffd27a;">' . esc_html( $label ) . '</strong>' : '' )
			. '.</p>'
			. '<p style="margin:0 0 12px;line-height:1.55;color:#f5f5f5;">Our team will review the details and respond within <strong style="color:#ffd27a;">48 hours</strong> to this email address.</p>'
			. '<p style="margin:24px 0 0;color:#c9c9c9;font-size:14px;">— The OGC NewFinity team<br>'
			. '<a href="https://ogcnewfinity.com/" style="color:#ffd27a;">ogcnewfinity.com</a></p>'
			. '</div></div>';
	}
}
