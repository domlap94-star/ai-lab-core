from pathlib import Path


def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def main() -> None:
    root = Path("/app")
    migration = (root / "alembic/versions/followup_calendar_tasks_20260820.py").read_text(encoding="utf-8")
    service = (root / "app/services/work_item_service.py").read_text(encoding="utf-8")
    schema = (root / "app/schemas/work_item.py").read_text(encoding="utf-8")
    router = (root / "app/api/work_items.py").read_text(encoding="utf-8")
    absences = (root / "app/api/absences.py").read_text(encoding="utf-8")
    calendar = (root / "app/api/calendar.py").read_text(encoding="utf-8")
    for table in ("work_items", "work_item_notes", "work_item_documents", "absence_requests"):
        require(f'"{table}"' in migration, f"missing migration table {table}")
    for value in ("task", "order", "realization", "reminder", "event", "vacation", "day_off", "sick_leave"):
        require(value in schema or value in migration, f"missing allowlist value {value}")
    require("pg_advisory_xact_lock" in service and "absence_overlap" in service, "absence overlap protection absent")
    require("expected_version" in schema and "version_conflict" in service, "optimistic concurrency absent")
    require("cross_client_document" in service, "cross-client document protection absent")
    require("WORK_LIMIT = 1000" in service and "ABSENCE_LIMIT = 500" in service, "calendar caps absent")
    require("description:" not in schema.split("class CalendarEntry", 1)[1].split("class CalendarMonth", 1)[0], "calendar leaks description")
    for path, token in ((router, "/archive"), (router, "/restore"), (absences, "/approve"), (absences, "/reject"), (calendar, '"/month"')):
        require(token in path, f"missing route {token}")
    print("CHUNK 13 backend domain contract: PASS")


if __name__ == "__main__": main()
