<?php
/**
 * Admin-AJAX handlers for Task Service CRUD (proxies to Python service).
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Nonce-protected admin-ajax actions for tasks.
 */
class Amy_Tasks_Ajax {

	const NONCE_ACTION = 'amy_agent_tasks';

	/**
	 * @var Amy_Api_Client
	 */
	private $api_client;

	/**
	 * @param Amy_Api_Client $api_client API client.
	 */
	public function __construct( Amy_Api_Client $api_client ) {
		$this->api_client = $api_client;
	}

	/**
	 * Register AJAX actions.
	 */
	public function register() {
		add_action( 'wp_ajax_amy_task_list', array( $this, 'ajax_list' ) );
		add_action( 'wp_ajax_amy_task_create', array( $this, 'ajax_create' ) );
		add_action( 'wp_ajax_amy_task_update', array( $this, 'ajax_update' ) );
		add_action( 'wp_ajax_amy_task_delete', array( $this, 'ajax_delete' ) );
		add_action( 'wp_ajax_amy_task_stats', array( $this, 'ajax_stats' ) );
	}

	/**
	 * Shared gate: capability + nonce.
	 */
	private function guard() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_send_json_error(
				array( 'message' => __( 'You do not have permission to manage tasks.', 'amy-agent' ) ),
				403
			);
		}
		check_ajax_referer( self::NONCE_ACTION, 'nonce' );
	}

	/**
	 * Forward a failed API response as JSON error.
	 *
	 * @param array{ok: bool, status_code: int, body: array|null, error: string|null} $result API result.
	 */
	private function send_api_error( array $result ) {
		$message = __( 'Request failed.', 'amy-agent' );
		if ( ! empty( $result['error'] ) ) {
			$message = (string) $result['error'];
		} elseif ( is_array( $result['body'] ) && ! empty( $result['body']['message'] ) ) {
			$message = (string) $result['body']['message'];
		}
		$status = ! empty( $result['status_code'] ) ? (int) $result['status_code'] : 500;
		if ( $status < 400 ) {
			$status = 500;
		}
		wp_send_json_error( array( 'message' => $message ), $status );
	}

	/**
	 * GET-style list via amy_task_list.
	 */
	public function ajax_list() {
		$this->guard();

		$filters = array();
		if ( isset( $_REQUEST['status'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified in guard().
			$filters['status'] = sanitize_text_field( wp_unslash( $_REQUEST['status'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		}
		if ( isset( $_REQUEST['priority'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			$filters['priority'] = sanitize_text_field( wp_unslash( $_REQUEST['priority'] ) ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		}
		if ( isset( $_REQUEST['assignee_wp_user_id'] ) && '' !== $_REQUEST['assignee_wp_user_id'] ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			$filters['assignee_wp_user_id'] = absint( $_REQUEST['assignee_wp_user_id'] ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		}

		$result = $this->api_client->list_tasks( $filters );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array( 'tasks' => array() ) );
	}

	/**
	 * Create via amy_task_create.
	 */
	public function ajax_create() {
		$this->guard();

		$title = isset( $_POST['title'] ) ? sanitize_text_field( wp_unslash( $_POST['title'] ) ) : '';
		if ( '' === $title ) {
			wp_send_json_error(
				array( 'message' => __( 'Title is required.', 'amy-agent' ) ),
				400
			);
		}

		$assignee_type = isset( $_POST['assignee_type'] ) ? sanitize_text_field( wp_unslash( $_POST['assignee_type'] ) ) : 'human';
		if ( ! in_array( $assignee_type, array( 'amy', 'human' ), true ) ) {
			wp_send_json_error(
				array( 'message' => __( 'Invalid assignee type.', 'amy-agent' ) ),
				400
			);
		}

		$assignee_wp_user_id = null;
		if ( 'human' === $assignee_type ) {
			$assignee_wp_user_id = isset( $_POST['assignee_wp_user_id'] ) ? absint( $_POST['assignee_wp_user_id'] ) : 0;
			if ( ! $assignee_wp_user_id ) {
				wp_send_json_error(
					array( 'message' => __( 'Please select an assignee.', 'amy-agent' ) ),
					400
				);
			}
		}

		$priority = isset( $_POST['priority'] ) ? sanitize_text_field( wp_unslash( $_POST['priority'] ) ) : 'normal';
		if ( ! in_array( $priority, array( 'normal', 'urgent' ), true ) ) {
			$priority = 'normal';
		}

		$status_val = isset( $_POST['status'] ) ? sanitize_text_field( wp_unslash( $_POST['status'] ) ) : 'todo';
		$allowed_status = array( 'todo', 'in_progress', 'waiting_extension', 'done' );
		if ( ! in_array( $status_val, $allowed_status, true ) ) {
			$status_val = 'todo';
		}

		$due_date = isset( $_POST['due_date'] ) ? sanitize_text_field( wp_unslash( $_POST['due_date'] ) ) : '';
		$due_date = '' !== $due_date ? $due_date : null;

		$description = isset( $_POST['description'] ) ? sanitize_textarea_field( wp_unslash( $_POST['description'] ) ) : '';
		$description = '' !== $description ? $description : null;

		$created_by = isset( $_POST['created_by_wp_user_id'] ) ? absint( $_POST['created_by_wp_user_id'] ) : 0;
		if ( ! $created_by ) {
			$created_by = get_current_user_id();
		}

		$payload = array(
			'title'                 => $title,
			'description'           => $description,
			'assignee_type'         => $assignee_type,
			'assignee_wp_user_id'   => $assignee_wp_user_id,
			'created_by_wp_user_id' => $created_by,
			'priority'              => $priority,
			'status'                => $status_val,
			'due_date'              => $due_date,
		);

		$result = $this->api_client->create_task( $payload );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * Partial update via amy_task_update.
	 */
	public function ajax_update() {
		$this->guard();

		$id = isset( $_POST['id'] ) ? sanitize_text_field( wp_unslash( $_POST['id'] ) ) : '';
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Task ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$payload = array();

		if ( isset( $_POST['title'] ) ) {
			$title = sanitize_text_field( wp_unslash( $_POST['title'] ) );
			if ( '' === $title ) {
				wp_send_json_error(
					array( 'message' => __( 'Title is required.', 'amy-agent' ) ),
					400
				);
			}
			$payload['title'] = $title;
		}

		if ( array_key_exists( 'description', $_POST ) ) {
			$description = sanitize_textarea_field( wp_unslash( $_POST['description'] ) );
			$payload['description'] = '' !== $description ? $description : null;
		}

		if ( isset( $_POST['assignee_type'] ) ) {
			$assignee_type = sanitize_text_field( wp_unslash( $_POST['assignee_type'] ) );
			if ( ! in_array( $assignee_type, array( 'amy', 'human' ), true ) ) {
				wp_send_json_error(
					array( 'message' => __( 'Invalid assignee type.', 'amy-agent' ) ),
					400
				);
			}
			$payload['assignee_type'] = $assignee_type;
			if ( 'amy' === $assignee_type ) {
				$payload['assignee_wp_user_id'] = null;
			} elseif ( isset( $_POST['assignee_wp_user_id'] ) ) {
				$uid = absint( $_POST['assignee_wp_user_id'] );
				if ( ! $uid ) {
					wp_send_json_error(
						array( 'message' => __( 'Please select an assignee.', 'amy-agent' ) ),
						400
					);
				}
				$payload['assignee_wp_user_id'] = $uid;
			}
		} elseif ( isset( $_POST['assignee_wp_user_id'] ) ) {
			$payload['assignee_wp_user_id'] = absint( $_POST['assignee_wp_user_id'] );
		}

		if ( isset( $_POST['priority'] ) ) {
			$priority = sanitize_text_field( wp_unslash( $_POST['priority'] ) );
			if ( in_array( $priority, array( 'normal', 'urgent' ), true ) ) {
				$payload['priority'] = $priority;
			}
		}

		if ( isset( $_POST['status'] ) ) {
			$status_val = sanitize_text_field( wp_unslash( $_POST['status'] ) );
			$allowed    = array( 'todo', 'in_progress', 'waiting_extension', 'done' );
			if ( in_array( $status_val, $allowed, true ) ) {
				$payload['status'] = $status_val;
			}
		}

		if ( array_key_exists( 'due_date', $_POST ) ) {
			$due_date = sanitize_text_field( wp_unslash( $_POST['due_date'] ) );
			$payload['due_date'] = '' !== $due_date ? $due_date : null;
		}

		if ( empty( $payload ) ) {
			wp_send_json_error(
				array( 'message' => __( 'No fields to update.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->update_task( $id, $payload );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}

	/**
	 * Delete via amy_task_delete.
	 */
	public function ajax_delete() {
		$this->guard();

		$id = isset( $_POST['id'] ) ? sanitize_text_field( wp_unslash( $_POST['id'] ) ) : '';
		if ( '' === $id ) {
			wp_send_json_error(
				array( 'message' => __( 'Task ID is required.', 'amy-agent' ) ),
				400
			);
		}

		$result = $this->api_client->delete_task( $id );
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array( 'ok' => true, 'id' => $id ) );
	}

	/**
	 * Stats via amy_task_stats.
	 */
	public function ajax_stats() {
		$this->guard();

		$result = $this->api_client->get_task_stats();
		if ( ! $result['ok'] ) {
			$this->send_api_error( $result );
		}

		wp_send_json_success( is_array( $result['body'] ) ? $result['body'] : array() );
	}
}
