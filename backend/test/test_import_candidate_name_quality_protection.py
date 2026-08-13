from __future__ import annotations

from types import SimpleNamespace

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.import_ingest_service import (
    ImportIngestService,
)


CANDIDATE_ID = 4
RAW_SHEET_NAME = "Gruba"
ENRICHED_NAME = "Tadeusz Gruba"


def get_candidate(
    db,
    *,
    for_update: bool = False,
):
    query = (
        db.query(ClientCandidate)
        .filter(
            ClientCandidate.id == CANDIDATE_ID,
            ClientCandidate.deleted_at.is_(None),
        )
    )

    if for_update:
        query = query.with_for_update()

    return query.one()


def read_name_fresh() -> str:
    db = SessionLocal()

    try:
        return get_candidate(db).name

    finally:
        db.close()


def build_data(
    candidate: ClientCandidate,
    *,
    name: str,
):
    return SimpleNamespace(
        client_type=candidate.client_type,
        name=name,
        legal_name=candidate.legal_name,
        tax_id=candidate.tax_id,
        registration_number=(
            candidate.registration_number
        ),
        industry_id=candidate.industry_id,
        website=candidate.website,
        primary_email=candidate.primary_email,
        primary_phone=candidate.primary_phone,
        street=candidate.street,
        building_number=candidate.building_number,
        unit_number=candidate.unit_number,
        postal_code=candidate.postal_code,
        city=candidate.city,
        country_code=candidate.country_code,
        notes=candidate.notes,
        confidence=candidate.confidence,
    )


def verify_pure_quality_rules() -> None:
    db = SessionLocal()

    try:
        service = ImportIngestService(db)

        print()
        print("=" * 120)
        print("PURE NAME QUALITY TESTS")
        print("=" * 120)

        cases = [
            (
                "Gruba",
                "Tadeusz Gruba",
                True,
            ),
            (
                "Tadeusz Gruba",
                "Gruba",
                False,
            ),
            (
                "grubatadeusz@gmail.com",
                "Gruba",
                True,
            ),
            (
                "grubatadeusz@gmail.com",
                "Tadeusz Gruba",
                True,
            ),
            (
                "Tadeusz Gruba",
                "grubatadeusz@gmail.com",
                False,
            ),
            (
                "Anna",
                "Anna Wnorowska",
                True,
            ),
            (
                "Anna Wnorowska",
                "Anna",
                False,
            ),
            (
                "Tadeusz Gruba",
                "Tadeusz Gruba",
                False,
            ),
            (
                "Nieznany klient",
                "Tadeusz Gruba",
                True,
            ),
            (
                "Tadeusz Gruba",
                "Nieznany klient",
                False,
            ),
        ]

        for current, incoming, expected in cases:
            actual = (
                service._should_replace_candidate_name(
                    current,
                    incoming,
                )
            )

            print(
                repr(current),
                "->",
                repr(incoming),
                "| expected:",
                expected,
                "| actual:",
                actual,
            )

            if actual != expected:
                raise RuntimeError(
                    "Name quality rule failed: "
                    f"{current!r} -> {incoming!r}"
                )

        print()
        print("PURE QUALITY RULES: OK")

    finally:
        db.rollback()
        db.close()


def prepare_enriched_state() -> None:
    db = SessionLocal()

    try:
        candidate = get_candidate(
            db,
            for_update=True,
        )

        print()
        print("=" * 120)
        print("PREPARE ENRICHED CONTROL STATE")
        print("=" * 120)

        print(
            "name_before_prepare:",
            repr(candidate.name),
        )

        candidate.name = ENRICHED_NAME

        db.flush()

        print(
            "name_after_flush:",
            repr(candidate.name),
        )

        db.commit()

        print(
            "PREPARE COMMIT: OK"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    fresh_name = read_name_fresh()

    print(
        "fresh_name_after_prepare:",
        repr(fresh_name),
    )

    if fresh_name != ENRICHED_NAME:
        raise RuntimeError(
            "Failed to persist enriched control state."
        )

    print(
        "ENRICHED STATE PERSISTENCE: OK"
    )


def simulate_worse_sheet_import() -> None:
    db = SessionLocal()

    try:
        service = ImportIngestService(db)

        candidate = get_candidate(
            db,
            for_update=True,
        )

        print()
        print("=" * 120)
        print("SIMULATE WORSE GOOGLE SHEETS IMPORT")
        print("=" * 120)

        print(
            "canonical_before_import:",
            repr(candidate.name),
        )

        incoming = build_data(
            candidate,
            name=RAW_SHEET_NAME,
        )

        should_replace = (
            service._should_replace_candidate_name(
                candidate.name,
                incoming.name,
            )
        )

        print(
            "should_replace_with_worse_name:",
            should_replace,
        )

        if should_replace:
            raise RuntimeError(
                "Quality helper allows name downgrade."
            )

        candidate_changed = (
            service._candidate_has_sheet_changes(
                candidate,
                incoming,
            )
        )

        print(
            "candidate_changed_for_name_downgrade:",
            candidate_changed,
        )

        if candidate_changed:
            raise RuntimeError(
                "Worse Google Sheets name still "
                "causes candidate_changed=True."
            )

        service._merge_google_sheets_candidate_data(
            candidate,
            incoming,
        )

        db.flush()

        print(
            "name_after_sheet_merge:",
            repr(candidate.name),
        )

        if candidate.name != ENRICHED_NAME:
            raise RuntimeError(
                "Google Sheets merge downgraded "
                "canonical candidate name."
            )

        db.commit()

        print(
            "SIMULATED IMPORT COMMIT: OK"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def verify_after_import_commit() -> None:
    name = read_name_fresh()

    print()
    print("=" * 120)
    print("FRESH SESSION AFTER SIMULATED IMPORT")
    print("=" * 120)

    print(
        "fresh_session_name:",
        repr(name),
    )

    if name != ENRICHED_NAME:
        raise RuntimeError(
            "Canonical name was downgraded "
            "after simulated import commit."
        )

    print(
        "DOWNGRADE PROTECTION PERSISTENCE: OK"
    )


def verify_upgrade_direction() -> None:
    db = SessionLocal()

    try:
        service = ImportIngestService(db)

        print()
        print("=" * 120)
        print("UPGRADE DIRECTION TEST")
        print("=" * 120)

        allowed = (
            service._should_replace_candidate_name(
                RAW_SHEET_NAME,
                ENRICHED_NAME,
            )
        )

        print(
            "upgrade_allowed:",
            allowed,
        )

        if not allowed:
            raise RuntimeError(
                "Importer blocks a genuine "
                "name-quality upgrade."
            )

        print(
            "UPGRADE DIRECTION: OK"
        )

    finally:
        db.rollback()
        db.close()


def main() -> None:
    verify_pure_quality_rules()

    prepare_enriched_state()

    simulate_worse_sheet_import()

    verify_after_import_commit()

    verify_upgrade_direction()

    print()
    print("=" * 120)
    print(
        "IMPORT NAME QUALITY PROTECTION "
        "PERSISTENCE TEST: OK"
    )
    print("=" * 120)

    print()
    print(
        "FINAL CANDIDATE 4 NAME:",
        repr(
            read_name_fresh()
        ),
    )


if __name__ == "__main__":
    main()
