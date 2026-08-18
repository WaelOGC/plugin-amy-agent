"""SEO Tasks check + approval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import seo_tasks_db
from app.schemas.messages import ErrorBody
from app.schemas.seo_tasks import (
    SeoApproveRequest,
    SeoCheckListResponse,
    SeoCheckRequest,
    SeoCheckResponse,
    SeoFinding,
    SeoRejectRequest,
)
from app.services.seo_check import check_snapshot

router = APIRouter(tags=["seo-tasks"])


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _to_response(row: dict) -> SeoCheckResponse:
    findings = [
        SeoFinding(**item) if not isinstance(item, SeoFinding) else item
        for item in row.get("findings") or []
    ]
    return SeoCheckResponse(
        check_id=row["check_id"],
        wp_post_id=row["wp_post_id"],
        post_type=row["post_type"],
        title=row.get("title") or "",
        verdict=row["verdict"],
        findings=findings,
        status=row["status"],
        checked_at=row["checked_at"],
        updated_at=row["updated_at"],
        approved_fields=row.get("approved_fields"),
        reject_reason=row.get("reject_reason"),
    )


@router.post(
    "/v1/seo-tasks/check",
    response_model=SeoCheckResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def run_check(body: SeoCheckRequest) -> SeoCheckResponse | JSONResponse:
    snapshot = body.model_dump()
    result = check_snapshot(**snapshot)
    row = seo_tasks_db.create_check(
        wp_post_id=body.wp_post_id,
        post_type=body.post_type,
        title=body.title,
        verdict=result["verdict"],
        findings=result["findings"],
        snapshot=snapshot,
    )
    return _to_response(row)


@router.get(
    "/v1/seo-tasks/checks",
    response_model=SeoCheckListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_checks(
    status_filter: str | None = Query(default=None, alias="status"),
    verdict: str | None = None,
) -> SeoCheckListResponse | JSONResponse:
    try:
        rows = seo_tasks_db.list_checks(
            status=status_filter,  # type: ignore[arg-type]
            verdict=verdict,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        return _error("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)
    return SeoCheckListResponse(checks=[_to_response(row) for row in rows])


@router.get(
    "/v1/seo-tasks/checks/{check_id}",
    response_model=SeoCheckResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def get_check(check_id: str) -> SeoCheckResponse | JSONResponse:
    row = seo_tasks_db.get_check(check_id)
    if row is None:
        return _error("not_found", "SEO check not found.", status.HTTP_404_NOT_FOUND)
    return _to_response(row)


@router.post(
    "/v1/seo-tasks/checks/{check_id}/approve",
    response_model=SeoCheckResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def approve_check(
    check_id: str, body: SeoApproveRequest
) -> SeoCheckResponse | JSONResponse:
    try:
        row = seo_tasks_db.approve_check(check_id, body.approved_fields)
    except ValueError as exc:
        return _error("invalid_status", str(exc), status.HTTP_409_CONFLICT)
    if row is None:
        return _error("not_found", "SEO check not found.", status.HTTP_404_NOT_FOUND)
    return _to_response(row)


@router.post(
    "/v1/seo-tasks/checks/{check_id}/reject",
    response_model=SeoCheckResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def reject_check(
    check_id: str, body: SeoRejectRequest | None = None
) -> SeoCheckResponse | JSONResponse:
    reason = body.reason if body is not None else None
    try:
        row = seo_tasks_db.reject_check(check_id, reason)
    except ValueError as exc:
        return _error("invalid_status", str(exc), status.HTTP_409_CONFLICT)
    if row is None:
        return _error("not_found", "SEO check not found.", status.HTTP_404_NOT_FOUND)
    return _to_response(row)
