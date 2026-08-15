from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.client import Client
from app.models.user import User


PATH = "/api/v1/clients/page"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def get_json(client: TestClient, headers: dict[str, str], **params):
    response = client.get(PATH, headers=headers, params=params)
    require(response.status_code == 200, response.text)
    return response.json()


def main() -> None:
    http = TestClient(app)

    anonymous = http.get(PATH)
    require(anonymous.status_code == 401, "Anonymous list must return 401")

    db = SessionLocal()

    try:
        user = db.query(User).filter(User.is_active.is_(True)).first()
        require(user is not None, "No active user for JWT acceptance")
        token = create_access_token(data={"sub": user.username})
        headers = {"Authorization": f"Bearer {token}"}

        active_count = (
            db.query(func.count(Client.id))
            .filter(Client.deleted_at.is_(None))
            .scalar()
        )

        first = get_json(http, headers, skip=0, limit=50)
        require(set(first) == {"items", "total", "skip", "limit"}, "Bad contract")
        require(first["total"] == active_count, "Total does not match active clients")
        require(first["skip"] == 0 and first["limit"] == 50, "Bad page metadata")
        require(len(first["items"]) == min(50, active_count), "Bad first page size")

        second = get_json(http, headers, skip=50, limit=50)
        first_ids = {item["id"] for item in first["items"]}
        second_ids = {item["id"] for item in second["items"]}
        require(first_ids.isdisjoint(second_ids), "Stable pages contain duplicates")
        combined_items = first["items"] + second["items"]
        effective_keys = [
            (
                date.fromisoformat(
                    item["source_record_date"] or item["created_at"][:10]
                ),
                item["id"],
            )
            for item in combined_items
        ]
        require(
            effective_keys == sorted(effective_keys, reverse=True),
            "Client effective-date ordering is unstable",
        )

        last_skip = ((active_count - 1) // 50) * 50 if active_count else 0
        last = get_json(http, headers, skip=last_skip, limit=50)
        require(
            len(last["items"]) == active_count - last_skip,
            "Bad last page size",
        )

        require(second["items"], "Need a client outside the first page")
        target = second["items"][0]
        search_value = next(
            (
                target[field]
                for field in (
                    "tax_id",
                    "primary_email",
                    "primary_phone",
                    "city",
                    "legal_name",
                    "name",
                )
                if target.get(field)
            ),
            target["name"],
        )
        searched = get_json(http, headers, search=search_value, limit=100)
        require(
            target["id"] in {item["id"] for item in searched["items"]},
            "Search did not find client outside first page",
        )
        require(searched["total"] >= 1, "Search total is invalid")
        require(len(searched["items"]) <= searched["total"], "Search total mismatch")

        typed = get_json(
            http,
            headers,
            client_type=target["client_type"],
            limit=100,
        )
        require(typed["total"] >= len(typed["items"]), "Type total mismatch")
        require(
            all(item["client_type"] == target["client_type"] for item in typed["items"]),
            "Type filter leaked another type",
        )

        industry_target = (
            db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                Client.industry_id.is_not(None),
            )
            .order_by(Client.id.asc())
            .first()
        )
        representative_industry_id = (
            industry_target.industry_id if industry_target is not None else 1
        )
        industry = get_json(
            http,
            headers,
            industry_id=representative_industry_id,
            limit=100,
        )
        require(industry["total"] >= len(industry["items"]), "Industry total mismatch")
        require(
            all(
                item["industry_id"] == representative_industry_id
                for item in industry["items"]
            ),
            "Industry filter leaked another industry",
        )

        combined = None
        if industry_target is not None:
            combined = get_json(
                http,
                headers,
                search=industry_target.name,
                client_type=industry_target.client_type,
                industry_id=industry_target.industry_id,
                limit=100,
            )
            require(
                industry_target.id
                in {item["id"] for item in combined["items"]},
                "Combined filters did not find representative client",
            )
            require(
                all(
                    item["client_type"] == industry_target.client_type
                    and item["industry_id"] == industry_target.industry_id
                    for item in combined["items"]
                ),
                "Combined filters are inconsistent",
            )

        too_large = http.get(PATH, headers=headers, params={"limit": 101})
        require(too_large.status_code == 422, "Limit above maximum must return 422")

        detail = http.get(
            f"/api/v1/clients/{target['id']}",
            headers=headers,
        )
        require(detail.status_code == 200, "Static /page broke client detail route")

        print("CLIENT LIST CONTRACT E2E: OK")
        print(f"active_total={active_count}")
        print(f"first_page={len(first['items'])}")
        print(f"last_page={len(last['items'])}")
        print(f"search_target_id={target['id']}")
        print(f"search_total={searched['total']}")
        print(f"type_total={typed['total']}")
        print(f"industry_total={industry['total']}")
        print(
            "combined_total="
            + (str(combined["total"]) if combined is not None else "N/A")
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
