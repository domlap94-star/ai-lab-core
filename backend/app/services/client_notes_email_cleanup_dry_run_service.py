from __future__ import annotations

import hashlib
import html
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.repositories.client_email_repository import LINKED_CANDIDATE_STATUSES
from app.services.client_email_service import ClientEmailService


CleanupClassification = Literal[
    "SAFE_REMOVE_TRANSCRIPT_ONLY",
    "SAFE_CLEAR_NOTES",
    "REVIEW_REQUIRED",
    "BLOCKED_NO_SOURCE_HISTORY",
    "NO_CHANGE",
]
SourceMatchStatus = Literal[
    "CONFIRMED_SOURCE_MATCH",
    "STRUCTURE_CONFIRMED_BUT_MESSAGE_NOT_UNIQUE",
    "NO_SOURCE_MATCH",
    "AMBIGUOUS",
]

TRANSCRIPT_MARKER = "Kierunek wiadomości:"
MARKER_LABELS = (
    "Kierunek wiadomości",
    "Temat wiadomości",
    "Data wiadomości",
    "Treść wiadomości",
)
_MARKER_RE = re.compile(
    r"^(Kierunek wiadomości|Temat wiadomości|Data wiadomości|Treść wiadomości):(.*)$",
    re.IGNORECASE,
)
_PARAGRAPH_SEPARATOR_RE = re.compile(r"((?:\r?\n)[ \t]*(?:\r?\n)+)")
_EMAIL_RE = re.compile(r"(?i)\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_NUMBER_RE = re.compile(r"\d")
_VALID_SIGNATURES = {
    (
        "Kierunek wiadomości",
        "Temat wiadomości",
        "Data wiadomości",
        "Treść wiadomości",
    ),
    (
        "Kierunek wiadomości",
        "Temat wiadomości",
        "Data wiadomości",
    ),
    (
        "Kierunek wiadomości",
        "Data wiadomości",
        "Treść wiadomości",
    ),
    ("Kierunek wiadomości", "Data wiadomości"),
}


def notes_sha256(value: str | None) -> str:
    payload = b"CLIENT_NOTES_NULL" if value is None else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class LegacyTranscriptBlock:
    direction: Literal["sent", "received"]
    subject: str | None
    message_at: datetime
    body: str | None
    signature: tuple[str, ...]
    character_count: int


@dataclass(frozen=True)
class ParsedLegacyNotes:
    blocks: tuple[LegacyTranscriptBlock, ...]
    proposed_notes: str | None
    has_manual_content: bool
    ambiguous: bool
    separator_patterns: tuple[str, ...]
    transcript_positions: tuple[str, ...]


@dataclass(frozen=True)
class SourceMessage:
    source_id: int
    direction: str
    message_at: datetime | None
    subject: str | None
    body: str | None


@dataclass(frozen=True)
class ClientNotesCleanupProposal:
    client_id: int
    before_length: int
    before_sha256: str
    classification: CleanupClassification
    removed_block_count: int
    removed_character_count: int
    preserved_character_count: int
    proposed_notes: str | None
    proposed_notes_sha256: str
    source_match_statuses: tuple[SourceMatchStatus, ...]
    marker_signatures: tuple[tuple[str, ...], ...]
    manual_excerpt: str | None
    has_manual_content: bool
    boundary_ambiguous: bool
    transcript_positions: tuple[str, ...]

    def report_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["source_match_statuses"] = list(self.source_match_statuses)
        record["marker_signatures"] = [list(item) for item in self.marker_signatures]
        record["transcript_positions"] = list(self.transcript_positions)
        return record


class LegacyEmailNotesParser:
    @classmethod
    def parse(cls, notes: str) -> ParsedLegacyNotes:
        parts = _PARAGRAPH_SEPARATOR_RE.split(notes)
        paragraph_indexes = list(range(0, len(parts), 2))
        blocks_by_index: dict[int, LegacyTranscriptBlock] = {}
        ambiguous = False
        separator_patterns = tuple(
            cls._separator_pattern(parts[index])
            for index in range(1, len(parts), 2)
        )

        for index in paragraph_indexes:
            paragraph = parts[index]
            block = cls._parse_paragraph(paragraph)
            if block is not None:
                blocks_by_index[index] = block
            elif cls._contains_direction_marker(paragraph):
                ambiguous = True

        kept_indexes = [
            index
            for index in paragraph_indexes
            if index not in blocks_by_index and parts[index] != ""
        ]
        proposed = cls._reconstruct_kept(parts, kept_indexes)
        positions = []
        for index in sorted(blocks_by_index):
            manual_before = any(item < index for item in kept_indexes)
            manual_after = any(item > index for item in kept_indexes)
            if manual_before and manual_after:
                positions.append("between_manual_content")
            elif manual_before:
                positions.append("at_end")
            elif manual_after:
                positions.append("at_start")
            else:
                positions.append("transcript_only")
        return ParsedLegacyNotes(
            blocks=tuple(blocks_by_index[index] for index in sorted(blocks_by_index)),
            proposed_notes=proposed,
            has_manual_content=bool(proposed and proposed.strip()),
            ambiguous=ambiguous,
            separator_patterns=separator_patterns,
            transcript_positions=tuple(positions),
        )

    @staticmethod
    def _contains_direction_marker(paragraph: str) -> bool:
        return any(
            line.casefold().startswith(TRANSCRIPT_MARKER.casefold())
            for line in paragraph.splitlines()
        )

    @classmethod
    def _parse_paragraph(cls, paragraph: str) -> LegacyTranscriptBlock | None:
        lines = paragraph.splitlines()
        if not lines:
            return None
        fields: list[tuple[str, str]] = []
        for line in lines:
            match = _MARKER_RE.fullmatch(line)
            if match is None:
                return None
            label = cls._canonical_label(match.group(1))
            value = match.group(2).strip()
            if not value:
                return None
            fields.append((label, value))
        signature = tuple(label for label, _ in fields)
        if signature not in _VALID_SIGNATURES:
            return None

        values = dict(fields)
        direction = cls._direction(values["Kierunek wiadomości"])
        message_at = cls._message_at(values["Data wiadomości"])
        if direction is None or message_at is None:
            return None
        return LegacyTranscriptBlock(
            direction=direction,
            subject=values.get("Temat wiadomości"),
            message_at=message_at,
            body=values.get("Treść wiadomości"),
            signature=signature,
            character_count=len(paragraph),
        )

    @staticmethod
    def _canonical_label(value: str) -> str:
        folded = value.casefold()
        return next(label for label in MARKER_LABELS if label.casefold() == folded)

    @staticmethod
    def _direction(value: str) -> Literal["sent", "received"] | None:
        normalized = value.casefold()
        if normalized == "wysłana":
            return "sent"
        if normalized == "odebrana":
            return "received"
        return None

    @staticmethod
    def _message_at(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _separator_pattern(value: str) -> str:
        line_breaks = value.count("\n")
        return f"blank_lines:{max(1, line_breaks - 1)}"

    @staticmethod
    def _reconstruct_kept(parts: list[str], kept_indexes: list[int]) -> str | None:
        if not kept_indexes:
            return None
        result = parts[kept_indexes[0]]
        previous = kept_indexes[0]
        for current in kept_indexes[1:]:
            separators = [
                parts[index]
                for index in range(previous + 1, current, 2)
                if parts[index]
            ]
            result += (separators[0] if separators else "\n\n") + parts[current]
            previous = current
        return result if result.strip() else None


class ClientNotesEmailCleanupDryRunService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.email_normalizer = ClientEmailService(db)

    def run(self) -> tuple[list[ClientNotesCleanupProposal], dict[str, Any]]:
        clients = (
            self.db.query(Client.id, Client.notes)
            .filter(Client.deleted_at.is_(None))
            .order_by(Client.id.asc())
            .all()
        )
        active_ids = [client.id for client in clients]
        messages_by_client = self._source_messages(active_ids)
        proposals: list[ClientNotesCleanupProposal] = []
        false_positive_phrase_notes = 0
        format_variants: Counter[tuple[str, ...]] = Counter()
        separators: Counter[str] = Counter()
        marker_coverage: Counter[str] = Counter()
        block_counts: Counter[int] = Counter()

        notes_not_null = 0
        notes_nonempty = 0
        transcript_like = 0
        for client in clients:
            notes = client.notes
            if notes is not None:
                notes_not_null += 1
            if notes is None or not notes.strip():
                continue
            notes_nonempty += 1
            if TRANSCRIPT_MARKER.casefold() not in notes.casefold():
                if self._contains_marker_phrase(notes):
                    false_positive_phrase_notes += 1
                continue

            transcript_like += 1
            parsed = LegacyEmailNotesParser.parse(notes)
            for block in parsed.blocks:
                format_variants[block.signature] += 1
                marker_coverage.update(block.signature)
            separators.update(parsed.separator_patterns)
            block_counts[len(parsed.blocks)] += 1
            proposals.append(
                self._proposal(
                    client_id=client.id,
                    notes=notes,
                    parsed=parsed,
                    messages=messages_by_client.get(client.id, []),
                )
            )

        summary = self._summary(
            proposals=proposals,
            active_clients=len(clients),
            notes_not_null=notes_not_null,
            notes_nonempty=notes_nonempty,
            transcript_like=transcript_like,
            sourced_clients=len(messages_by_client),
            format_variants=format_variants,
            marker_coverage=marker_coverage,
            separators=separators,
            block_counts=block_counts,
            false_positive_phrase_notes=false_positive_phrase_notes,
        )
        return proposals, summary

    def _source_messages(self, active_ids: list[int]) -> dict[int, list[SourceMessage]]:
        rows = (
            self.db.query(CandidateSource, ClientCandidate.matched_client_id)
            .join(ClientCandidate, ClientCandidate.id == CandidateSource.candidate_id)
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
                ClientCandidate.matched_client_id.in_(active_ids),
            )
            .order_by(CandidateSource.id.desc())
            .all()
        )
        result: dict[int, list[SourceMessage]] = defaultdict(list)
        seen: set[tuple[int, int, str]] = set()
        for source, client_id in rows:
            dedupe_key = (client_id, source.import_source_id, source.external_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
            result[client_id].append(
                SourceMessage(
                    source_id=source.id,
                    direction=self.email_normalizer._direction(payload),
                    message_at=self.email_normalizer._parse_message_at(payload),
                    subject=self.email_normalizer._clean_string(
                        payload.get("subject") or payload.get("Subject")
                    ),
                    body=self.email_normalizer._body_text(payload, source.extracted_text),
                )
            )
        return dict(result)

    def _proposal(
        self,
        *,
        client_id: int,
        notes: str,
        parsed: ParsedLegacyNotes,
        messages: list[SourceMessage],
    ) -> ClientNotesCleanupProposal:
        statuses = tuple(self._cross_check(block, messages) for block in parsed.blocks)
        if not messages:
            classification: CleanupClassification = "BLOCKED_NO_SOURCE_HISTORY"
        elif parsed.ambiguous or not parsed.blocks or any(
            status != "CONFIRMED_SOURCE_MATCH" for status in statuses
        ):
            classification = "REVIEW_REQUIRED"
        elif parsed.has_manual_content:
            classification = "SAFE_REMOVE_TRANSCRIPT_ONLY"
        elif parsed.proposed_notes is None:
            classification = "SAFE_CLEAR_NOTES"
        else:
            classification = "NO_CHANGE"

        safe = classification in {"SAFE_REMOVE_TRANSCRIPT_ONLY", "SAFE_CLEAR_NOTES"}
        proposed = parsed.proposed_notes if safe else notes
        return ClientNotesCleanupProposal(
            client_id=client_id,
            before_length=len(notes),
            before_sha256=notes_sha256(notes),
            classification=classification,
            removed_block_count=len(parsed.blocks) if safe else 0,
            removed_character_count=(len(notes) - len(proposed or "")) if safe else 0,
            preserved_character_count=len(proposed or ""),
            proposed_notes=proposed,
            proposed_notes_sha256=notes_sha256(proposed),
            source_match_statuses=statuses or ("AMBIGUOUS",),
            marker_signatures=tuple(block.signature for block in parsed.blocks),
            manual_excerpt=(
                self._safe_excerpt(parsed.proposed_notes)
                if parsed.has_manual_content
                else None
            ),
            has_manual_content=parsed.has_manual_content,
            boundary_ambiguous=parsed.ambiguous,
            transcript_positions=parsed.transcript_positions,
        )

    def _cross_check(
        self,
        block: LegacyTranscriptBlock,
        messages: list[SourceMessage],
    ) -> SourceMatchStatus:
        candidates = [
            message
            for message in messages
            if message.direction == block.direction
            and message.message_at is not None
            and message.message_at.astimezone(timezone.utc) == block.message_at
        ]
        if block.subject is not None:
            subject = self._normalized_subject(block.subject)
            candidates = [
                message
                for message in candidates
                if self._normalized_subject(message.subject) == subject
            ]
        if len(candidates) > 1 and block.body is not None:
            body = self.email_normalizer._normalize_text(block.body)
            body_matches = [
                message
                for message in candidates
                if self.email_normalizer._normalize_text(message.body or "") == body
            ]
            if len(body_matches) == 1:
                candidates = body_matches
        if len(candidates) == 1:
            return "CONFIRMED_SOURCE_MATCH"
        if len(candidates) > 1:
            return "STRUCTURE_CONFIRMED_BUT_MESSAGE_NOT_UNIQUE"
        return "NO_SOURCE_MATCH"

    @staticmethod
    def _normalized_subject(value: str | None) -> str:
        if value is None:
            return ""
        return html.unescape(value).replace("\xa0", " ").strip()

    @staticmethod
    def _contains_marker_phrase(notes: str) -> bool:
        folded = notes.casefold()
        return any(label.casefold() in folded for label in MARKER_LABELS)

    @staticmethod
    def _safe_excerpt(value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        excerpt = value.strip()[:120]
        excerpt = _EMAIL_RE.sub("[EMAIL]", excerpt)
        return _NUMBER_RE.sub("#", excerpt)

    @staticmethod
    def _summary(
        *,
        proposals: list[ClientNotesCleanupProposal],
        active_clients: int,
        notes_not_null: int,
        notes_nonempty: int,
        transcript_like: int,
        sourced_clients: int,
        format_variants: Counter[tuple[str, ...]],
        marker_coverage: Counter[str],
        separators: Counter[str],
        block_counts: Counter[int],
        false_positive_phrase_notes: int,
    ) -> dict[str, Any]:
        classification_names = (
            "SAFE_REMOVE_TRANSCRIPT_ONLY",
            "SAFE_CLEAR_NOTES",
            "REVIEW_REQUIRED",
            "BLOCKED_NO_SOURCE_HISTORY",
            "NO_CHANGE",
        )
        class_counts = Counter(item.classification for item in proposals)
        classes = {name: class_counts[name] for name in classification_names}
        source_status_names = (
            "CONFIRMED_SOURCE_MATCH",
            "STRUCTURE_CONFIRMED_BUT_MESSAGE_NOT_UNIQUE",
            "NO_SOURCE_MATCH",
            "AMBIGUOUS",
        )
        source_statuses = Counter(
            status for item in proposals for status in item.source_match_statuses
        )
        source_status_summary = {
            name: source_statuses[name] for name in source_status_names
        }
        safe = [
            item
            for item in proposals
            if item.classification in {"SAFE_REMOVE_TRANSCRIPT_ONLY", "SAFE_CLEAR_NOTES"}
        ]
        transcript_with_source = sum(
            item.classification != "BLOCKED_NO_SOURCE_HISTORY" for item in proposals
        )
        return {
            "baseline": {
                "active_clients": active_clients,
                "notes_not_null": notes_not_null,
                "notes_nonempty": notes_nonempty,
                "transcript_like_notes": transcript_like,
                "clients_with_sourced_gmail_history": sourced_clients,
                "transcript_like_with_sourced_gmail": transcript_with_source,
                "transcript_like_without_sourced_gmail": class_counts[
                    "BLOCKED_NO_SOURCE_HISTORY"
                ],
            },
            "classification": classes,
            "content": {
                "safe_records_preserving_manual_content": class_counts[
                    "SAFE_REMOVE_TRANSCRIPT_ONLY"
                ],
                "safe_records_becoming_null": class_counts["SAFE_CLEAR_NOTES"],
                "legacy_blocks_proposed_removed": sum(
                    item.removed_block_count for item in safe
                ),
                "characters_proposed_removed": sum(
                    item.removed_character_count for item in safe
                ),
                "characters_proposed_preserved": sum(
                    item.preserved_character_count for item in safe
                ),
            },
            "source_cross_check": source_status_summary,
            "format_audit": {
                "format_variant_count": len(format_variants),
                "format_variants": [
                    {"signature": list(signature), "block_count": count}
                    for signature, count in format_variants.most_common()
                ],
                "marker_coverage_blocks": dict(marker_coverage),
                "separator_patterns": dict(separators),
                "clients_by_block_count": {
                    str(count): clients for count, clients in sorted(block_counts.items())
                },
                "multiple_message_clients": sum(
                    clients for count, clients in block_counts.items() if count > 1
                ),
                "maximum_blocks_in_notes": max(block_counts, default=0),
                "transcript_positions": dict(
                    Counter(
                        position
                        for item in proposals
                        for position in item.transcript_positions
                    )
                ),
                "clients_with_manual_and_transcript": sum(
                    item.has_manual_content for item in proposals
                ),
                "malformed_or_truncated_clients": sum(
                    item.boundary_ambiguous or not item.marker_signatures
                    for item in proposals
                ),
            },
            "false_positive_audit": {
                "non_transcript_notes_with_marker_phrases": false_positive_phrase_notes,
                "rule_requires_full_structure": True,
            },
            "manual_content_safety_samples": {
                "transcript_only_to_null": [
                    {
                        "client_id": item.client_id,
                        "before_length": item.before_length,
                        "proposed_length": 0,
                        "markers": sorted(
                            {label for signature in item.marker_signatures for label in signature}
                        ),
                    }
                    for item in proposals
                    if item.classification == "SAFE_CLEAR_NOTES"
                ][:5],
                "manual_content_preserved": [
                    {
                        "client_id": item.client_id,
                        "before_length": item.before_length,
                        "proposed_length": item.preserved_character_count,
                        "manual_excerpt": item.manual_excerpt,
                    }
                    for item in proposals
                    if item.classification == "SAFE_REMOVE_TRANSCRIPT_ONLY"
                ][:5],
                "review_required": [
                    {
                        "client_id": item.client_id,
                        "before_length": item.before_length,
                        "block_count": len(item.marker_signatures),
                        "source_status_counts": dict(
                            Counter(item.source_match_statuses)
                        ),
                        "manual_excerpt": item.manual_excerpt,
                    }
                    for item in proposals
                    if item.classification == "REVIEW_REQUIRED"
                ][:10],
            },
            "production_database_modifications": 0,
        }
