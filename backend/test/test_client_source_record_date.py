from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.user import User
from app.services.client_source_record_date_service import (
    ClientSourceRecordDateService,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parse = ClientSourceRecordDateService.parse_payload

    require(parse({"DATA": "17.01.2025"}) == date(2025, 1, 17), "Valid date")
    require(parse({" data ": "01.12.2024"}) == date(2024, 12, 1), "Key")
    require(parse({"DATA": "30.02.2026"}) is None, "Invalid calendar date")
    require(parse({"DATA": "17.01.25"}) is None, "Ambiguous short year")
    require(parse({"DATA": "Oględziny 17.01.2025"}) is None, "Text value")
    require(parse({"DATA NASTEPNEGO KONTAKTU": "17.01.2025"}) is None, "Key")
    require(parse(None) is None, "Missing payload")

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
        print("database_modifications=0")
    finally:
        db.close()


if __name__ == "__main__":
    main()
