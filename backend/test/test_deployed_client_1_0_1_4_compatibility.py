from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.user import User
from app.schemas.client import ClientRead


PATH = "/api/v1/clients"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    http = TestClient(app)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.is_active.is_(True)).first()
        require(user is not None, "No active user for deployed-client JWT check")
        token = create_access_token(data={"sub": user.username})
        headers = {"Authorization": f"Bearer {token}"}

        require(
            http.get(PATH).status_code == 401,
            "Anonymous legacy list must return 401",
        )

        response = http.get(
            PATH,
            headers=headers,
            params={"skip": 0, "limit": 100},
        )
        require(response.status_code == 200, response.text)
        payload = response.json()
        require(isinstance(payload, list), "Deployed +4 requires a JSON array root")
        require(payload, "Legacy compatibility page is unexpectedly empty")
        for item in payload:
            ClientRead.model_validate(item)

        target = payload[0]
        searched_response = http.get(
            PATH,
            headers=headers,
            params={"search": target["name"], "skip": 0, "limit": 100},
        )
        require(searched_response.status_code == 200, searched_response.text)
        searched = searched_response.json()
        require(isinstance(searched, list), "Legacy search root must be an array")
        require(
            target["id"] in {item["id"] for item in searched},
            "Legacy search missed its representative client",
        )
        for item in searched:
            ClientRead.model_validate(item)

        require(
            http.get(PATH, headers=headers, params={"limit": 501}).status_code
            == 422,
            "Legacy maximum above 500 must be rejected",
        )

        print("DEPLOYED CLIENT 1.0.1+4 COMPATIBILITY: OK")
        print(f"legacy_page={len(payload)}")
        print(f"legacy_search_total={len(searched)}")
        print(f"representative_client_id={target['id']}")
        print("legacy_root=array")
        print("legacy_client_read_validation=OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
