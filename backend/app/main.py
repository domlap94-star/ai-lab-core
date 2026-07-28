from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.database.init_db import init_database

MAX_DB_RETRIES = 30
RETRY_DELAY = 2


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, MAX_DB_RETRIES + 1):
        try:
            init_database()
            print("✓ Database initialized.")
            break

        except OperationalError as e:
            print(
                f"Database not ready ({attempt}/{MAX_DB_RETRIES}). "
                f"Retrying in {RETRY_DELAY}s..."
            )

            if attempt == MAX_DB_RETRIES:
                raise RuntimeError(
                    "Could not connect to PostgreSQL."
                ) from e

            await asyncio.sleep(RETRY_DELAY)

    yield


app = FastAPI(
    title="AI-Lab",
    version="0.1.0",
    lifespan=lifespan,
)

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

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "application": "AI-Lab",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }