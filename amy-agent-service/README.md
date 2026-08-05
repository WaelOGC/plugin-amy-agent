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

## Endpoints (see plugin `docs/api-contract.md`)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/v1/health` | Requires `X-Amy-Secret` |
| POST | `/v1/config/validate` | Schema check only |
| POST | `/v1/chat` | Calls selected provider; `200` / `502` |
| GET | `/uploads/submit-idea/{session_id}/{file}` | Public static files (no auth); scoped to upload dir |

## Tests

```bash
pytest
```
