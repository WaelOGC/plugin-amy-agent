<?php
/**
 * HTTP client for the Amy Python service.
 *
 * @package Amy_Agent
 */

defined( 'ABSPATH' ) || exit;

/**
 * Proxies internal requests to amy-agent-service. Never calls AI providers.
 */
class Amy_Api_Client {

	/**
	 * @var Amy_Settings
	 */
	private $settings;

	/**
	 * @param Amy_Settings $settings Settings instance.
	 */
	public function __construct( Amy_Settings $settings ) {
		$this->settings = $settings;
	}

	/**
	 * GET /v1/health on the Python service.
	 *
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function health() {
		return $this->request( 'GET', '/v1/health' );
	}

	/**
	 * POST /v1/config/validate — schema check only in Phase 1.
	 *
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function validate_config() {
		return $this->request(
			'POST',
			'/v1/config/validate',
			array(
				'ai' => $this->settings->get_ai_config(),
			)
		);
	}

	/**
	 * POST /v1/chat — forwards to Python with AI config from settings.
	 *
	 * @param array $payload Chat request body (without ai; ai is merged from settings).
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function chat( array $payload ) {
		$payload['ai'] = $this->settings->get_ai_config();
		return $this->request( 'POST', '/v1/chat', $payload, 60 );
	}

	/**
	 * POST a Submit Idea JSON endpoint, injecting AI config when needed.
	 *
	 * @param string $path    Path under /v1/submit-idea/….
	 * @param array  $payload Request body (without ai).
	 * @param bool   $with_ai Whether to merge AI config from settings.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function submit_idea( $path, array $payload, $with_ai = false ) {
		if ( $with_ai ) {
			$payload['ai'] = $this->settings->get_ai_config();
		}
		return $this->request( 'POST', $path, $payload, 60 );
	}

	/**
	 * POST /v1/submit-idea/upload — multipart file proxy.
	 *
	 * @param string $session_id Session UUID.
	 * @param array  $file       WordPress-style file array (name, type, tmp_name, size).
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function submit_idea_upload( $session_id, array $file ) {
		$base = $this->settings->get_service_url();
		if ( '' === $base ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Service URL is not configured.',
			);
		}

		$secret = $this->settings->get_shared_secret();
		if ( '' === $secret ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Shared secret is not configured.',
			);
		}

		$tmp  = isset( $file['tmp_name'] ) ? (string) $file['tmp_name'] : '';
		$name = isset( $file['name'] ) ? (string) $file['name'] : 'upload';
		$type = isset( $file['type'] ) ? (string) $file['type'] : 'application/octet-stream';

		if ( '' === $tmp || ! is_readable( $tmp ) ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Uploaded file is not readable.',
			);
		}

		if ( ! class_exists( 'CURLFile' ) ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'CURLFile is required for uploads.',
			);
		}

		$url  = $base . '/v1/submit-idea/upload';
		$body = array(
			'session_id' => (string) $session_id,
			'file'       => new \CURLFile( $tmp, $type, $name ),
		);

		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_init -- multipart proxy to local Python service.
		$ch = curl_init( $url );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_setopt
		curl_setopt_array(
			$ch,
			array(
				CURLOPT_POST           => true,
				CURLOPT_POSTFIELDS     => $body,
				CURLOPT_RETURNTRANSFER => true,
				CURLOPT_TIMEOUT        => 60,
				CURLOPT_HTTPHEADER     => array(
					'Accept: application/json',
					'X-Amy-Secret: ' . $secret,
				),
			)
		);
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_exec
		$raw    = curl_exec( $ch );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_errno
		$errno  = curl_errno( $ch );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_error
		$errstr = curl_error( $ch );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_getinfo
		$status = (int) curl_getinfo( $ch, CURLINFO_HTTP_CODE );
		// phpcs:ignore WordPress.WP.AlternativeFunctions.curl_curl_close
		curl_close( $ch );

		if ( $errno ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => $errstr ? $errstr : 'Upload request failed.',
			);
		}

		$decoded = json_decode( (string) $raw, true );

		return array(
			'ok'          => $status >= 200 && $status < 300,
			'status_code' => $status,
			'body'        => is_array( $decoded ) ? $decoded : null,
			'error'       => ( $status >= 200 && $status < 300 ) ? null : ( is_array( $decoded ) && isset( $decoded['message'] ) ? (string) $decoded['message'] : 'Request failed.' ),
		);
	}

	/**
	 * POST /v1/analytics/event — ingest one visitor event.
	 *
	 * @param array<string, mixed> $payload Event body (session_id, event_type, …).
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function track_event( array $payload ) {
		return $this->request( 'POST', '/v1/analytics/event', $payload );
	}

	/**
	 * GET /v1/analytics/leads — optional status filter (cold/warm/hot).
	 *
	 * @param string|null $status Lead status filter.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function list_leads( $status = null ) {
		$path = '/v1/analytics/leads';
		if ( null !== $status && '' !== $status ) {
			$path .= '?' . http_build_query( array( 'status' => $status ) );
		}
		return $this->request( 'GET', $path );
	}

	/**
	 * POST /v1/seo-tasks/check — rule-based snapshot check.
	 *
	 * @param array<string, mixed> $payload SeoCheckRequest body.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function seo_check( array $payload ) {
		return $this->request( 'POST', '/v1/seo-tasks/check', $payload );
	}

	/**
	 * GET /v1/seo-tasks/checks — optional status, verdict, and content_type filters.
	 *
	 * @param string|null $status       pending_approval|approved|rejected.
	 * @param string|null $verdict      red|orange|green.
	 * @param string|null $content_type post|page|category|tag|media.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function list_seo_checks( $status = null, $verdict = null, $content_type = null ) {
		$query = array();
		if ( null !== $status && '' !== $status ) {
			$query['status'] = $status;
		}
		if ( null !== $verdict && '' !== $verdict ) {
			$query['verdict'] = $verdict;
		}
		if ( null !== $content_type && '' !== $content_type ) {
			$query['content_type'] = $content_type;
		}
		$path = '/v1/seo-tasks/checks';
		if ( ! empty( $query ) ) {
			$path .= '?' . http_build_query( $query );
		}
		return $this->request( 'GET', $path );
	}

	/**
	 * GET /v1/seo-tasks/checks/{id}.
	 *
	 * @param string $id Check UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function get_seo_check( $id ) {
		return $this->request( 'GET', '/v1/seo-tasks/checks/' . rawurlencode( (string) $id ) );
	}

	/**
	 * POST /v1/seo-tasks/checks/{id}/approve — records approval; does not write to WordPress.
	 *
	 * @param string               $id      Check UUID.
	 * @param array<string, mixed> $fields  Approved field values.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function approve_seo_check( $id, array $fields ) {
		return $this->request(
			'POST',
			'/v1/seo-tasks/checks/' . rawurlencode( (string) $id ) . '/approve',
			array( 'approved_fields' => $fields )
		);
	}

	/**
	 * POST /v1/seo-tasks/checks/{id}/reject.
	 *
	 * @param string      $id     Check UUID.
	 * @param string|null $reason Optional reason.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function reject_seo_check( $id, $reason = null ) {
		return $this->request(
			'POST',
			'/v1/seo-tasks/checks/' . rawurlencode( (string) $id ) . '/reject',
			array( 'reason' => $reason )
		);
	}

	/**
	 * POST /v1/seo-tasks/batches — start a batch run.
	 *
	 * @param array<string, mixed> $payload SeoBatchStartRequest body.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function start_seo_batch( array $payload ) {
		return $this->request( 'POST', '/v1/seo-tasks/batches', $payload, 120 );
	}

	/**
	 * POST /v1/seo-tasks/checks/{id}/generate — AI-suggested text fields.
	 *
	 * @param string $check_id Check UUID.
	 * @param array  $payload  Optional { fields: string[] }; ai is merged from settings.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function generate_seo_fields( $check_id, array $payload = array() ) {
		$payload['ai'] = $this->settings->get_ai_config();
		return $this->request(
			'POST',
			'/v1/seo-tasks/checks/' . rawurlencode( (string) $check_id ) . '/generate',
			$payload,
			60
		);
	}

	/**
	 * POST /v1/seo-tasks/checks/{id}/generate-image — AI-generated featured image.
	 *
	 * @param string $check_id Check UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function generate_seo_image( $check_id ) {
		return $this->request(
			'POST',
			'/v1/seo-tasks/checks/' . rawurlencode( (string) $check_id ) . '/generate-image',
			array( 'ai' => $this->settings->get_ai_config() ),
			90
		);
	}

	/**
	 * POST /v1/seo-tasks/batches/{id}/continue.
	 *
	 * @param string $id Batch run UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function continue_seo_batch( $id ) {
		return $this->request(
			'POST',
			'/v1/seo-tasks/batches/' . rawurlencode( (string) $id ) . '/continue',
			array(),
			120
		);
	}

	/**
	 * POST /v1/seo-tasks/batches/{id}/stop.
	 *
	 * @param string $id Batch run UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function stop_seo_batch( $id ) {
		return $this->request(
			'POST',
			'/v1/seo-tasks/batches/' . rawurlencode( (string) $id ) . '/stop',
			array()
		);
	}

	/**
	 * GET /v1/seo-tasks/batches/{id}.
	 *
	 * @param string $id Batch run UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function get_seo_batch( $id ) {
		return $this->request( 'GET', '/v1/seo-tasks/batches/' . rawurlencode( (string) $id ) );
	}

	/**
	 * GET /v1/tasks — optional filters: status, priority, assignee_wp_user_id.
	 *
	 * @param array<string, mixed> $filters Query filters.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function list_tasks( array $filters = array() ) {
		$allowed = array( 'status', 'priority', 'assignee_wp_user_id' );
		$query   = array();
		foreach ( $allowed as $key ) {
			if ( isset( $filters[ $key ] ) && '' !== $filters[ $key ] && null !== $filters[ $key ] ) {
				$query[ $key ] = $filters[ $key ];
			}
		}
		$path = '/v1/tasks';
		if ( ! empty( $query ) ) {
			$path .= '?' . http_build_query( $query );
		}
		return $this->request( 'GET', $path );
	}

	/**
	 * POST /v1/tasks — create a task.
	 *
	 * @param array<string, mixed> $payload TaskCreateRequest body.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function create_task( array $payload ) {
		return $this->request( 'POST', '/v1/tasks', $payload );
	}

	/**
	 * PATCH /v1/tasks/{id} — partial update.
	 *
	 * @param string               $id      Task UUID.
	 * @param array<string, mixed> $payload TaskUpdateRequest body.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function update_task( $id, array $payload ) {
		return $this->request( 'PATCH', '/v1/tasks/' . rawurlencode( (string) $id ), $payload );
	}

	/**
	 * DELETE /v1/tasks/{id}.
	 *
	 * @param string $id Task UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function delete_task( $id ) {
		return $this->request( 'DELETE', '/v1/tasks/' . rawurlencode( (string) $id ) );
	}

	/**
	 * GET /v1/tasks/stats — aggregate counts for Task Service cards.
	 *
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function get_task_stats() {
		return $this->request( 'GET', '/v1/tasks/stats' );
	}

	/**
	 * POST /v1/tasks/sync-dashboard-users — cache manage_options user pool for reassignment.
	 *
	 * @param array<int, array{wp_user_id: int, display_name: string}> $users Users.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function sync_dashboard_users( array $users ) {
		return $this->request( 'POST', '/v1/tasks/sync-dashboard-users', array( 'users' => $users ) );
	}

	/**
	 * GET /v1/notifications.
	 *
	 * @param int  $wp_user_id  Recipient WP user ID.
	 * @param bool $unread_only Only unread when true.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function list_notifications( $wp_user_id, $unread_only = true ) {
		$query = array(
			'wp_user_id'   => (int) $wp_user_id,
			'unread_only'  => $unread_only ? 'true' : 'false',
		);
		return $this->request( 'GET', '/v1/notifications?' . http_build_query( $query ) );
	}

	/**
	 * POST /v1/notifications/{id}/read.
	 *
	 * @param string $id Notification UUID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function mark_notification_read( $id ) {
		return $this->request( 'POST', '/v1/notifications/' . rawurlencode( (string) $id ) . '/read', array() );
	}

	/**
	 * POST /v1/tasks/{id}/acknowledge.
	 *
	 * @param string $id      Task UUID.
	 * @param int    $user_id Acting WP user ID.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function acknowledge_task( $id, $user_id ) {
		return $this->request(
			'POST',
			'/v1/tasks/' . rawurlencode( (string) $id ) . '/acknowledge',
			array( 'requester_wp_user_id' => (int) $user_id )
		);
	}

	/**
	 * POST /v1/tasks/{id}/extension-request.
	 *
	 * @param string $id                Task UUID.
	 * @param int    $user_id           Requester WP user ID.
	 * @param float  $requested_seconds Seconds to extend.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function request_extension( $id, $user_id, $requested_seconds ) {
		return $this->request(
			'POST',
			'/v1/tasks/' . rawurlencode( (string) $id ) . '/extension-request',
			array(
				'requester_wp_user_id' => (int) $user_id,
				'requested_seconds'    => (float) $requested_seconds,
			)
		);
	}

	/**
	 * POST /v1/extension-requests/{id}/approve.
	 *
	 * @param string $id      Extension request UUID.
	 * @param int    $user_id Actor (must be task creator).
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function approve_extension( $id, $user_id ) {
		return $this->request(
			'POST',
			'/v1/extension-requests/' . rawurlencode( (string) $id ) . '/approve',
			array( 'requester_wp_user_id' => (int) $user_id )
		);
	}

	/**
	 * POST /v1/extension-requests/{id}/deny.
	 *
	 * @param string $id      Extension request UUID.
	 * @param int    $user_id Actor (must be task creator).
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function deny_extension( $id, $user_id ) {
		return $this->request(
			'POST',
			'/v1/extension-requests/' . rawurlencode( (string) $id ) . '/deny',
			array( 'requester_wp_user_id' => (int) $user_id )
		);
	}

	/**
	 * Best-effort error message from a non-2xx Python response, including FastAPI's
	 * default validation-error shape ({"detail": [...]}), which has no "message" key.
	 *
	 * @param int        $status  HTTP status code.
	 * @param array|null $decoded Decoded JSON body, or null if not JSON.
	 * @return string
	 */
	private function extract_error_message( $status, $decoded ) {
		if ( is_array( $decoded ) ) {
			if ( isset( $decoded['message'] ) ) {
				return (string) $decoded['message'];
			}
			if ( isset( $decoded['detail'] ) ) {
				$detail = $decoded['detail'];
				if ( is_string( $detail ) ) {
					return $detail;
				}
				if ( is_array( $detail ) ) {
					$first = reset( $detail );
					if ( is_array( $first ) && isset( $first['msg'] ) ) {
						return (string) $first['msg'] . ( isset( $first['loc'] ) ? ' (' . wp_json_encode( $first['loc'] ) . ')' : '' );
					}
				}
			}
		}
		return sprintf( 'Request failed (HTTP %d).', (int) $status );
	}

	/**
	 * Perform an authenticated request to the Python service.
	 *
	 * @param string     $method  HTTP method.
	 * @param string     $path    Path beginning with /.
	 * @param array|null $body    JSON body for POST/PUT.
	 * @param int        $timeout Timeout in seconds.
	 * @return array{ok: bool, status_code: int, body: array|null, error: string|null}
	 */
	public function request( $method, $path, $body = null, $timeout = 15 ) {
		$base = $this->settings->get_service_url();
		if ( '' === $base ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Service URL is not configured.',
			);
		}

		$secret = $this->settings->get_shared_secret();
		if ( '' === $secret ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => 'Shared secret is not configured.',
			);
		}

		$url  = $base . $path;
		$args = array(
			'method'  => strtoupper( $method ),
			'timeout' => (int) $timeout,
			'headers' => array(
				'Accept'       => 'application/json',
				'X-Amy-Secret' => $secret,
			),
		);

		if ( null !== $body ) {
			$args['headers']['Content-Type'] = 'application/json';
			$args['body']                    = wp_json_encode( $body );
		}

		$response = wp_remote_request( $url, $args );

		if ( is_wp_error( $response ) ) {
			return array(
				'ok'          => false,
				'status_code' => 0,
				'body'        => null,
				'error'       => $response->get_error_message(),
			);
		}

		$status  = (int) wp_remote_retrieve_response_code( $response );
		$raw     = wp_remote_retrieve_body( $response );
		$decoded = json_decode( $raw, true );

		return array(
			'ok'          => $status >= 200 && $status < 300,
			'status_code' => $status,
			'body'        => is_array( $decoded ) ? $decoded : null,
			'error'       => ( $status >= 200 && $status < 300 )
				? null
				: $this->extract_error_message( $status, $decoded ),
		);
	}
}
