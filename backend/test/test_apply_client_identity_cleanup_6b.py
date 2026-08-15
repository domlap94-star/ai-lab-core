from __future__ import annotations

import inspect
from copy import deepcopy
from types import SimpleNamespace

from test.apply_client_identity_cleanup_6b import (
    APPROVAL_SCOPE,
    EXPECTED_CLIENT_IDS,
    ApprovedRename,
    ControlledApplyError,
    assign_approved_names,
    execute,
    validate_approval_manifest,
    validate_client_rows,
    validate_dry_run_proposals,
    validate_quality_delta,
    validate_snapshot_diff,
)


OLD_NAMES = (
    "old-39",
    "old-113",
    "old-1912",
    "old-1915",
    "old-2269",
    "old-2282",
)
NEW_NAMES = (
    "new-39",
    "new-113",
    "new-1912",
    "new-1915",
    "new-2269",
    "new-2282",
)


def approvals():
    return [
        ApprovedRename(client_id, old, new)
        for client_id, old, new in zip(
            EXPECTED_CLIENT_IDS,
            OLD_NAMES,
            NEW_NAMES,
            strict=True,
        )
    ]


def clients():
    return [
        SimpleNamespace(
            id=item.client_id,
            name=item.expected_old_name,
            client_type="other",
            legal_name=None,
            primary_email="unchanged@example.com",
            primary_phone="500 000 000",
            tax_id=None,
            street=None,
            building_number=None,
            unit_number=None,
            postal_code=None,
            city=None,
            country_code="PL",
            notes="unchanged",
            deleted_at=None,
            updated_at=None,
        )
        for item in approvals()
    ]


def proposals():
    return [
        SimpleNamespace(
            client_id=item.client_id,
            action="SAFE_RENAME_CANDIDATE",
            proposed_name=item.approved_new_name,
            duplicate_risk="NONE",
            identity_support_evidence=[SimpleNamespace(source_id=1)],
            conflicts=[],
        )
        for item in approvals()
    ]


def expect_rejected(callback, phrase: str) -> None:
    try:
        callback()
    except ControlledApplyError as error:
        assert phrase in str(error)
    else:
        raise AssertionError("Controlled apply validation unexpectedly passed")


def manifest_payload():
    return {
        "approval_scope": APPROVAL_SCOPE,
        "approved_count": 6,
        "records": [
            {
                "client_id": item.client_id,
                "expected_old_name": item.expected_old_name,
                "approved_new_name": item.approved_new_name,
            }
            for item in approvals()
        ],
    }


def snapshot(rows):
    records = []
    for client in rows:
        records.append(
            {
                "client_id": client.id,
                "name": client.name,
                "client_type": client.client_type,
                "legal_name": client.legal_name,
                "primary_email": client.primary_email,
                "primary_phone": client.primary_phone,
                "tax_id": client.tax_id,
                "street": client.street,
                "building_number": client.building_number,
                "unit_number": client.unit_number,
                "postal_code": client.postal_code,
                "city": client.city,
                "country_code": client.country_code,
                "notes_state": "value",
                "notes_sha256": "stable",
                "deleted_at": None,
                "updated_at": None,
            }
        )
    return {
        "records": records,
        "relationships": {str(client.id): {"stable": True} for client in rows},
        "hold_names": {"13": "hold"},
    }


def main() -> None:
    payload = manifest_payload()
    assert len(validate_approval_manifest(payload)) == 6

    wrong_count = deepcopy(payload)
    wrong_count["approved_count"] = 5
    expect_rejected(
        lambda: validate_approval_manifest(wrong_count),
        "count must equal six",
    )

    unexpected_id = deepcopy(payload)
    unexpected_id["records"][5]["client_id"] = 9999
    expect_rejected(
        lambda: validate_approval_manifest(unexpected_id),
        "unexpected client IDs",
    )

    mismatched_clients = clients()
    mismatched_clients[5].name = "changed independently"
    expect_rejected(
        lambda: validate_client_rows(approvals(), mismatched_clients),
        "OLD name mismatch",
    )

    inactive_clients = clients()
    inactive_clients[0].deleted_at = "deleted"
    expect_rejected(
        lambda: validate_client_rows(approvals(), inactive_clients),
        "not active",
    )

    mismatched_proposals = proposals()
    mismatched_proposals[0].proposed_name = "different proposal"
    expect_rejected(
        lambda: validate_dry_run_proposals(approvals(), mismatched_proposals),
        "proposed name mismatch",
    )

    duplicate_proposals = proposals()
    duplicate_proposals[0].duplicate_risk = "POSSIBLE"
    expect_rejected(
        lambda: validate_dry_run_proposals(approvals(), duplicate_proposals),
        "duplicate risk is not NONE",
    )

    # Validation is performed for all six before the first assignment.
    atomic_clients = clients()
    atomic_clients[5].name = "precondition failure"
    original_names = [client.name for client in atomic_clients]
    expect_rejected(
        lambda: assign_approved_names(approvals(), atomic_clients),
        "OLD name mismatch",
    )
    assert [client.name for client in atomic_clients] == original_names

    successful_clients = clients()
    seventh = SimpleNamespace(name="unrelated")
    before = snapshot(successful_clients)
    unchanged_fields = [
        (client.client_type, client.primary_email, client.notes)
        for client in successful_clients
    ]
    assign_approved_names(approvals(), successful_clients)
    assert [client.name for client in successful_clients] == list(NEW_NAMES)
    assert seventh.name == "unrelated"
    assert [
        (client.client_type, client.primary_email, client.notes)
        for client in successful_clients
    ] == unchanged_fields
    after = snapshot(successful_clients)
    validate_snapshot_diff(before, after)

    changed_type = deepcopy(after)
    changed_type["records"][0]["client_type"] = "person"
    expect_rejected(
        lambda: validate_snapshot_diff(before, changed_type),
        "client_type",
    )

    before_quality = {
        "active_clients": 100,
        "email_as_name": 1,
        "phone_as_name": 5,
        "file_as_name": 0,
        "suspicious_unique": 6,
    }
    after_quality = {
        "active_clients": 100,
        "email_as_name": 0,
        "phone_as_name": 0,
        "file_as_name": 0,
        "suspicious_unique": 0,
    }
    real_shape_approvals = [
        ApprovedRename(39, "old@example.com", "Person One"),
        ApprovedRename(113, "500 000 001", "Person Two"),
        ApprovedRename(1912, "500 000 002", "Person Three"),
        ApprovedRename(1915, "500 000 003", "Person Four"),
        ApprovedRename(2269, "500 000 004", "Person Five"),
        ApprovedRename(2282, "500 000 005", "Company Six"),
    ]
    validate_quality_delta(
        before_quality,
        after_quality,
        real_shape_approvals,
    )
    anomalous_quality = dict(after_quality)
    anomalous_quality["phone_as_name"] = 1
    expect_rejected(
        lambda: validate_quality_delta(
            before_quality,
            anomalous_quality,
            real_shape_approvals,
        ),
        "quality delta",
    )

    assert inspect.signature(execute).parameters["apply"].default is False

    print("CONTROLLED CLIENT IDENTITY APPLY TESTS: OK")
    print("default invocation: dry-run")
    print("production database modifications: 0")


if __name__ == "__main__":
    main()
