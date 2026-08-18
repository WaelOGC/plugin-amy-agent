# Amy Agent Service

Python intelligence layer for the Amy Agent WordPress plugin. Phase 2: real provider adapters + working `/v1/chat`.

## Layout

Sibling of Local’s `app/` folder:

```
amy-agent/                    # Local site root
├── app/
└── amy-agent-service/        # this service
```

## Setup

```bash
cd amy-agent-service
py -3 -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -e ".[dev]"
copy .env.example .env   # or: cp .env.example .env
```

Edit `.env`:

- `AMY_SHARED_SECRET` — must match WordPress **Settings → Amy Agent → Shared secret**
- `PORT` — default `8765`
- `PUBLIC_BASE_URL` — public origin of this service (no trailing slash), used for Submit Idea upload links in emails. Local: `http://127.0.0.1:8765`. On Dokploy, use the publicly reachable HTTPS URL of this service (not an internal Docker hostname).

**Do not put AI provider API keys in `.env`.** Keys live in WordPress Options and are sent per request in the `ai` payload.

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

## Local + WordPress (Local by Flywheel)

PHP may need a different host than the browser:

- Try `http://127.0.0.1:8765` first in plugin settings
- If PHP cannot reach the host, try `http://host.docker.internal:8765`

## Persistence

Submit Your Idea sessions are stored in SQLite at `data/submit_idea_sessions.db` (created automatically). This survives **process restarts** on the same filesystem. A **Dokploy redeploy** that starts a fresh container will still wipe sessions unless `data/` (or the app directory) is mounted as a persistent volume in the Dokploy service config (Application → Volumes).

Task Service tasks are stored in a separate SQLite file at `data/tasks.db` (created automatically, no TTL). Analytics events live in `data/analytics.db` (90-day retention). SEO Tasks checks live in `data/seo_tasks.db` (no TTL). All of these files have the **exact same volume-mounting requirement**: a Dokploy redeploy will wipe them unless `data/` is mounted as a persistent volume in the Dokploy service configuration. Do not mount individual DB files — mount the whole `data/` directory. The existing `data/` volume already covers `seo_tasks.db`; no extra volume config is needed.

## Endpoints (see plugin `docs/api-contract.md`)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/v1/health` | Requires `X-Amy-Secret` |
| POST | `/v1/config/validate` | Schema check only |
| POST | `/v1/chat` | Calls selected provider; `200` / `502` |
| GET | `/v1/tasks` | List tasks (optional `status`, `priority`, `assignee_wp_user_id`) |
| POST | `/v1/tasks` | Create task |
| GET | `/v1/tasks/stats` | Aggregate counts for Task Service stat cards |
| GET | `/v1/tasks/{id}` | Fetch one task |
| PATCH | `/v1/tasks/{id}` | Partial update |
| DELETE | `/v1/tasks/{id}` | Delete task |
| POST | `/v1/analytics/event` | Ingest a visitor event (fixed event-type set) |
| GET | `/v1/analytics/leads` | Lead list for the admin page (optional `status`) |
| GET | `/v1/analytics/leads/{session_id}/events` | Event timeline for one session |
| POST | `/v1/seo-tasks/check` | Rule-based SEO snapshot check; stores a pending-approval row |
| GET | `/v1/seo-tasks/checks` | List stored checks (optional `status`, `verdict`) |
| GET | `/v1/seo-tasks/checks/{id}` | Fetch one check |
| POST | `/v1/seo-tasks/checks/{id}/approve` | Record approval (`approved_fields`); does not write to WordPress |
| POST | `/v1/seo-tasks/checks/{id}/reject` | Record rejection (optional `reason`) |
| GET | `/uploads/submit-idea/{session_id}/{file}` | Public static files (no auth); scoped to upload dir |

## Tests

```bash
pytest
```
