"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.routes import chat, config_sync, health, submit_idea

app = FastAPI(
    title="Amy Agent Service",
    version="0.1.0",
    description="Intelligence layer for the Amy Agent WordPress plugin (Phase 1 scaffold).",
)

app.include_router(health.router)
app.include_router(config_sync.router)
app.include_router(chat.router)
app.include_router(submit_idea.router)
