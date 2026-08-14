from __future__ import annotations

import argparse
import asyncio
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func

from app.ai.clients.ollama_client import OllamaClient
from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.services.client_entity_semantic_projection_service import (
    ClientEntitySemanticProjectionService,
)


MODEL = "llama3.2"
MIN_AI_CONFIDENCE = 0.99

REPORT_DIR = Path("/app/test/reports")
DECISIONS_PATH = REPORT_DIR / "client_ai_source_verification_decisions.jsonl"
SUMMARY_PATH = REPORT_DIR / "client_ai_source_verification_summary.json"

EMAIL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?:\+?48[\s./-]*)?(?:\d[\s./-]*){9}"
)

NIP_RE = re.compile(
    r"\b(?:NIP\s*[:\-]?\s*)?([0-9][0-9\s\-]{8,20}[0-9])\b",
    re.IGNORECASE,
)


SYSTEM_MISSION = r"""
MISJA NADRZĘDNA — OSTATECZNA WERYFIKACJA KLIENTÓW AI-LAB

Jesteś konserwatywnym audytorem tożsamości klienta. Nie jesteś generatorem
danych. Twoim zadaniem jest wyłącznie stwierdzić, czy KONKRETNY rekord źródłowy
potwierdza, że rekord z bazy AI-Lab reprezentuje tego samego klienta / tę samą
encję.

ZASADY BEZWZGLĘDNE:

1. Nie wymyślaj brakujących danych.
2. Nie uznawaj podobieństwa tematu, miejscowości, inwestycji ani branży za
   potwierdzenie tożsamości.
3. Firma, instytucja i osoba fizyczna to różne typy encji.
4. Osoba podpisująca e-mail może być tylko KONTAKTEM firmy lub instytucji.
5. W Google Sheets historyczne kolumny IMIĘ / NAZWISKO są semantycznie mieszane.
   Mogą zawierać osobę, firmę, instytucję, oddział, adres, komentarz lub status.
   Interpretuj znaczenie całego wiersza, nie nazwę kolumny.
6. NIP zgodny dokładnie jest bardzo mocnym potwierdzeniem.
7. Dokładnie zgodny e-mail lub telefon jest mocnym potwierdzeniem osoby/kontaktu,
   ale dla organizacji inny e-mail/telefon nie oznacza automatycznie konfliktu,
   bo organizacja może mieć wielu pracowników.
8. Sprzeczny jednoznaczny NIP oznacza CONFLICT.
9. Źródło ma potwierdzać klienta wprost. Jeśli trzeba zgadywać — INSUFFICIENT.
10. Nie zaakceptuj first-party, relay, stopki technicznej, danych KRS/sądu,
    adresu URL, tekstu RODO ani zwykłego zdania jako nazwy klienta.
11. Jeżeli klientem jest organizacja, a źródło potwierdza tylko nazwisko osoby
    bez jawnego związku z organizacją — INSUFFICIENT.
12. Jeżeli źródło jawnie pokazuje organizację oraz osobę kontaktową, możesz
    potwierdzić organizację.
13. SAME_CLIENT z confidence >= 0.99 oznacza: na podstawie tego źródła jesteś
    gotów dopuścić automatyczny zapis do CRM bez ręcznego sprawdzenia.
14. Jeżeli nie masz takiej pewności, nie podnoś confidence sztucznie.

ZWRÓĆ WYŁĄCZNIE JSON:
{
  "verdict": "SAME_CLIENT" | "INSUFFICIENT" | "CONFLICT",
  "confidence": 0.0-1.0,
  "reason": "krótkie konkretne uzasadnienie",
  "matched_fields": ["..."],
  "entity_seen_in_source": "..." | null,
  "contact_seen_in_source": "..." | null
}
""".strip()


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def normalize(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        ch for ch in text
        if not unicodedata.combining(ch)
    )
    text = (
        text
        .replace("Ł", "L")
        .replace("ł", "l")
        .casefold()
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_email(value: Any) -> str:
    value = clean(value).casefold()
    return value if EMAIL_RE.fullmatch(value) else ""


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", clean(value))
    if len(digits) == 11 and digits.startswith("48"):
        digits = digits[2:]
    return digits if len(digits) == 9 else ""


def normalize_nip(value: Any) -> str:
    digits = re.sub(r"\D", "", clean(value))
    return digits if len(digits) == 10 else ""


def flatten_payload(payload: dict[str, Any]) -> str:
    parts: list[str] = []

    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            try:
                rendered = json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            except Exception:
                rendered = str(value)
        else:
            rendered = str(value)

        parts.append(f"{key}: {rendered}")

    return "\n".join(parts)


def extract_identifiers(text: str) -> dict[str, list[str]]:
    emails = sorted({
        match.group(0).strip().casefold()
        for match in EMAIL_RE.finditer(text)
    })

    phones = sorted({
        phone
        for match in PHONE_RE.finditer(text)
        if (phone := normalize_phone(match.group(0)))
    })

    nips: set[str] = set()

    for match in NIP_RE.finditer(text):
        value = normalize_nip(match.group(1))
        if value:
            nips.add(value)

    return {
        "emails": emails,
        "phones": sorted(phones),
        "nips": sorted(nips),
    }


def candidate_snapshot(
    candidate: ClientCandidate,
    projection,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.id,
        "candidate_status": candidate.status,
        "candidate_type": candidate.client_type,
        "candidate_name": candidate.name,
        "candidate_legal_name": candidate.legal_name,
        "candidate_tax_id": candidate.tax_id,
        "candidate_email": candidate.primary_email,
        "candidate_phone": candidate.primary_phone,
        "candidate_city": candidate.city,
        "projection_entity_name": projection.entity_name,
        "projection_entity_type": projection.entity_type,
        "projection_legal_name": projection.legal_name,
        "projection_tax_id": projection.tax_id,
        "projection_contact_name": projection.contact_name,
        "projection_contact_email": projection.contact_email,
        "projection_contact_phone": projection.contact_phone,
        "projection_units": projection.organizational_units,
        "projection_status": projection.status,
        "projection_reason": projection.reason,
    }


def hard_nip_conflict(
    candidate: ClientCandidate,
    projection,
    source_ids: dict[str, list[str]],
) -> bool:
    db_nips = {
        value
        for raw in (
            candidate.tax_id,
            projection.tax_id,
        )
        if (value := normalize_nip(raw))
    }

    src_nips = set(source_ids["nips"])

    return bool(
        db_nips
        and src_nips
        and db_nips.isdisjoint(src_nips)
    )


def deterministic_support(
    candidate: ClientCandidate,
    projection,
    source_text: str,
    source_ids: dict[str, list[str]],
) -> list[str]:
    support: list[str] = []

    db_nip = normalize_nip(
        projection.tax_id
        or candidate.tax_id
    )

    if db_nip and db_nip in source_ids["nips"]:
        support.append("exact_nip")

    db_emails = {
        value
        for raw in (
            candidate.primary_email,
            projection.contact_email,
        )
        if (value := normalize_email(raw))
    }

    if db_emails.intersection(source_ids["emails"]):
        support.append("exact_email")

    db_phones = {
        value
        for raw in (
            candidate.primary_phone,
            projection.contact_phone,
        )
        if (value := normalize_phone(raw))
    }

    if db_phones.intersection(source_ids["phones"]):
        support.append("exact_phone")

    source_norm = normalize(source_text)

    for label, raw in (
        ("projection_entity_name", projection.entity_name),
        ("candidate_name", candidate.name),
        ("projection_contact_name", projection.contact_name),
    ):
        value = normalize(raw)
        if len(value) >= 4 and value in source_norm:
            support.append(label)

    return sorted(set(support))


def source_priority_label(source_type: str) -> str:
    if source_type == "google_sheets_row":
        return "GOOGLE_SHEETS_PRIMARY"
    return "GMAIL_FALLBACK"


def build_prompt(
    *,
    candidate: ClientCandidate,
    projection,
    source: CandidateSource,
    source_text: str,
    deterministic: list[str],
) -> str:
    snap = candidate_snapshot(
        candidate,
        projection,
    )

    payload = {
        "mission": SYSTEM_MISSION,
        "source_priority": source_priority_label(
            source.source_type
        ),
        "database_and_projection": snap,
        "deterministic_support": deterministic,
        "source_id": source.id,
        "source_type": source.source_type,
        "source_record": source_text[:12000],
    }

    return (
        SYSTEM_MISSION
        + "\n\nDANE DO OCENY:\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


async def ai_judge(
    client: OllamaClient,
    prompt: str,
) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": [
                    "SAME_CLIENT",
                    "INSUFFICIENT",
                    "CONFLICT",
                ],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "reason": {
                "type": "string",
            },
            "matched_fields": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "entity_seen_in_source": {
                "type": [
                    "string",
                    "null",
                ],
            },
            "contact_seen_in_source": {
                "type": [
                    "string",
                    "null",
                ],
            },
        },
        "required": [
            "verdict",
            "confidence",
            "reason",
            "matched_fields",
            "entity_seen_in_source",
            "contact_seen_in_source",
        ],
    }

    response = await client.generate(
        model=MODEL,
        prompt=prompt,
        stream=False,
        format=schema,
    )

    raw = response.get("response")

    if not raw:
        raise RuntimeError(
            "Ollama returned empty response."
        )

    return json.loads(raw)


def gmail_source_text(payload: dict[str, Any]) -> str:
    selected: dict[str, Any] = {}

    for key in (
        "from",
        "to",
        "cc",
        "subject",
        "text",
        "textPlain",
        "snippet",
    ):
        if key in payload:
            selected[key] = payload[key]

    return flatten_payload(selected)


def source_text(source: CandidateSource) -> str:
    payload = source.raw_payload or {}

    if source.source_type == "google_sheets_row":
        return flatten_payload(payload)

    if source.source_type == "gmail_message":
        return gmail_source_text(payload)

    return ""


def already_has_decision(candidate_id: int) -> bool:
    if not DECISIONS_PATH.exists():
        return False

    with DECISIONS_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            if row.get("candidate_id") == candidate_id:
                if row.get("final_verdict") in {
                    "ACCEPTED",
                    "MERGED",
                    "REVIEW",
                    "CONFLICT",
                    "ERROR",
                }:
                    return True

    return False


def append_decision(data: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DECISIONS_PATH.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                data,
                ensure_ascii=False,
            )
            + "\n"
        )


def find_existing_client(
    db,
    *,
    tax_id: str | None,
    email: str | None,
    phone: str | None,
) -> tuple[Client | None, str | None]:
    nip = normalize_nip(tax_id)

    if nip:
        client = (
            db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                func.regexp_replace(
                    Client.tax_id,
                    r"\D",
                    "",
                    "g",
                ) == nip,
            )
            .first()
        )

        if client is not None:
            return client, "tax_id"

    normalized_email_value = normalize_email(email)

    if normalized_email_value:
        client = (
            db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                func.lower(
                    func.trim(
                        Client.primary_email
                    )
                ) == normalized_email_value,
            )
            .first()
        )

        if client is not None:
            return client, "email"

    normalized_phone_value = normalize_phone(phone)

    if normalized_phone_value:
        clients = (
            db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                Client.primary_phone.isnot(None),
            )
            .all()
        )

        matches = [
            client
            for client in clients
            if normalize_phone(
                client.primary_phone
            ) == normalized_phone_value
        ]

        if len(matches) == 1:
            return matches[0], "phone"

    return None, None


def assign_documents(
    db,
    *,
    candidate: ClientCandidate,
    client: Client,
    method: str,
) -> None:
    now = datetime.now(
        timezone.utc
    )

    documents = (
        db.query(Document)
        .filter(
            Document.candidate_id
            == candidate.id
        )
        .all()
    )

    for document in documents:
        if (
            document.client_id is not None
            and document.client_id != client.id
        ):
            raise RuntimeError(
                f"Document {document.id} already belongs "
                f"to client {document.client_id}."
            )

        document.client_id = client.id

        if document.match_status in {
            "unmatched",
            "suggested",
            "matched",
        }:
            document.match_status = "confirmed"

        document.match_confidence = 1.0
        document.match_method = method
        document.matched_at = now


def persist_verified_candidate(
    db,
    *,
    candidate: ClientCandidate,
    projection,
    verified_by: str,
) -> tuple[str, int]:
    entity_name = clean(
        projection.entity_name
        or candidate.name
    )

    if not entity_name:
        raise RuntimeError(
            "No usable entity name after verification."
        )

    entity_type = (
        projection.entity_type
        if projection.entity_type in {
            "company",
            "person",
            "institution",
            "other",
        }
        else candidate.client_type
    )

    tax_id = (
        projection.tax_id
        or candidate.tax_id
    )

    email = (
        projection.contact_email
        or candidate.primary_email
    )

    phone = (
        projection.contact_phone
        or candidate.primary_phone
    )

    existing, matched_by = find_existing_client(
        db,
        tax_id=tax_id,
        email=email,
        phone=phone,
    )

    if existing is not None:
        candidate.status = "merged"
        candidate.matched_client_id = existing.id

        assign_documents(
            db,
            candidate=candidate,
            client=existing,
            method=(
                "ai_source_verified_merge_"
                + verified_by
            ),
        )

        db.flush()

        return (
            f"MERGED:{matched_by}",
            existing.id,
        )

    client = Client(
        client_type=entity_type,
        name=entity_name,
        legal_name=(
            projection.legal_name
            or candidate.legal_name
        ),
        tax_id=tax_id,
        registration_number=candidate.registration_number,
        industry_id=candidate.industry_id,
        website=candidate.website,
        primary_email=email,
        primary_phone=phone,
        street=candidate.street,
        building_number=candidate.building_number,
        unit_number=candidate.unit_number,
        postal_code=candidate.postal_code,
        city=candidate.city,
        country_code=(
            candidate.country_code
            or "PL"
        ),
        notes=candidate.notes,
    )

    db.add(client)
    db.flush()

    candidate.status = "accepted"
    candidate.matched_client_id = client.id

    assign_documents(
        db,
        candidate=candidate,
        client=client,
        method=(
            "ai_source_verified_accept_"
            + verified_by
        ),
    )

    db.flush()

    return "ACCEPTED", client.id


async def evaluate_source(
    *,
    ollama: OllamaClient,
    candidate: ClientCandidate,
    projection,
    source: CandidateSource,
) -> dict[str, Any]:
    text = source_text(source)
    ids = extract_identifiers(text)

    if hard_nip_conflict(
        candidate,
        projection,
        ids,
    ):
        return {
            "source_id": source.id,
            "source_type": source.source_type,
            "verdict": "CONFLICT",
            "confidence": 1.0,
            "reason": "Hard NIP conflict detected deterministically.",
            "matched_fields": [],
            "deterministic_support": [],
            "entity_seen_in_source": None,
            "contact_seen_in_source": None,
        }

    support = deterministic_support(
        candidate,
        projection,
        text,
        ids,
    )

    decision = await ai_judge(
        ollama,
        build_prompt(
            candidate=candidate,
            projection=projection,
            source=source,
            source_text=text,
            deterministic=support,
        ),
    )

    decision.update({
        "source_id": source.id,
        "source_type": source.source_type,
        "deterministic_support": support,
    })

    return decision


def auto_accept_allowed(
    decision: dict[str, Any],
) -> bool:
    if decision.get("verdict") != "SAME_CLIENT":
        return False

    try:
        confidence = float(
            decision.get("confidence", 0.0)
        )
    except Exception:
        return False

    if confidence < MIN_AI_CONFIDENCE:
        return False

    deterministic = set(
        decision.get(
            "deterministic_support",
            [],
        )
    )

    # AI must never be the only basis for a write.
    return bool(
        deterministic.intersection({
            "exact_nip",
            "exact_email",
            "exact_phone",
            "projection_entity_name",
            "candidate_name",
            "projection_contact_name",
        })
    )


async def process_candidate(
    *,
    db,
    ollama: OllamaClient,
    candidate: ClientCandidate,
    apply: bool,
) -> dict[str, Any]:
    projection_service = (
        ClientEntitySemanticProjectionService(
            db
        )
    )

    projection = projection_service.project(
        candidate
    )

    if projection.status in {
        "first_party_internal",
        "relay_container",
    }:
        return {
            "candidate_id": candidate.id,
            "final_verdict": "REVIEW",
            "verified_by": None,
            "reason": projection.status,
            "projection": candidate_snapshot(
                candidate,
                projection,
            ),
            "source_decisions": [],
        }

    sources = (
        db.query(CandidateSource)
        .filter(
            CandidateSource.candidate_id == candidate.id,
            CandidateSource.deleted_at.is_(None),
        )
        .order_by(
            CandidateSource.created_at.asc(),
            CandidateSource.id.asc(),
        )
        .all()
    )

    sheets = [
        source
        for source in sources
        if source.source_type == "google_sheets_row"
    ]

    gmail = [
        source
        for source in sources
        if source.source_type == "gmail_message"
    ]

    source_decisions: list[dict[str, Any]] = []

    # PHASE 1: Google Sheets. Gmail is forbidden until Sheets fails.
    for source in sheets:
        decision = await evaluate_source(
            ollama=ollama,
            candidate=candidate,
            projection=projection,
            source=source,
        )

        source_decisions.append(
            decision
        )

        if decision["verdict"] == "CONFLICT":
            return {
                "candidate_id": candidate.id,
                "final_verdict": "CONFLICT",
                "verified_by": "google_sheets",
                "reason": decision["reason"],
                "projection": candidate_snapshot(
                    candidate,
                    projection,
                ),
                "source_decisions": source_decisions,
            }

        if auto_accept_allowed(
            decision
        ):
            if not apply:
                return {
                    "candidate_id": candidate.id,
                    "final_verdict": "WOULD_ACCEPT",
                    "verified_by": "google_sheets",
                    "reason": decision["reason"],
                    "projection": candidate_snapshot(
                        candidate,
                        projection,
                    ),
                    "source_decisions": source_decisions,
                }

            outcome, client_id = (
                persist_verified_candidate(
                    db,
                    candidate=candidate,
                    projection=projection,
                    verified_by="google_sheets",
                )
            )

            db.commit()

            return {
                "candidate_id": candidate.id,
                "final_verdict": (
                    "MERGED"
                    if outcome.startswith("MERGED")
                    else "ACCEPTED"
                ),
                "persist_outcome": outcome,
                "client_id": client_id,
                "verified_by": "google_sheets",
                "reason": decision["reason"],
                "projection": candidate_snapshot(
                    candidate,
                    projection,
                ),
                "source_decisions": source_decisions,
            }

    # PHASE 2: Gmail fallback only because Sheets did not confirm.
    for source in gmail:
        decision = await evaluate_source(
            ollama=ollama,
            candidate=candidate,
            projection=projection,
            source=source,
        )

        source_decisions.append(
            decision
        )

        if decision["verdict"] == "CONFLICT":
            continue

        if auto_accept_allowed(
            decision
        ):
            if not apply:
                return {
                    "candidate_id": candidate.id,
                    "final_verdict": "WOULD_ACCEPT",
                    "verified_by": "gmail",
                    "reason": decision["reason"],
                    "projection": candidate_snapshot(
                        candidate,
                        projection,
                    ),
                    "source_decisions": source_decisions,
                }

            outcome, client_id = (
                persist_verified_candidate(
                    db,
                    candidate=candidate,
                    projection=projection,
                    verified_by="gmail",
                )
            )

            db.commit()

            return {
                "candidate_id": candidate.id,
                "final_verdict": (
                    "MERGED"
                    if outcome.startswith("MERGED")
                    else "ACCEPTED"
                ),
                "persist_outcome": outcome,
                "client_id": client_id,
                "verified_by": "gmail",
                "reason": decision["reason"],
                "projection": candidate_snapshot(
                    candidate,
                    projection,
                ),
                "source_decisions": source_decisions,
            }

    return {
        "candidate_id": candidate.id,
        "final_verdict": "REVIEW",
        "verified_by": None,
        "reason": (
            "No >=99% source-backed confirmation. "
            "Sheets checked before Gmail."
        ),
        "projection": candidate_snapshot(
            candidate,
            projection,
        ),
        "source_decisions": source_decisions,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=[
            "dry-run",
            "apply",
        ],
        default="dry-run",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    args = parser.parse_args()

    apply = args.mode == "apply"

    db = SessionLocal()
    ollama = OllamaClient()

    counts = {
        "processed": 0,
        "accepted": 0,
        "merged": 0,
        "would_accept": 0,
        "review": 0,
        "conflict": 0,
        "error": 0,
        "verified_by_google_sheets": 0,
        "verified_by_gmail": 0,
    }

    started_at = datetime.now(
        timezone.utc
    )

    try:
        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.status == "pending",
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.matched_client_id.is_(None),
            )
            .order_by(
                ClientCandidate.id.asc()
            )
            .all()
        )

        if args.limit > 0:
            candidates = candidates[
                :args.limit
            ]

        print("=" * 100)
        print("AI-LAB CLIENT SOURCE VERIFICATION")
        print("=" * 100)
        print("mode:", args.mode)
        print("model:", MODEL)
        print(
            "minimum_ai_confidence:",
            MIN_AI_CONFIDENCE,
        )
        print(
            "candidate_count:",
            len(candidates),
        )
        print(
            "priority:",
            "GOOGLE SHEETS -> GMAIL FALLBACK",
        )
        print(
            "write_rule:",
            "AI >= 0.99 AND deterministic source support",
        )
        print("=" * 100)

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            if (
                args.resume
                and already_has_decision(
                    candidate.id
                )
            ):
                print(
                    f"[{index}/{len(candidates)}] "
                    f"{candidate.id}: SKIP RESUME"
                )
                continue

            try:
                result = await process_candidate(
                    db=db,
                    ollama=ollama,
                    candidate=candidate,
                    apply=apply,
                )

                verdict = result[
                    "final_verdict"
                ]

            except Exception as exc:
                db.rollback()

                result = {
                    "candidate_id": candidate.id,
                    "final_verdict": "ERROR",
                    "verified_by": None,
                    "reason": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    "source_decisions": [],
                }

                verdict = "ERROR"

            counts["processed"] += 1

            key_map = {
                "ACCEPTED": "accepted",
                "MERGED": "merged",
                "WOULD_ACCEPT": "would_accept",
                "REVIEW": "review",
                "CONFLICT": "conflict",
                "ERROR": "error",
            }

            key = key_map.get(
                verdict
            )

            if key:
                counts[key] += 1

            verified_by = result.get(
                "verified_by"
            )

            if verified_by == "google_sheets":
                counts[
                    "verified_by_google_sheets"
                ] += 1

            if verified_by == "gmail":
                counts[
                    "verified_by_gmail"
                ] += 1

            result["mode"] = args.mode
            result["timestamp"] = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            append_decision(
                result
            )

            print(
                f"[{index}/{len(candidates)}] "
                f"candidate={candidate.id} "
                f"verdict={verdict} "
                f"source={verified_by or '-'}"
            )

        finished_at = datetime.now(
            timezone.utc
        )

        summary = {
            "mode": args.mode,
            "model": MODEL,
            "minimum_ai_confidence": (
                MIN_AI_CONFIDENCE
            ),
            "priority": (
                "google_sheets_then_gmail"
            ),
            "started_at": (
                started_at.isoformat()
            ),
            "finished_at": (
                finished_at.isoformat()
            ),
            "counts": counts,
        }

        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        SUMMARY_PATH.write_text(
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print()
        print("=" * 100)
        print("SUMMARY")
        print("=" * 100)

        print(
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            )
        )

        print()
        print(
            "DECISIONS:",
            DECISIONS_PATH,
        )

        print(
            "SUMMARY:",
            SUMMARY_PATH,
        )

        if not apply:
            print()
            print(
                "DATABASE WRITES: 0 "
                "(dry-run mode)"
            )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
