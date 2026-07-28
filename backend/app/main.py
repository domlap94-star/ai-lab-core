from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.database.init_db import init_database
from app.core.config import settings

# ==========================================================
# Logging
# ==========================================================

logger = logging.getLogger("ai_lab")

# ==========================================================
# Database startup
# ==========================================================

MAX_DB_RETRIES = 30
RETRY_DELAY = 2

# ==========================================================
# Lifespan
# ==========================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI-Lab backend...")

    for attempt in range(1, MAX_DB_RETRIES + 1):
        try:
            init_database()

            logger.info("Database initialized successfully.")

            break

        except OperationalError as e:
            logger.warning(
                "Database not ready (%s/%s). Retrying in %ss...",
                attempt,
                MAX_DB_RETRIES,
                RETRY_DELAY,
            )

            if attempt == MAX_DB_RETRIES:
                logger.exception(
                    "Unable to connect to PostgreSQL."
                )

                raise RuntimeError(
                    "Could not connect to PostgreSQL."
                ) from e

            await asyncio.sleep(RETRY_DELAY)

    logger.info("Application started.")

    yield

    logger.info("Application shutdown.")

# ==========================================================
# FastAPI
# ==========================================================

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Routers
# ==========================================================

app.include_router(api_router)

# ==========================================================
# Endpoints
# ==========================================================


@app.get("/", tags=["System"])
def root():
    return {
        "application": settings.app_name,
        "environment": settings.environment,
        "status": "running",
        "version": app.version,
    }


@app.get("/health", tags=["System"])
def health():
    """
    Basic health endpoint.

    Future versions should include:
    - PostgreSQL
    - Ollama
    - Qdrant
    - Open WebUI
    - n8n
    """

    return {
        "status": "ok",
    }


@app.get("/version", tags=["System"])
def version():
    return {
        "application": settings.app_name,
        "version": app.version,
        "environment": settings.environment,
        "debug": settings.debug,
    }