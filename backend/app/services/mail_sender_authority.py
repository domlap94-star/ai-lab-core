from __future__ import annotations

from email.utils import getaddresses
from typing import Any

from app.services.ignored_mail_source_service import EMAIL_RE


def canonical_mail_addresses(value: Any) -> list[tuple[str | None, str]]:
    """Return strict, source-authored mailboxes without identity inference."""

    candidates: list[tuple[str, str]] = []

    def collect(item: Any) -> None:
        if isinstance(item, dict):
            direct_address = item.get("address")
            if direct_address is not None:
                candidates.append(
                    (str(item.get("name") or ""), str(direct_address))
                )
            entries = item.get("value")
            if isinstance(entries, list):
                for entry in entries:
                    collect(entry)
            text_value = item.get("text")
            if text_value:
                candidates.extend(getaddresses([str(text_value)]))
        elif isinstance(item, list):
            for entry in item:
                collect(entry)
        elif item:
            candidates.extend(getaddresses([str(item)]))

    collect(value)
    result: list[tuple[str | None, str]] = []
    seen: set[str] = set()
    for raw_name, raw_address in candidates:
        address = raw_address.strip().lower()
        if not EMAIL_RE.fullmatch(address) or address in seen:
            continue
        seen.add(address)
        name = " ".join(raw_name.split()).strip() or None
        result.append((name, address))
    return result


def canonical_mail_sender(value: Any) -> tuple[str | None, str] | None:
    addresses = canonical_mail_addresses(value)
    return addresses[0] if addresses else None
