from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    probe_counts = {"started": 0, "stopped": 0}

    @asynccontextmanager
    async def probe_lifespan(_: FastAPI):
        probe_counts["started"] += 1
        try:
            yield
        finally:
            probe_counts["stopped"] += 1

    probe = FastAPI(lifespan=probe_lifespan)

    @probe.get("/probe")
    def probe_route() -> dict[str, bool]:
        return {"ok": True}

    constructor_client = TestClient(probe)
    require(constructor_client.get("/probe").status_code == 200, "Probe failed")
    require(probe_counts == {"started": 0, "stopped": 0}, "Constructor started lifespan")
    constructor_client.close()
    with TestClient(probe) as context_client:
        require(context_client.get("/probe").status_code == 200, "Context probe failed")
        require(probe_counts["started"] == 1, "Context manager did not start lifespan")
    require(probe_counts["stopped"] == 1, "Context manager did not stop lifespan")

    product_lifespan_starts = 0
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def forbidden_product_lifespan(_: FastAPI):
        nonlocal product_lifespan_starts
        product_lifespan_starts += 1
        raise AssertionError("Product lifespan must not run in this auth contract")
        yield  # pragma: no cover

    app.router.lifespan_context = forbidden_product_lifespan
    http = TestClient(app)
    try:
        requests = (
            http.get("/api/v1/calendar/month", params={"year": 2026, "month": 8}),
            http.get("/api/v1/work-items"),
            http.post("/api/v1/work-items", json={}),
            http.get("/api/v1/absence-requests"),
            http.post("/api/v1/absence-requests", json={}),
            http.get("/api/v1/admin/backups/storage-locations"),
            http.get("/api/v1/admin/backups/legacy-candidates"),
            http.post(
                "/api/v1/admin/backups/storage-locations/register",
                json={"host_path": r"D:\Backup"},
            ),
        )
        statuses = [response.status_code for response in requests]
        require(statuses == [401] * 8, "CHUNK 13 endpoint accepted an unauthenticated request")
        require(product_lifespan_starts == 0, "Product lifespan was entered")
    finally:
        http.close()
        app.router.lifespan_context = original_lifespan
    print(f"CHUNK 13 API authentication: PASS statuses={statuses}")
    print(f"PRODUCT_LIFESPAN_START_COUNT={product_lifespan_starts}")
    print("TESTCLIENT_CONTEXT_LIFESPAN_START_COUNT=1")


if __name__ == "__main__":
    main()
