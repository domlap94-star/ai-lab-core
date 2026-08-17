from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.user import User
from app.repositories.client_email_repository import (
    LINKED_CANDIDATE_STATUSES,
)


PUBLIC_KEYS = {
    "id",
    "external_id",
    "message_id",
    "thread_id",
    "direction",
    "message_at",
    "from_name",
    "from_address",
    "to_addresses",
    "cc_addresses",
    "subject",
    "body_text",
    "source_url",
    "attachment_count",
    "attachments",
    "created_at",
}
ATTACHMENT_KEYS = {
    "document_id",
    "original_filename",
    "content_type",
    "file_size",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def eligible_sources(db):
    return (
        db.query(CandidateSource, ClientCandidate)
        .join(
            ClientCandidate,
            ClientCandidate.id == CandidateSource.candidate_id,
        )
        .filter(
            CandidateSource.source_type == "gmail_message",
            CandidateSource.deleted_at.is_(None),
            ClientCandidate.deleted_at.is_(None),
            ClientCandidate.matched_client_id.isnot(None),
            ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
        )
    )


def main() -> None:
    http = TestClient(app)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.is_active.is_(True)).first()
        require(user is not None, "No active user for JWT acceptance")
        headers = {
            "Authorization": "Bearer "
            + create_access_token(data={"sub": user.username})
        }

        client_counts = (
            db.query(
                ClientCandidate.matched_client_id,
                func.count(func.distinct(CandidateSource.external_id)).label(
                    "message_count"
                ),
            )
            .join(
                CandidateSource,
                CandidateSource.candidate_id == ClientCandidate.id,
            )
            .join(Client, Client.id == ClientCandidate.matched_client_id)
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
                Client.deleted_at.is_(None),
            )
            .group_by(ClientCandidate.matched_client_id)
            .order_by(
                func.count(func.distinct(CandidateSource.external_id)).desc(),
                ClientCandidate.matched_client_id.asc(),
            )
            .all()
        )
        require(client_counts, "No sourced Gmail client exists")
        target_client_id, expected_total = client_counts[0]

        empty_client_id = (
            db.query(Client.id)
            .filter(
                Client.deleted_at.is_(None),
                ~Client.id.in_([row[0] for row in client_counts]),
            )
            .order_by(Client.id.asc())
            .limit(1)
            .scalar()
        )
        require(empty_client_id is not None, "No empty-state client exists")

        path = f"/api/v1/clients/{target_client_id}/emails"
        require(http.get(path).status_code == 401, "Anonymous request must be 401")
        default_page = http.get(path, headers=headers)
        require(default_page.status_code == 200, default_page.text)
        require(
            default_page.json()["limit"] == 20
            and len(default_page.json()["items"]) == 20,
            "Default page size must be 20",
        )
        require(
            http.get(path, headers=headers, params={"limit": 101}).status_code
            == 422,
            "Limit above maximum must be 422",
        )

        unknown_id = (db.query(func.max(Client.id)).scalar() or 0) + 100_000
        require(
            http.get(
                f"/api/v1/clients/{unknown_id}/emails", headers=headers
            ).status_code
            == 404,
            "Unknown client must be 404",
        )
        deleted_client = (
            db.query(Client.id)
            .filter(Client.deleted_at.isnot(None))
            .order_by(Client.id.asc())
            .first()
        )
        if deleted_client is not None:
            require(
                http.get(
                    f"/api/v1/clients/{deleted_client[0]}/emails",
                    headers=headers,
                ).status_code
                == 404,
                "Soft-deleted client must be 404",
            )

        empty = http.get(
            f"/api/v1/clients/{empty_client_id}/emails", headers=headers
        )
        require(empty.status_code == 200, empty.text)
        require(empty.json()["total"] == 0, "Empty client total must be zero")
        require(empty.json()["items"] == [], "Empty client items must be empty")

        first = http.get(path, headers=headers, params={"skip": 0, "limit": 20})
        require(first.status_code == 200, first.text)
        first_page = first.json()
        focused_source_id = first_page["items"][0]["id"]
        focused = http.get(
            path,
            headers=headers,
            params={"source_id": focused_source_id},
        )
        require(focused.status_code == 200, focused.text)
        require(focused.json()["total"] == 1, "Focused email total must be one")
        require(
            focused.json()["items"][0]["id"] == focused_source_id,
            "Focused endpoint returned the wrong source",
        )
        cross_client = http.get(
            f"/api/v1/clients/{empty_client_id}/emails",
            headers=headers,
            params={"source_id": focused_source_id},
        )
        require(cross_client.status_code == 200, cross_client.text)
        require(
            cross_client.json()["items"] == [],
            "Email source leaked across client scope",
        )
        second = http.get(
            path,
            headers=headers,
            params={"skip": 20, "limit": 20},
        )
        require(second.status_code == 200, second.text)
        second_page = second.json()

        require(first_page["total"] == expected_total, "Total/count mismatch")
        require(first_page["skip"] == 0, "Wrong skip")
        require(first_page["limit"] == 20, "Wrong limit")
        require(
            second_page["total"] == expected_total,
            "Count/items criteria differ",
        )
        combined = first_page["items"] + second_page["items"]
        require(
            len({item["external_id"] for item in combined}) == len(combined),
            "Duplicate Gmail message was exposed",
        )

        ordering = [
            (
                datetime.fromisoformat(item["message_at"])
                if item["message_at"] is not None
                else None,
                item["id"],
            )
            for item in combined
        ]
        for previous, current in zip(ordering, ordering[1:]):
            if previous[0] is None:
                require(current[0] is None, "NULL message date is not last")
            elif current[0] is not None:
                require(
                    previous[0] > current[0]
                    or (
                        previous[0] == current[0]
                        and previous[1] > current[1]
                    ),
                    "Newest-first stable ordering failed",
                )

        for item in combined:
            require(set(item) == PUBLIC_KEYS, "Unsafe or missing email fields")
            require("raw_payload" not in item, "raw_payload leaked")
            require(item["message_id"] == item["external_id"], "Bad message ID")
            require(
                item["direction"] in {"sent", "received", "unknown"},
                "Bad direction",
            )
            source = (
                eligible_sources(db)
                .filter(
                    CandidateSource.id == item["id"],
                    ClientCandidate.matched_client_id == target_client_id,
                )
                .first()
            )
            require(source is not None, "Unrelated or invalid source leaked")
            require(
                source[0].external_id == item["external_id"],
                "Source provenance mismatch",
            )
            for attachment in item["attachments"]:
                require(
                    set(attachment) == ATTACHMENT_KEYS,
                    "Unsafe attachment fields",
                )
                require("storage_path" not in attachment, "storage_path leaked")
            require(
                item["attachment_count"] == len(item["attachments"]),
                "Attachment count/list mismatch",
            )

        attachment_client = (
            db.query(ClientCandidate.matched_client_id)
            .join(
                CandidateSource,
                CandidateSource.candidate_id == ClientCandidate.id,
            )
            .join(
                Document,
                Document.gmail_message_id == CandidateSource.external_id,
            )
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
                Document.source_type == "gmail_attachment",
            )
            .group_by(ClientCandidate.matched_client_id)
            .order_by(func.count(Document.id).desc())
            .first()
        )
        require(attachment_client is not None, "No attachment client exists")
        attachment_page_response = http.get(
            f"/api/v1/clients/{attachment_client[0]}/emails",
            headers=headers,
            params={"limit": 100},
        )
        require(attachment_page_response.status_code == 200, attachment_page_response.text)
        attachment_items = attachment_page_response.json()["items"]
        require(
            any(item["attachment_count"] > 0 for item in attachment_items),
            "Deterministic attachment linkage was not exposed",
        )
        require(
            all(
                "storage_path" not in attachment
                for item in attachment_items
                for attachment in item["attachments"]
            ),
            "Attachment storage_path leaked",
        )

        transcript_clients = (
            db.query(func.count(Client.id))
            .filter(
                Client.deleted_at.is_(None),
                Client.notes.ilike("%Kierunek wiadomości:%"),
            )
            .scalar()
        )
        gmail_clients = {row[0] for row in client_counts}
        transcript_ids = {
            row[0]
            for row in db.query(Client.id)
            .filter(
                Client.deleted_at.is_(None),
                Client.notes.ilike("%Kierunek wiadomości:%"),
            )
            .all()
        }
        exposed_messages = sum(row[1] for row in client_counts)

        print("CLIENT EMAIL API E2E: OK")
        print(f"real_client_id={target_client_id}")
        print(f"real_client_total={expected_total}")
        print(f"empty_client_id={empty_client_id}")
        print(f"first_page={len(first_page['items'])}")
        print(f"second_page={len(second_page['items'])}")
        print(f"transcript_clients={transcript_clients}")
        print(f"transcript_with_gmail={len(transcript_ids & gmail_clients)}")
        print(f"transcript_without_gmail={len(transcript_ids - gmail_clients)}")
        print(f"gmail_without_transcript={len(gmail_clients - transcript_ids)}")
        print(f"gmail_linked_clients={len(gmail_clients)}")
        print(f"total_exposed_messages={exposed_messages}")
        print(
            "field_coverage="
            + str(
                {
                    key: sum(item[key] not in (None, "", []) for item in combined)
                    for key in (
                        "message_at",
                        "subject",
                        "body_text",
                        "from_address",
                        "to_addresses",
                    )
                }
            )
        )
        print(
            "direction_coverage="
            + str(
                {
                    value: sum(item["direction"] == value for item in combined)
                    for value in ("sent", "received", "unknown")
                }
            )
        )
        print(
            "attachment_messages="
            + str(sum(item["attachment_count"] > 0 for item in combined))
        )
        print(f"attachment_client_id={attachment_client[0]}")
        print(
            "attachment_documents="
            + str(sum(item["attachment_count"] for item in attachment_items))
        )
        print("database_modifications=0")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
