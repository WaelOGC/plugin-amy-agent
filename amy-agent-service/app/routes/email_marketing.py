"""Email marketing history, opt-out, Amy propose, optional inbound webhook."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import email_history_db
from app.schemas.email_marketing import (
    AddNoteRequest,
    CheckSuppressedResponse,
    EmailMessageOut,
    EmailThreadDetailResponse,
    EmailThreadListResponse,
    EmailThreadOut,
    InboundWebhookRequest,
    ProposeSendRequest,
    ProposeSendResponse,
    RecordOutboundRequest,
    RecordOutboundResponse,
    SuppressionListResponse,
    SuppressionOut,
    SuppressionRequest,
)
from app.schemas.messages import ErrorBody

router = APIRouter(tags=["email-marketing"])

INBOUND_LIMITATION = (
    "FluentSMTP is outbound-only. Automatic mailbox inbound is not wired "
    "(no AgentMail). Log replies with Add reply note, or POST the optional "
    "inbound webhook if you forward hello@ mail yourself."
)


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _thread_out(row: dict) -> EmailThreadOut:
    last = row.get("last_message")
    return EmailThreadOut(
        id=row["id"],
        participant_email=row["participant_email"],
        subject=row.get("subject"),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_message=EmailMessageOut(**last) if last else None,
        suppressed=bool(row.get("suppressed")),
    )


def _message_out(row: dict) -> EmailMessageOut:
    return EmailMessageOut(**row)


@router.get(
    "/v1/email-marketing/threads",
    response_model=EmailThreadListResponse,
    dependencies=[Depends(require_amy_secret)],
)
def list_threads(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
) -> EmailThreadListResponse:
    data = email_history_db.list_threads(limit=limit, offset=offset, q=q)
    return EmailThreadListResponse(
        threads=[_thread_out(t) for t in data["threads"]],
        total=data["total"],
        limit=data["limit"],
        offset=data["offset"],
    )


@router.get(
    "/v1/email-marketing/threads/{thread_id}",
    response_model=EmailThreadDetailResponse,
    dependencies=[Depends(require_amy_secret)],
)
def get_thread(thread_id: str) -> EmailThreadDetailResponse | JSONResponse:
    thread = email_history_db.get_thread(thread_id)
    if not thread:
        return _error("not_found", "Thread not found.", status.HTTP_404_NOT_FOUND)
    messages = email_history_db.list_messages(thread_id)
    thread["suppressed"] = email_history_db.is_suppressed(thread["participant_email"])
    thread["last_message"] = messages[-1] if messages else None
    return EmailThreadDetailResponse(
        thread=_thread_out(thread),
        messages=[_message_out(m) for m in messages],
        inbound_limitation=INBOUND_LIMITATION,
    )


@router.post(
    "/v1/email-marketing/outbound",
    response_model=RecordOutboundResponse,
    dependencies=[Depends(require_amy_secret)],
)
def record_outbound(body: RecordOutboundRequest) -> RecordOutboundResponse | JSONResponse:
    try:
        result = email_history_db.record_outbound_batch(
            recipients=[r.model_dump() for r in body.recipients],
            subject=body.subject,
            body=body.body,
            from_email=body.from_email,
            wp_user_id=body.wp_user_id,
            channel=body.channel if body.channel in email_history_db.VALID_CHANNELS else "fluentsmtp",
        )
    except ValueError as exc:
        return _error("bad_request", str(exc), status.HTTP_400_BAD_REQUEST)
    return RecordOutboundResponse(recorded=result["recorded"], items=result["items"])


@router.post(
    "/v1/email-marketing/threads/{thread_id}/notes",
    response_model=EmailMessageOut,
    dependencies=[Depends(require_amy_secret)],
)
def add_note(thread_id: str, body: AddNoteRequest) -> EmailMessageOut | JSONResponse:
    try:
        msg = email_history_db.add_manual_note(
            thread_id=thread_id,
            body=body.body,
            wp_user_id=body.wp_user_id,
            as_inbound=body.as_inbound,
        )
    except ValueError as exc:
        code = "not_found" if "not found" in str(exc).lower() else "bad_request"
        http = status.HTTP_404_NOT_FOUND if code == "not_found" else status.HTTP_400_BAD_REQUEST
        return _error(code, str(exc), http)
    return _message_out(msg)


@router.post(
    "/v1/email-marketing/propose",
    response_model=ProposeSendResponse,
    dependencies=[Depends(require_amy_secret)],
)
def propose_send(body: ProposeSendRequest) -> ProposeSendResponse | JSONResponse:
    """Amy-triggered send hook: stores a proposed draft; never sends mail."""
    try:
        result = email_history_db.propose_send(
            to_email=body.to_email,
            subject=body.subject,
            body=body.body,
            from_email=body.from_email,
            proposed_by=body.proposed_by,
            meta=body.meta,
        )
    except ValueError as exc:
        return _error("bad_request", str(exc), status.HTTP_400_BAD_REQUEST)
    thread = result["thread"]
    thread["suppressed"] = email_history_db.is_suppressed(thread["participant_email"])
    thread["last_message"] = result["message"]
    return ProposeSendResponse(
        thread=_thread_out(thread),
        message=_message_out(result["message"]),
        requires_human_approve=True,
    )


@router.get(
    "/v1/email-marketing/suppressions",
    response_model=SuppressionListResponse,
    dependencies=[Depends(require_amy_secret)],
)
def list_suppressions(
    limit: int = Query(default=500, ge=1, le=2000),
) -> SuppressionListResponse:
    rows = email_history_db.list_suppressions(limit=limit)
    return SuppressionListResponse(suppressions=[SuppressionOut(**r) for r in rows])


@router.get(
    "/v1/email-marketing/suppressions/check",
    response_model=CheckSuppressedResponse,
    dependencies=[Depends(require_amy_secret)],
)
def check_suppressed(
    email: str = Query(min_length=3, max_length=254),
) -> CheckSuppressedResponse:
    key = email.strip().lower()
    return CheckSuppressedResponse(
        email=key,
        suppressed=email_history_db.is_suppressed(key),
    )


@router.post(
    "/v1/email-marketing/suppressions",
    response_model=SuppressionOut,
    dependencies=[Depends(require_amy_secret)],
)
def add_suppression(body: SuppressionRequest) -> SuppressionOut | JSONResponse:
    try:
        row = email_history_db.add_suppression(
            body.email,
            reason=body.reason,
            source=body.source or "manual",
        )
    except ValueError as exc:
        return _error("bad_request", str(exc), status.HTTP_400_BAD_REQUEST)
    return SuppressionOut(**row)


@router.delete(
    "/v1/email-marketing/suppressions/{email}",
    response_model=None,
    dependencies=[Depends(require_amy_secret)],
)
def remove_suppression(email: str):
    ok = email_history_db.remove_suppression(email)
    if not ok:
        return _error("not_found", "Suppression not found.", status.HTTP_404_NOT_FOUND)
    return {"ok": True, "email": email.strip().lower()}


@router.post(
    "/v1/email-marketing/inbound",
    response_model=EmailMessageOut,
    dependencies=[Depends(require_amy_secret)],
)
def inbound_webhook(body: InboundWebhookRequest) -> EmailMessageOut | JSONResponse:
    """Optional generic inbound. FluentSMTP has no receive path; no AgentMail."""
    from_email = body.from_email or body.from_
    to_email = body.to_email or body.to
    text = body.body or body.text or body.message or body.html
    if not from_email or not text:
        return _error(
            "bad_request",
            "from_email and body (or text/message) are required.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        result = email_history_db.record_inbound(
            from_email=from_email,
            to_email=to_email,
            subject=body.subject,
            body=text,
            channel="inbound_webhook",
            meta=body.meta,
        )
    except ValueError as exc:
        return _error("bad_request", str(exc), status.HTTP_400_BAD_REQUEST)
    return _message_out(result["message"])
