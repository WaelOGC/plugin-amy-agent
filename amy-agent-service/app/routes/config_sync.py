"""Config validate endpoint (no provider API calls in Phase 1)."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.providers import is_known_provider
from app.schemas.messages import ConfigValidateRequest, ConfigValidateResponse

router = APIRouter(tags=["config"])


@router.post(
    "/v1/config/validate",
    response_model=ConfigValidateResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def validate_config(body: ConfigValidateRequest) -> ConfigValidateResponse | JSONResponse:
    provider = body.ai.provider
    api_key = (body.ai.api_key or "").strip()

    if not is_known_provider(provider) or not api_key:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ConfigValidateResponse(
                ok=False,
                error="invalid_config",
                message="Unknown provider or empty API key.",
            ).model_dump(),
        )

    return ConfigValidateResponse(ok=True, provider=provider)
