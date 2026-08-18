"""SEO Tasks batch-run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import seo_batches_db
from app.schemas.messages import ErrorBody
from app.schemas.seo_batches import (
    SeoBatchItemResult,
    SeoBatchReport,
    SeoBatchRunListResponse,
    SeoBatchRunResponse,
    SeoBatchRunSummary,
    SeoBatchStartRequest,
)
from app.schemas.seo_tasks import SeoFinding

router = APIRouter(tags=["seo-tasks-batches"])


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _item_result(raw: dict) -> SeoBatchItemResult:
    findings = [
        SeoFinding(**item) if not isinstance(item, SeoFinding) else item
        for item in raw.get("findings") or []
    ]
    return SeoBatchItemResult(
        item_id=int(raw.get("item_id") or 0),
        title=raw.get("title") or "",
        check_id=raw.get("check_id"),
        verdict=raw.get("verdict"),
        findings=findings,
        error=raw.get("error"),
    )


def _to_response(row: dict) -> SeoBatchRunResponse:
    reports = [
        SeoBatchReport(
            batch_index=int(rep.get("batch_index") or 0),
            results=[_item_result(item) for item in rep.get("results") or []],
        )
        for rep in row.get("reports") or []
    ]
    return SeoBatchRunResponse(
        batch_run_id=row["batch_run_id"],
        content_type=row["content_type"],
        mode=row["mode"],
        batch_size=row["batch_size"],
        total_items=row["total_items"],
        status=row["status"],
        processed_count=row["processed_count"],
        reports=reports,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_summary(row: dict) -> SeoBatchRunSummary:
    return SeoBatchRunSummary(
        batch_run_id=row["batch_run_id"],
        content_type=row["content_type"],
        mode=row["mode"],
        batch_size=row["batch_size"],
        total_items=row["total_items"],
        status=row["status"],
        processed_count=row["processed_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _items_payload(body: SeoBatchStartRequest) -> list[dict]:
    return [
        {
            "item_id": item.item_id,
            "title": item.title,
            "snapshot": item.snapshot,
        }
        for item in body.items
    ]


@router.post(
    "/v1/seo-tasks/batches",
    response_model=SeoBatchRunResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def start_batch(body: SeoBatchStartRequest) -> SeoBatchRunResponse | JSONResponse:
    try:
        run = seo_batches_db.create_batch_run(
            content_type=body.content_type,
            mode=body.mode,
            batch_size=body.batch_size,
            items=_items_payload(body),
        )
    except ValueError as exc:
        return _error("invalid_batch", str(exc), status.HTTP_400_BAD_REQUEST)

    if body.mode == "auto":
        while run["status"] == "in_progress":
            try:
                run = seo_batches_db.process_next_batch(run["batch_run_id"])
            except (KeyError, ValueError) as exc:
                return _error("invalid_batch", str(exc), status.HTTP_409_CONFLICT)
    else:
        try:
            run = seo_batches_db.process_next_batch(run["batch_run_id"])
        except (KeyError, ValueError) as exc:
            return _error("invalid_batch", str(exc), status.HTTP_409_CONFLICT)
    return _to_response(run)


@router.post(
    "/v1/seo-tasks/batches/{batch_run_id}/continue",
    response_model=SeoBatchRunResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def continue_batch(batch_run_id: str) -> SeoBatchRunResponse | JSONResponse:
    existing = seo_batches_db.get_batch_run(batch_run_id)
    if existing is None:
        return _error("not_found", "Batch run not found.", status.HTTP_404_NOT_FOUND)
    if existing["mode"] != "manual":
        return _error(
            "invalid_status",
            "Continue is only valid for manual batch runs.",
            status.HTTP_409_CONFLICT,
        )
    if existing["status"] != "in_progress":
        return _error(
            "invalid_status",
            "batch run is not in progress",
            status.HTTP_409_CONFLICT,
        )
    try:
        run = seo_batches_db.process_next_batch(batch_run_id)
    except KeyError:
        return _error("not_found", "Batch run not found.", status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return _error("invalid_status", str(exc), status.HTTP_409_CONFLICT)
    return _to_response(run)


@router.post(
    "/v1/seo-tasks/batches/{batch_run_id}/stop",
    response_model=SeoBatchRunResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def stop_batch(batch_run_id: str) -> SeoBatchRunResponse | JSONResponse:
    try:
        run = seo_batches_db.stop_batch_run(batch_run_id)
    except KeyError:
        return _error("not_found", "Batch run not found.", status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return _error("invalid_status", str(exc), status.HTTP_409_CONFLICT)
    return _to_response(run)


@router.get(
    "/v1/seo-tasks/batches",
    response_model=SeoBatchRunListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_batches(
    content_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
) -> SeoBatchRunListResponse | JSONResponse:
    try:
        rows = seo_batches_db.list_batch_runs(
            content_type=content_type,
            status=status_filter,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        return _error("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)
    return SeoBatchRunListResponse(runs=[_to_summary(row) for row in rows])


@router.get(
    "/v1/seo-tasks/batches/{batch_run_id}",
    response_model=SeoBatchRunResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def get_batch(batch_run_id: str) -> SeoBatchRunResponse | JSONResponse:
    run = seo_batches_db.get_batch_run(batch_run_id)
    if run is None:
        return _error("not_found", "Batch run not found.", status.HTTP_404_NOT_FOUND)
    return _to_response(run)
