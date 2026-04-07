"""DKS_mod — Fox3 DCS x Digital Kneeboard Simulator Integration API."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from dks_mod.config import settings
from dks_mod.database import close_db, init_db
from dks_mod.models import StatusResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dks_mod")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    logger.info("DKS_mod starting up...")
    await init_db()
    logger.info("Database initialized at %s", settings.db_path)

    # Start gRPC event listeners for active servers
    from dks_mod.events import start_listeners
    await start_listeners()

    yield

    # Shutdown
    from dks_mod.events import stop_listeners
    await stop_listeners()
    await close_db()
    logger.info("DKS_mod shut down.")


app = FastAPI(
    title="DKS_mod",
    description="Fox3 DCS x Digital Kneeboard Simulator Integration API",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount routers
from dks_mod.auth import router as auth_router
from dks_mod.events import router as events_router
from dks_mod.olympus import router as olympus_router
from dks_mod.tacview import router as tacview_router
from dks_mod.webhooks import router as webhooks_router

app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(webhooks_router, prefix=settings.api_prefix)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(tacview_router, prefix=settings.api_prefix)
app.include_router(olympus_router, prefix=settings.api_prefix)


@app.get("/", response_model=StatusResponse)
async def root():
    return StatusResponse(status="ok")


@app.get(f"{settings.api_prefix}/health", response_model=StatusResponse)
async def health():
    return StatusResponse(status="healthy")


if __name__ == "__main__":
    uvicorn.run(
        "dks_mod.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
