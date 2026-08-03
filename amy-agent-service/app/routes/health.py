"""Health endpoint."""

from fastapi import APIRouter, Depends

from app import __version__
from app.auth import require_amy_secret
from app.schemas.messages import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/v1/health", response_model=HealthResponse, dependencies=[Depends(require_amy_secret)])
async def health() -> HealthResponse:
    return HealthResponse(ok=True, version=__version__)
