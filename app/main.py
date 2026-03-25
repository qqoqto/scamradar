"""ScamRadar — LINE Bot 防詐分析系統 + Web Dashboard main application."""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.utils.logger import setup_logging
from app.routers.webhook import router as webhook_router
from app.routers.public_api import router as public_api_router
from app.models.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v2.0...")

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
    description="台灣詐騙防護平台 — LINE Bot + Web Dashboard + Public API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ──────────────────────────────────────────────────

# Phase 1: LINE Bot webhook
app.include_router(webhook_router, prefix="/api/v1")

# Phase 2: Public API (dashboard + third-party)
app.include_router(public_api_router)


# ─── Health & root ───────────────────────────────────────────────

@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "service": "ScamRadar", "version": "2.0.0"}


# Keep old /health endpoint for backward compatibility
@app.get("/health")
async def health():
    return {"status": "healthy"}


# ─── Serve React Dashboard (static files) ───────────────────────
#
# After `npm run build`, frontend/dist/ contains the React SPA.
# FastAPI serves these as static files, with index.html as fallback
# for client-side routing (React Router).

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")

if os.path.isdir(STATIC_DIR):
    logger.info(f"Serving React dashboard from {STATIC_DIR}")

    # Serve /assets/* (JS, CSS, images from Vite build)
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

    # SPA catch-all: non-API routes serve index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API or health routes
        if full_path.startswith(("api/", "health", "docs", "openapi")):
            return None

        # Try to serve the exact file (e.g. favicon, manifest)
        file_path = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)

        # Fallback to index.html for React Router
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    # No frontend build — serve simple JSON root
    @app.get("/")
    async def root():
        return {
            "app": "ScamRadar",
            "status": "running",
            "version": "2.0.0",
            "dashboard": "Frontend not built. Run: cd frontend && npm install && npm run build",
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
