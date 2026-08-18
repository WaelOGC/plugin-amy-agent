"""Analytics event ingestion and lead-list endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import analytics_db
from app.schemas.analytics import (
    EventIngestRequest,
    EventIngestResponse,
    LeadEventItem,
    LeadEventListResponse,
    LeadListItem,
    LeadListResponse,
)
from app.schemas.messages import ErrorBody
from app.services import geolocation, lead_scoring

router = APIRouter(tags=["analytics"])


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _session_id_short(session_id: str) -> str:
    compact = session_id.replace("-", "")
    return compact[:8] if compact else session_id[:8]


def _to_lead_item(session: dict, events: list[dict]) -> LeadListItem:
    short = _session_id_short(session["id"])
    return LeadListItem(
        session_id=session["id"],
        session_id_short=short,
        visitor_label=f"Visitor {short}",
        ip_country=session.get("ip_country"),
        ip_city=session.get("ip_city"),
        last_seen_at=float(session["last_seen_at"]),
        lead_status=session["lead_status"],
        lead_email=session.get("lead_email"),
        signal=lead_scoring.signal_for_events(events),
    )


@router.post(
    "/v1/analytics/event",
    response_model=EventIngestResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def ingest_event(body: EventIngestRequest) -> EventIngestResponse | JSONResponse:
    event_type = body.event_type.strip()
    if event_type not in analytics_db.VALID_EVENT_TYPES:
        return _error(
            "invalid_event_type",
            "Unknown event_type.",
            status.HTTP_400_BAD_REQUEST,
        )

    session_id = body.session_id.strip()
    if not session_id:
        return _error(
            "invalid_session",
            "session_id is required.",
            status.HTTP_400_BAD_REQUEST,
        )

    page_path = (body.page_path or "").strip() or None
    event_data = body.event_data if isinstance(body.event_data, dict) else None

    existing = analytics_db.get_session(session_id)
    if existing is None:
        try:
            country, city = geolocation.lookup_ip(body.ip)
        except Exception:
            country, city = None, None
        analytics_db.create_session(
            session_id,
            ip_country=country,
            ip_city=city,
        )

    analytics_db.insert_event(
        session_id=session_id,
        event_type=event_type,
        event_data=event_data,
        page_path=page_path,
    )

    email = lead_scoring.extract_captured_email(event_type, event_data)
    if email:
        analytics_db.set_lead_email(session_id, email)

    lead_status = lead_scoring.compute_lead_status(session_id)
    analytics_db.set_lead_status(session_id, lead_status)

    return EventIngestResponse(ok=True, session_id=session_id, lead_status=lead_status)


@router.get(
    "/v1/analytics/leads",
    response_model=LeadListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_leads(
    status_filter: str | None = Query(default=None, alias="status"),
) -> LeadListResponse | JSONResponse:
    try:
        rows = analytics_db.list_leads(status=status_filter)  # type: ignore[arg-type]
    except ValueError as exc:
        return _error("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)

    leads: list[LeadListItem] = []
    for row in rows:
        events = analytics_db.list_events(row["id"])
        leads.append(_to_lead_item(row, events))
    return LeadListResponse(leads=leads)


@router.get(
    "/v1/analytics/leads/{session_id}/events",
    response_model=LeadEventListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_lead_events(session_id: str) -> LeadEventListResponse | JSONResponse:
    existing = analytics_db.get_session(session_id)
    if existing is None:
        return _error("not_found", "Session not found.", status.HTTP_404_NOT_FOUND)
    events = analytics_db.list_events(session_id)
    return LeadEventListResponse(
        session_id=session_id,
        events=[
            LeadEventItem(
                id=e["id"],
                event_type=e["event_type"],
                event_data=e.get("event_data"),
                page_path=e.get("page_path"),
                created_at=e["created_at"],
            )
            for e in events
        ],
    )
