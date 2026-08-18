"""SEO Tasks check + approval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import seo_tasks_db
from app.providers import get_provider, is_known_provider
from app.providers.errors import ProviderError
from app.providers.gemini import GeminiProvider
from app.schemas.messages import ChatMessage, ErrorBody
from app.schemas.seo_tasks import (
    SeoApproveRequest,
    SeoCheckListResponse,
    SeoCheckRequest,
    SeoCheckResponse,
    SeoFinding,
    SeoGenerateImageRequest,
    SeoGenerateImageResponse,
    SeoGenerateRequest,
    SeoGenerateResponse,
    SeoRejectRequest,
)
from app.services.seo_check import run_check_for_type
from app.services.seo_generate import build_prompt, fields_from_findings, parse_response

router = APIRouter(tags=["seo-tasks"])


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _stored_snapshot(check_id: str) -> dict:
    """Read the stored snapshot without changing seo_tasks_db's public mapping."""
    conn = seo_tasks_db._connect()
    try:
        db_row = conn.execute(
            "SELECT snapshot FROM seo_checks WHERE id = ?", (check_id,)
        ).fetchone()
    finally:
        conn.close()
    decoded = seo_tasks_db._decode_json(db_row["snapshot"]) if db_row else None
    return decoded if isinstance(decoded, dict) else {}


def _to_response(row: dict) -> SeoCheckResponse:
    findings = [
        SeoFinding(**item) if not isinstance(item, SeoFinding) else item
        for item in row.get("findings") or []
    ]
    return SeoCheckResponse(
        check_id=row["check_id"],
        wp_post_id=row["wp_post_id"],
        post_type=row["post_type"],
        content_type=row.get("content_type") or "post",
        title=row.get("title") or "",
        verdict=row["verdict"],
        findings=findings,
        status=row["status"],
        checked_at=row["checked_at"],
        updated_at=row["updated_at"],
        approved_fields=row.get("approved_fields"),
        reject_reason=row.get("reject_reason"),
        batch_run_id=row.get("batch_run_id"),
    )


@router.post(
    "/v1/seo-tasks/check",
    response_model=SeoCheckResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def run_check(body: SeoCheckRequest) -> SeoCheckResponse | JSONResponse:
    snapshot = body.model_dump()
    result = run_check_for_type(body.content_type, snapshot)
    row = seo_tasks_db.create_check(
        wp_post_id=body.wp_post_id,
        post_type=body.post_type,
        content_type=body.content_type,
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
    content_type: str | None = None,
) -> SeoCheckListResponse | JSONResponse:
    try:
        rows = seo_tasks_db.list_checks(
            status=status_filter,  # type: ignore[arg-type]
            verdict=verdict,  # type: ignore[arg-type]
            content_type=content_type,
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


@router.post(
    "/v1/seo-tasks/checks/{check_id}/generate",
    response_model=SeoGenerateResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def generate_fields(
    check_id: str, body: SeoGenerateRequest
) -> SeoGenerateResponse | JSONResponse:
    row = seo_tasks_db.get_check(check_id)
    if row is None:
        return _error("not_found", "SEO check not found.", status.HTTP_404_NOT_FOUND)

    provider_slug = body.ai.provider
    api_key = (body.ai.api_key or "").strip()
    if not is_known_provider(provider_slug) or not api_key:
        return _error(
            "invalid_config", "Unknown provider or empty API key.", status.HTTP_400_BAD_REQUEST
        )

    fields = body.fields or fields_from_findings(row.get("findings") or [])
    if not fields:
        return _error(
            "nothing_to_generate",
            "Nothing on this item is missing or weak enough to generate.",
            status.HTTP_400_BAD_REQUEST,
        )

    snapshot = row.get("snapshot") or _stored_snapshot(check_id)
    messages = build_prompt(
        content_type=row.get("content_type") or "post",
        title=row.get("title") or "",
        content_excerpt=str(snapshot.get("content_excerpt") or ""),
        existing_focus_keyphrase=str(snapshot.get("focus_keyphrase") or ""),
        fields=fields,
    )

    provider = get_provider(provider_slug)
    resolved_model = provider.resolve_model(body.ai.model)
    try:
        text = await provider.complete(messages, api_key=api_key, model=body.ai.model)
    except ProviderError as exc:
        return _error(
            exc.code,
            "Amy could not reach the AI provider. Please try again shortly.",
            status.HTTP_502_BAD_GATEWAY,
        )
    except Exception:
        return _error(
            "provider_error",
            "Amy could not reach the AI provider. Please try again shortly.",
            status.HTTP_502_BAD_GATEWAY,
        )

    try:
        generated = parse_response(text, fields)
    except ValueError:
        return _error(
            "generation_parse_error",
            "Amy's suggestion could not be read. Please try generating again.",
            status.HTTP_502_BAD_GATEWAY,
        )
    if not generated:
        return _error(
            "empty_generation",
            "Amy did not return usable suggestions. Please try again.",
            status.HTTP_502_BAD_GATEWAY,
        )

    return SeoGenerateResponse(
        check_id=check_id,
        generated_fields=generated,
        provider=provider_slug,
        model=resolved_model,
    )


@router.post(
    "/v1/seo-tasks/checks/{check_id}/generate-image",
    response_model=SeoGenerateImageResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def generate_image(
    check_id: str, body: SeoGenerateImageRequest
) -> SeoGenerateImageResponse | JSONResponse:
    row = seo_tasks_db.get_check(check_id)
    if row is None:
        return _error("not_found", "SEO check not found.", status.HTTP_404_NOT_FOUND)

    if body.ai.provider != "gemini":
        return _error(
            "unsupported_provider",
            "Image generation is only available with the Gemini provider in this version.",
            status.HTTP_400_BAD_REQUEST,
        )
    api_key = (body.ai.api_key or "").strip()
    if not api_key:
        return _error("invalid_config", "Empty API key.", status.HTTP_400_BAD_REQUEST)

    title = row.get("title") or "this page"
    content_type = row.get("content_type") or "post"
    prompt = (
        f"A clean, professional featured image for a {content_type} titled "
        f'"{title}" on the website of OGC NewFinity, an AI/blockchain/web development '
        "agency. Modern, minimal, tech-forward style. No text or logos in the image."
    )

    provider = GeminiProvider()
    try:
        image = await provider.generate_image(prompt, api_key=api_key)
    except ProviderError as exc:
        return _error(
            exc.code,
            "Amy could not generate an image right now. Please try again shortly.",
            status.HTTP_502_BAD_GATEWAY,
        )
    except Exception:
        return _error(
            "provider_error",
            "Amy could not generate an image right now. Please try again shortly.",
            status.HTTP_502_BAD_GATEWAY,
        )

    # Best-effort alt text via the same provider's text call; fall back to a plain string.
    alt_text = f"{title} — featured image"
    try:
        alt_messages = [
            ChatMessage(
                role="system",
                content="Write one short, descriptive image alt text. Plain text only, no quotes.",
            ),
            ChatMessage(
                role="user",
                content=f'The image illustrates: "{title}" ({content_type}).',
            ),
        ]
        alt_reply = await provider.complete(alt_messages, api_key=api_key, model=body.ai.model)
        if alt_reply.strip():
            alt_text = alt_reply.strip().strip('"')[:125]
    except Exception:
        pass  # alt text is best-effort; the generated image itself is the important part

    return SeoGenerateImageResponse(
        check_id=check_id,
        image_base64=image.data_base64,
        mime_type=image.mime_type,
        suggested_alt_text=alt_text,
    )
