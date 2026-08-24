from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.database.init_db import init_database
from app.core.config import settings
from app.services.vision_dispatcher import start_vision_dispatcher
from app.services.knowledge_base_dispatcher import start_knowledge_base_dispatcher
from app.services.backup_plan_reconciler import start_backup_plan_reconciler


logger = logging.getLogger("ai_lab")

MAX_DB_RETRIES = 30
RETRY_DELAY = 2


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI-Lab backend...")

    for attempt in range(1, MAX_DB_RETRIES + 1):
        try:
            init_database()
            logger.info(
                "Database initialized successfully."
            )
            break

        except OperationalError as exc:
            logger.warning(
                "Database not ready (%s/%s). "
                "Retrying in %ss...",
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
                ) from exc

            await asyncio.sleep(RETRY_DELAY)

    vision_task = start_vision_dispatcher()
    knowledge_base_task = start_knowledge_base_dispatcher()
    backup_plan_task = start_backup_plan_reconciler()
    logger.info("Application started.")
    yield
    if vision_task is not None:
        vision_task.cancel()
        try:
            await vision_task
        except asyncio.CancelledError:
            pass
    if knowledge_base_task is not None:
        knowledge_base_task.cancel()
        try:
            await knowledge_base_task
        except asyncio.CancelledError:
            pass
    backup_plan_task.cancel()
    try:
        await backup_plan_task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutdown.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)


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
    return {
        "status": "ok",
    }


@app.get("/version", tags=["System"])
def version():
    return {
        "application": settings.app_name,
        "version": app.version,
        "api_version": settings.api_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "minimum_app_version": (
            settings.minimum_app_version
        ),
        "latest_app_version": (
            settings.latest_app_version
        ),
    }
