"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import chat, config_sync, health, submit_idea, tasks
from app.routes.submit_idea import UPLOAD_ROOT

app = FastAPI(
    title="Amy Agent Service",
    version="0.1.2",
    description="Intelligence layer for the Amy Agent WordPress plugin (Phase 1 scaffold).",
)

app.include_router(health.router)
app.include_router(config_sync.router)
app.include_router(chat.router)
app.include_router(submit_idea.router)
app.include_router(tasks.router)

# Public, unauthenticated file serving for Submit Idea attachments (email links).
# Scoped to uploads/submit-idea only; Starlette StaticFiles blocks path traversal
# and does not enable directory listing.
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads/submit-idea",
    StaticFiles(directory=str(UPLOAD_ROOT), html=False),
    name="submit_idea_uploads",
)
