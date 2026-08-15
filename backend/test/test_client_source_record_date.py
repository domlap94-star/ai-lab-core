from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.industry import Industry
from app.services.client_source_record_date_service import (
    ClientSourceRecordDateService,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def effective_key(item: dict) -> tuple[date, int]:
    effective = date.fromisoformat(
        item["source_record_date"] or item["created_at"][:10]
    )
    return effective, item["id"]


def require_ordered(items: list[dict], *, newest: bool) -> None:
    keys = [effective_key(item) for item in items]
    require(
        keys == sorted(keys, reverse=newest),
        f"Global effective-date order mismatch: {keys[:5]}",
    )


def main() -> None:
    parse = ClientSourceRecordDateService.parse_payload

    require(parse({"DATA": "17.01.2025"}) == date(2025, 1, 17), "Valid date")
    require(parse({" data ": "01.12.2024"}) == date(2024, 12, 1), "Key")
    require(parse({"DATA": "30.02.2026"}) is None, "Invalid calendar date")
    require(parse({"DATA": "17.01.25"}) is None, "Ambiguous short year")
    require(parse({"DATA": "Oględziny 17.01.2025"}) is None, "Text value")
    require(parse({"DATA NASTEPNEGO KONTAKTU": "17.01.2025"}) is None, "Key")
    require(parse(None) is None, "Missing payload")

    utc = timezone.utc
    candidates = [
        (1, datetime(2026, 1, 1, tzinfo=utc)),
        (2, datetime(2024, 1, 1, tzinfo=utc)),
        (3, datetime(2026, 1, 1, tzinfo=utc)),
        (4, datetime(2026, 1, 1, tzinfo=utc)),
    ]
    source_dates = {
        1: date(2023, 1, 1),
        3: date(2025, 1, 1),
        4: date(2025, 1, 1),
    }
    newest_ids = ClientSourceRecordDateService.order_client_ids(
        candidates,
        source_dates,
        sort_order="newest",
    )
    oldest_ids = ClientSourceRecordDateService.order_client_ids(
        candidates,
        source_dates,
        sort_order="oldest",
    )
    require(newest_ids == [4, 3, 2, 1], f"Newest cases: {newest_ids}")
    require(oldest_ids == [1, 2, 3, 4], f"Oldest cases: {oldest_ids}")

    boundary_candidates = [
        (client_id, datetime(2020, 1, 1, tzinfo=utc))
        for client_id in range(1, 66)
    ]
    boundary_sources = {
        client_id: date(2020, 1, client_id % 28 + 1)
        for client_id in range(1, 66)
    }
    boundary_ids = ClientSourceRecordDateService.order_client_ids(
        boundary_candidates,
        boundary_sources,
        sort_order="newest",
    )
    first_page = boundary_ids[:50]
    second_page = boundary_ids[50:]
    first_last = (
        boundary_sources[first_page[-1]],
        first_page[-1],
    )
    second_first = (
        boundary_sources[second_page[0]],
        second_page[0],
    )
    require(first_last >= second_first, "Synthetic page boundary order")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.is_active.is_(True)).first()
        require(user is not None, "No active user")
        token = create_access_token(data={"sub": user.username})
        headers = {"Authorization": f"Bearer {token}"}
        http = TestClient(app)

        page = http.get(
            "/api/v1/clients/page",
            params={"skip": 0, "limit": 100},
            headers=headers,
        )
        require(page.status_code == 200, page.text)
        payload = page.json()
        require(payload["items"], "Expected real clients")
        require(
            all("source_record_date" in item for item in payload["items"]),
            "Additive field missing from page",
        )
        require(
            all("raw_payload" not in item for item in payload["items"]),
            "Raw provenance leaked",
        )
        require_ordered(payload["items"], newest=True)

        explicit_newest = http.get(
            "/api/v1/clients/page",
            params={"sort_order": "newest", "skip": 0, "limit": 100},
            headers=headers,
        )
        require(explicit_newest.status_code == 200, explicit_newest.text)
        require(
            [item["id"] for item in explicit_newest.json()["items"]]
            == [item["id"] for item in payload["items"]],
            "Default sort differs from explicit newest",
        )

        next_page = http.get(
            "/api/v1/clients/page",
            params={"sort_order": "newest", "skip": 100, "limit": 100},
            headers=headers,
        )
        require(next_page.status_code == 200, next_page.text)
        require_ordered(next_page.json()["items"], newest=True)
        require(
            effective_key(payload["items"][-1])
            >= effective_key(next_page.json()["items"][0]),
            "Real page boundary order",
        )

        oldest = http.get(
            "/api/v1/clients/page",
            params={"sort_order": "oldest", "skip": 0, "limit": 100},
            headers=headers,
        )
        require(oldest.status_code == 200, oldest.text)
        require_ordered(oldest.json()["items"], newest=False)

        invalid_sort = http.get(
            "/api/v1/clients/page",
            params={"sort_order": "name"},
            headers=headers,
        )
        require(invalid_sort.status_code == 422, invalid_sort.text)

        representative = payload["items"][0]
        search_page = http.get(
            "/api/v1/clients/page",
            params={"search": representative["name"], "sort_order": "newest"},
            headers=headers,
        )
        require(search_page.status_code == 200, search_page.text)
        require_ordered(search_page.json()["items"], newest=True)

        type_page = http.get(
            "/api/v1/clients/page",
            params={
                "client_type": representative["client_type"],
                "sort_order": "newest",
            },
            headers=headers,
        )
        require(type_page.status_code == 200, type_page.text)
        require_ordered(type_page.json()["items"], newest=True)

        industry = db.query(Industry).filter(Industry.is_active.is_(True)).first()
        if industry is not None:
            industry_page = http.get(
                "/api/v1/clients/page",
                params={"industry_id": industry.id, "sort_order": "newest"},
                headers=headers,
            )
            require(industry_page.status_code == 200, industry_page.text)
            require_ordered(industry_page.json()["items"], newest=True)

        dated = next(
            (item for item in payload["items"] if item["source_record_date"]),
            None,
        )
        if dated is not None:
            detail = http.get(
                f"/api/v1/clients/{dated['id']}",
                headers=headers,
            )
            require(detail.status_code == 200, detail.text)
            require(
                detail.json()["source_record_date"]
                == dated["source_record_date"],
                "Detail/page source date mismatch",
            )

        legacy = http.get(
            "/api/v1/clients",
            params={"skip": 0, "limit": 1},
            headers=headers,
        )
        require(legacy.status_code == 200, legacy.text)
        require(isinstance(legacy.json(), list), "Legacy response changed")

        print("CLIENT SOURCE RECORD DATE: OK")
        print("parser_format=DD.MM.YYYY")
        print("selection=earliest_valid_date")
        print("default_sort=global_newest")
        print("page_boundary=OK")
        print("database_modifications=0")
    finally:
        db.close()


if __name__ == "__main__":
    main()
