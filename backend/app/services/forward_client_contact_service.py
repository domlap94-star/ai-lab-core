from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.models.client import Client
from app.models.client_contact_point import ClientContactPoint
from app.services.forward_source_ingestion_service import (
    CONTACT_METADATA_KEY,
    ForwardSourceIngestionService,
)


class ForwardClientContactService:
    """Append validated contacts without weakening an existing primary."""

    @classmethod
    def add_from_payloads(
        cls,
        client: Client,
        payloads: Iterable[dict[str, Any] | None],
    ) -> int:
        incoming = {"email": [], "phone": []}
        for payload in payloads:
            metadata = (payload or {}).get(CONTACT_METADATA_KEY)
            if not isinstance(metadata, dict):
                continue
            for kind, key in (("email", "emails"), ("phone", "phones")):
                values = metadata.get(key)
                if isinstance(values, list):
                    incoming[kind].extend(
                        value for value in values if isinstance(value, str)
                    )

        added = 0
        for kind, values in incoming.items():
            existing = [item for item in client.contact_points if item.kind == kind]
            normalized_existing = {item.normalized_value for item in existing}
            has_primary = any(item.is_primary for item in existing)
            scalar_name = "primary_email" if kind == "email" else "primary_phone"
            scalar = getattr(client, scalar_name)

            if scalar and not existing:
                normalized = cls._normalize(kind, scalar)
                if normalized:
                    client.contact_points.append(
                        ClientContactPoint(
                            kind=kind,
                            value=scalar.strip(),
                            normalized_value=normalized,
                            is_primary=True,
                            position=0,
                        )
                    )
                    existing = [client.contact_points[-1]]
                    normalized_existing.add(normalized)
                    has_primary = True

            for value in values:
                normalized = cls._normalize(kind, value)
                if not normalized or normalized in normalized_existing:
                    continue
                is_primary = not has_primary
                client.contact_points.append(
                    ClientContactPoint(
                        kind=kind,
                        value=value.strip(),
                        normalized_value=normalized,
                        is_primary=is_primary,
                        position=len(existing),
                    )
                )
                existing.append(client.contact_points[-1])
                normalized_existing.add(normalized)
                added += 1
                if is_primary:
                    setattr(client, scalar_name, value.strip())
                    has_primary = True
        return added

    @staticmethod
    def _normalize(kind: str, value: str) -> str:
        if kind == "email":
            return ForwardSourceIngestionService.normalize_email(value)
        return ForwardSourceIngestionService.normalize_phone(value)
