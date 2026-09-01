from __future__ import annotations

import hashlib
import json
import math

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


DOCUMENT_METADATA_UNICODE_UNSAFE = "DOCUMENT_METADATA_UNICODE_UNSAFE"
DOCUMENT_METADATA_UNICODE_KEY_COLLISION = (
    "DOCUMENT_METADATA_UNICODE_KEY_COLLISION"
)
DOCUMENT_METADATA_JSON_INVALID = "DOCUMENT_METADATA_JSON_INVALID"
DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH = (
    "DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH"
)

_HIGH_MIN = 0xD800
_HIGH_MAX = 0xDBFF
_LOW_MIN = 0xDC00
_LOW_MAX = 0xDFFF
_REPLACEMENT = "\uFFFD"
_HEX = frozenset("0123456789abcdefABCDEF")
_MAX_DEPTH = 64
_MAX_NODES = 100_000
_MAX_JSON_TEXT_CHARS = 16 * 1024 * 1024


class DocumentMetadataSafetyError(ValueError):
    """Bounded metadata failure that never includes metadata content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TextSanitizationStats:
    replaced_high: int = 0
    replaced_low: int = 0
    preserved_valid_pairs: int = 0

    @property
    def replacement_count(self) -> int:
        return self.replaced_high + self.replaced_low


@dataclass(frozen=True)
class TextSanitizationResult:
    value: str = field(repr=False)
    stats: TextSanitizationStats = TextSanitizationStats()


@dataclass(frozen=True)
class LexicalReplacement:
    offset: int
    length: int
    codepoint_class: str


@dataclass(frozen=True)
class JsonLexicalRepairResult:
    candidate_text: str = field(repr=False)
    before_sha256: str
    after_sha256: str
    replaced_high: int
    replaced_low: int
    preserved_valid_pairs: int
    replacements: tuple[LexicalReplacement, ...]
    top_level_type: str
    path_fingerprint: str

    @property
    def replacement_count(self) -> int:
        return self.replaced_high + self.replaced_low

    def safe_evidence(self) -> dict[str, Any]:
        return {
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "replaced_high": self.replaced_high,
            "replaced_low": self.replaced_low,
            "preserved_valid_pairs": self.preserved_valid_pairs,
            "replacement_count": self.replacement_count,
            "replacements": [
                {
                    "offset": item.offset,
                    "length": item.length,
                    "codepoint_class": item.codepoint_class,
                }
                for item in self.replacements
            ],
            "top_level_type": self.top_level_type,
            "path_fingerprint": self.path_fingerprint,
        }


def _is_high(code: int) -> bool:
    return _HIGH_MIN <= code <= _HIGH_MAX


def _is_low(code: int) -> bool:
    return _LOW_MIN <= code <= _LOW_MAX


def sanitize_metadata_text(value: str) -> TextSanitizationResult:
    parts: list[str] = []
    high = 0
    low = 0
    pairs = 0
    index = 0
    while index < len(value):
        code = ord(value[index])
        if _is_high(code):
            if index + 1 < len(value) and _is_low(ord(value[index + 1])):
                parts.append(value[index])
                parts.append(value[index + 1])
                pairs += 1
                index += 2
                continue
            parts.append(_REPLACEMENT)
            high += 1
        elif _is_low(code):
            parts.append(_REPLACEMENT)
            low += 1
        else:
            parts.append(value[index])
        index += 1
    return TextSanitizationResult(
        "".join(parts),
        TextSanitizationStats(
            replaced_high=high,
            replaced_low=low,
            preserved_valid_pairs=pairs,
        ),
    )


def assert_metadata_text_safe(value: str) -> None:
    index = 0
    while index < len(value):
        code = ord(value[index])
        if _is_high(code):
            if index + 1 < len(value) and _is_low(ord(value[index + 1])):
                index += 2
                continue
            raise DocumentMetadataSafetyError(
                DOCUMENT_METADATA_UNICODE_UNSAFE
            )
        if _is_low(code):
            raise DocumentMetadataSafetyError(
                DOCUMENT_METADATA_UNICODE_UNSAFE
            )
        index += 1


def sanitize_json_compatible(value: Any) -> Any:
    active: set[int] = set()
    budget = [0]

    def visit(current: Any, depth: int) -> Any:
        budget[0] += 1
        if depth > _MAX_DEPTH or budget[0] > _MAX_NODES:
            raise DocumentMetadataSafetyError(
                DOCUMENT_METADATA_JSON_INVALID
            )
        if current is None:
            return None
        if isinstance(current, bool):
            return current
        if isinstance(current, int):
            return current
        if isinstance(current, float):
            return current if math.isfinite(current) else None
        if isinstance(current, str):
            return sanitize_metadata_text(current).value
        if isinstance(current, datetime):
            return sanitize_metadata_text(current.isoformat()).value
        if isinstance(current, bytes):
            return current.hex()
        if isinstance(current, dict):
            identity = id(current)
            if identity in active:
                raise DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_JSON_INVALID
                )
            active.add(identity)
            try:
                result: dict[str, Any] = {}
                for original_key, item in current.items():
                    safe_key = sanitize_metadata_text(
                        str(original_key)
                    ).value
                    if safe_key in result:
                        raise DocumentMetadataSafetyError(
                            DOCUMENT_METADATA_UNICODE_KEY_COLLISION
                        )
                    result[safe_key] = visit(item, depth + 1)
                return result
            finally:
                active.remove(identity)
        if isinstance(current, (list, tuple, set)):
            identity = id(current)
            if identity in active:
                raise DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_JSON_INVALID
                )
            active.add(identity)
            try:
                return [visit(item, depth + 1) for item in current]
            finally:
                active.remove(identity)
        try:
            numeric_value = float(current)
            if not math.isfinite(numeric_value):
                return None
            return numeric_value
        except Exception:
            return sanitize_metadata_text(str(current)).value

    result = visit(value, 0)
    assert_json_compatible_safe(result)
    return result


def assert_json_compatible_safe(value: Any) -> None:
    active: set[int] = set()
    budget = [0]

    def visit(current: Any, depth: int) -> None:
        budget[0] += 1
        if depth > _MAX_DEPTH or budget[0] > _MAX_NODES:
            raise DocumentMetadataSafetyError(
                DOCUMENT_METADATA_JSON_INVALID
            )
        if current is None or isinstance(current, (bool, int)):
            return
        if isinstance(current, float):
            if not math.isfinite(current):
                raise DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_JSON_INVALID
                )
            return
        if isinstance(current, str):
            assert_metadata_text_safe(current)
            return
        if isinstance(current, dict):
            identity = id(current)
            if identity in active:
                raise DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_JSON_INVALID
                )
            active.add(identity)
            try:
                for key, item in current.items():
                    if not isinstance(key, str):
                        raise DocumentMetadataSafetyError(
                            DOCUMENT_METADATA_JSON_INVALID
                        )
                    assert_metadata_text_safe(key)
                    visit(item, depth + 1)
            finally:
                active.remove(identity)
            return
        if isinstance(current, list):
            identity = id(current)
            if identity in active:
                raise DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_JSON_INVALID
                )
            active.add(identity)
            try:
                for item in current:
                    visit(item, depth + 1)
            finally:
                active.remove(identity)
            return
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_JSON_INVALID
        )

    visit(value, 0)
    try:
        json.dumps(value, ensure_ascii=True, allow_nan=False)
    except Exception as error:
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_JSON_INVALID
        ) from error


def _load_json_unique(text: str) -> Any:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_UNICODE_KEY_COLLISION
                )
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=pairs_hook)
    except DocumentMetadataSafetyError:
        raise
    except Exception as error:
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_JSON_INVALID
        ) from error


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return "invalid"


def _structure(value: Any) -> tuple[dict[str, int], str]:
    counts: dict[str, int] = {}
    paths: list[str] = []

    def visit(current: Any, path: tuple[str, ...]) -> None:
        kind = _type_name(current)
        counts[kind] = counts.get(kind, 0) + 1
        paths.append("/".join(path) + ":" + kind)
        if isinstance(current, dict):
            for key, item in current.items():
                segment = hashlib.sha256(
                    key.encode("utf-8", "surrogatepass")
                ).hexdigest()
                visit(item, path + ("k:" + segment,))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                visit(item, path + (f"i:{index}",))

    visit(value, ())
    fingerprint = hashlib.sha256(
        "\n".join(sorted(paths)).encode("ascii")
    ).hexdigest()
    return counts, fingerprint


def repair_json_text_surrogates(text: str) -> JsonLexicalRepairResult:
    if len(text) > _MAX_JSON_TEXT_CHARS:
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_JSON_INVALID
        )
    before = _load_json_unique(text)
    try:
        before_bytes = text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_JSON_INVALID
        ) from error

    unicode_tokens: list[tuple[int, int]] = []
    index = 0
    in_string = False
    while index < len(text):
        char = text[index]
        if not in_string:
            if char == '"':
                in_string = True
            index += 1
            continue
        if char == '"':
            in_string = False
            index += 1
            continue
        if char != "\\":
            index += 1
            continue
        if index + 1 >= len(text):
            raise DocumentMetadataSafetyError(
                DOCUMENT_METADATA_JSON_INVALID
            )
        if (
            text[index + 1] == "u"
            and index + 6 <= len(text)
            and all(char in _HEX for char in text[index + 2:index + 6])
        ):
            unicode_tokens.append(
                (index, int(text[index + 2:index + 6], 16))
            )
            index += 6
            continue
        index += 2
    if in_string:
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_JSON_INVALID
        )

    replacements: list[LexicalReplacement] = []
    preserved_pairs = 0
    token_index = 0
    while token_index < len(unicode_tokens):
        offset, code = unicode_tokens[token_index]
        if _is_high(code):
            if token_index + 1 < len(unicode_tokens):
                next_offset, next_code = unicode_tokens[token_index + 1]
                if next_offset == offset + 6 and _is_low(next_code):
                    preserved_pairs += 1
                    token_index += 2
                    continue
            replacements.append(
                LexicalReplacement(offset, 6, "unpaired_high")
            )
        elif _is_low(code):
            replacements.append(
                LexicalReplacement(offset, 6, "unpaired_low")
            )
        token_index += 1

    parts: list[str] = []
    cursor = 0
    for replacement in replacements:
        parts.append(text[cursor:replacement.offset])
        parts.append("\\uFFFD")
        cursor = replacement.offset + replacement.length
    parts.append(text[cursor:])
    candidate = "".join(parts)
    after = _load_json_unique(candidate)

    before_counts, before_paths = _structure(before)
    after_counts, after_paths = _structure(after)
    expected = sanitize_json_compatible(before)
    if (
        _type_name(before) != _type_name(after)
        or before_counts != after_counts
        or before_paths != after_paths
        or after != expected
    ):
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH
        )
    assert_json_compatible_safe(after)

    cursor = 0
    for replacement in replacements:
        if (
            text[cursor:replacement.offset]
            != candidate[cursor:replacement.offset]
        ):
            raise DocumentMetadataSafetyError(
                DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH
            )
        cursor = replacement.offset + replacement.length
    if text[cursor:] != candidate[cursor:]:
        raise DocumentMetadataSafetyError(
            DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH
        )

    return JsonLexicalRepairResult(
        candidate_text=candidate,
        before_sha256=hashlib.sha256(before_bytes).hexdigest(),
        after_sha256=hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
        replaced_high=sum(
            item.codepoint_class == "unpaired_high"
            for item in replacements
        ),
        replaced_low=sum(
            item.codepoint_class == "unpaired_low"
            for item in replacements
        ),
        preserved_valid_pairs=preserved_pairs,
        replacements=tuple(replacements),
        top_level_type=_type_name(after),
        path_fingerprint=after_paths,
    )
