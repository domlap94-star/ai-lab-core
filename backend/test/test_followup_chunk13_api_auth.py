from fastapi.testclient import TestClient

from app.main import app


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    http = TestClient(app)
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
    require(all(response.status_code == 401 for response in requests), "CHUNK 13 endpoint accepted an unauthenticated request")
    print("CHUNK 13 API authentication: PASS")


if __name__ == "__main__":
    main()
