"""ScamRadar — LINE Bot 防詐分析系統 main application."""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.utils.logger import setup_logging
from app.routers.webhook import router as webhook_router
from app.models.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.app_name}...")

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init skipped (may not be connected yet): {e}")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="ScamRadar 獵詐雷達",
    description="LINE Bot 社群帳號風險評估 / IP 地理溯源 / 詐騙內容偵測",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(webhook_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"app": "ScamRadar", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
