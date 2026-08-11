"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config_task_rules as rules
from app.routes import chat, config_sync, health, notifications, submit_idea, tasks
from app.routes.submit_idea import UPLOAD_ROOT
from app.services.task_escalation import run_escalation_pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amy-agent-service")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler.add_job(
        run_escalation_pass,
        "interval",
        seconds=rules.ESCALATION_JOB_INTERVAL_SECONDS,
        id="task_escalation",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Task escalation scheduler started (every %ss)",
        rules.ESCALATION_JOB_INTERVAL_SECONDS,
    )
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Task escalation scheduler stopped")


app = FastAPI(
    title="Amy Agent Service",
    version="0.1.3",
    description="Intelligence layer for the Amy Agent WordPress plugin (Phase 1 scaffold).",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(config_sync.router)
app.include_router(chat.router)
app.include_router(submit_idea.router)
app.include_router(tasks.router)
app.include_router(notifications.router)

# Public, unauthenticated file serving for Submit Idea attachments (email links).
# Scoped to uploads/submit-idea only; Starlette StaticFiles blocks path traversal
# and does not enable directory listing.
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads/submit-idea",
    StaticFiles(directory=str(UPLOAD_ROOT), html=False),
    name="submit_idea_uploads",
)
