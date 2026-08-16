from __future__ import annotations

import re
from dataclasses import dataclass


# ============================================================
# CLASSIC REPLY / FORWARD BOUNDARIES
# ============================================================

CLASSIC_LINE_BOUNDARY_RE = re.compile(
    r"(?im)^"
    r"(?:"
    r">"
    r"|-----\s*original message\s*-----"
    r"|-----\s*wiadomo(?:ść|sc) oryginalna\s*-----"
    r"|--------\s*oryginalna wiadomo(?:ść|sc)\s*--------"
    r"|----------\s*forwarded message"
    r"|----------\s*przekazana wiadomo(?:ść|sc)"
    r"|begin forwarded message:"
    r"|from:"
    r"|sent:"
    r"|wysłano:"
    r"|wyslano:"
    r")"
)


# ============================================================
# POLISH "DNIA ..."
# ============================================================

POLISH_DNIA_REPLY_RE = re.compile(
    r"(?is)"
    r"(?:^|\s)"
    r"Dnia\s+"
    r"\d{1,2}\s+"
    r"[^\s]{2,20}\s+"
    r"\d{4}"
    r"(?:\s+\d{1,2}:\d{2})?"
    r".{0,500}?"
    r"napisa.{0,16}?:"
)


# ============================================================
# GMAIL POLISH WEEKDAY FORMAT
# ============================================================

GMAIL_POLISH_REPLY_RE = re.compile(
    r"(?is)"
    r"(?:^|\s)"
    r"(?:"
    r"pon"
    r"|wt"
    r"|śr"
    r"|sr"
    r"|czw"
    r"|pt"
    r"|sob"
    r"|niedz"
    r")"
    r"\.?,?\s+"
    r"\d{1,2}\s+"
    r"[^\s]{2,20}\s+"
    r"\d{4}"
    r".{0,500}?"
    r"napisa.{0,16}?:"
)


# ============================================================
# "W DNIU YYYY-MM-DD ... NAPISAŁ"
#
# Real corpus examples:
#
# W dniu 2022-10-27 07:52:12 użytkownik ... napisał:
# W dniu 2024-02-04 14:15:48 użytkownik ... napisał:
#
# Encoding damage in historical imports means the parser
# intentionally does not require an exact spelling of
# "użytkownik" or "napisał".
# ============================================================

POLISH_W_DNIU_REPLY_RE = re.compile(
    r"(?is)"
    r"(?:^|\s)"
    r"W\s+dniu\s+"
    r"(?:"
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|"
    r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r")"
    r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
    r".{0,500}?"
    r"napisa.{0,16}?:"
)


# ============================================================
# "W DNIU DD.MM.YYYY ... PISZE:"
# ============================================================

POLISH_PISZE_RE = re.compile(
    r"(?is)"
    r"(?:^|\s)"
    r"W\s+dniu\s+"
    r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}"
    r".{0,400}?"
    r"\bpisze\s*:"
)


# ============================================================
# OUTLOOK HEADER BLOCK
#
# Examples:
#
# ________________________________
# Od: ...
# Wysłane: ...
# Do: ...
# Temat: ...
#
# or:
#
# Od: ...
# Data: ...
# Do: ...
# DW: ...
# Temat: ...
#
# We require the STRUCTURE of the header block.
# A standalone "Od:" must never trigger this rule because
# website relay payloads also legitimately start with "Od:".
# ============================================================

OUTLOOK_SEPARATOR_HEADER_RE = re.compile(
    r"(?im)"
    r"^(?:_{6,}|-{6,})\s*\n"
    r"\s*(?:Od|From)\s*:[^\n]*\n"
    r"\s*(?:"
    r"Wys[^:\n]{0,24}"
    r"|Data"
    r"|Sent"
    r")\s*:[^\n]*\n"
    r"\s*(?:Do|To)\s*:[^\n]*\n"
    r"(?:"
    r"\s*(?:DW|CC)\s*:[^\n]*\n"
    r")?"
    r"\s*(?:Temat|Subject)\s*:"
)

OUTLOOK_HEADER_RE = re.compile(
    r"(?im)"
    r"^\s*(?:Od|From)\s*:[^\n]*\n"
    r"\s*(?:"
    r"Wys[^:\n]{0,24}"
    r"|Data"
    r"|Sent"
    r")\s*:[^\n]*\n"
    r"\s*(?:Do|To)\s*:[^\n]*\n"
    r"(?:"
    r"\s*(?:DW|CC)\s*:[^\n]*\n"
    r")?"
    r"\s*(?:Temat|Subject)\s*:"
)


# ============================================================
# GENERIC ENGLISH
# ============================================================

GENERIC_WROTE_RE = re.compile(
    r"(?is)"
    r"(?:^|\s)"
    r".{0,250}?"
    r"\bwrote\s*:"
)


# ============================================================
# STRICT CONTACT-FORM RELAY GRAMMAR
# ============================================================

RELAY_EMAIL_RE = re.compile(
    r"(?im)"
    r"^\s*"
    r"(?:Z|Od|From)"
    r"\s*:\s*"
    r"\{?\s*"
    r"([^{}\s]+@[^{}\s]+)"
    r"\s*\}?"
    r"\s*$"
)

RELAY_NAME_RE = re.compile(
    r"(?im)"
    r"^\s*"
    r"Nazwa"
    r"\s*:\s*"
    r"\{?\s*"
    r"(.+?)"
    r"\s*\}?"
    r"\s*$"
)

RELAY_MESSAGE_LABEL_RE = re.compile(
    r"(?im)"
    r"^\s*"
    r"Wiadomo(?:ść|sc|┼Ť─ç)"
    r"\s*:"
)

RELAY_MESSAGE_RE = re.compile(
    r"(?is)"
    r"(?:^|\n)"
    r"\s*"
    r"Wiadomo(?:ść|sc|┼Ť─ç)"
    r"\s*:\s*"
    r"(.*)$"
)


@dataclass(frozen=True)
class RelayPayload:
    email: str
    name: str
    message: str


@dataclass(frozen=True)
class GmailMessageBoundary:
    current_content: str
    quoted_history: str

    boundary_method: str | None
    boundary_index: int | None

    relay_payload: RelayPayload | None


class GmailMessageBoundaryService:
    """
    Gmail Message Boundary 1.2.

    Pure transport/content parser.

    Responsibilities:
    - isolate current-author content,
    - isolate quoted history,
    - recognize complete website/contact-form relay payloads.

    It deliberately has no knowledge of:
    - CRM clients,
    - NEXT Stabil,
    - employee names,
    - company NIPs,
    - first-party mailboxes.

    Those belong to a separate identity layer.
    """

    def parse(
        self,
        text: str | None,
    ) -> GmailMessageBoundary:
        normalized = self._normalize_text(
            text
        )

        if not normalized:
            return GmailMessageBoundary(
                current_content="",
                quoted_history="",
                boundary_method=None,
                boundary_index=None,
                relay_payload=None,
            )

        boundary = self._find_boundary(
            normalized
        )

        if boundary is None:
            current = normalized.strip()
            quoted = ""
            method = None
            index = None

        else:
            index, method = boundary

            current = (
                normalized[:index]
                .strip()
            )

            quoted = (
                normalized[index:]
                .strip()
            )

        relay_payload = (
            self._extract_relay_payload(
                current
            )
        )

        return GmailMessageBoundary(
            current_content=current,
            quoted_history=quoted,
            boundary_method=method,
            boundary_index=index,
            relay_payload=relay_payload,
        )

    # ========================================================
    # BOUNDARY DETECTION
    # ========================================================

    def _find_boundary(
        self,
        text: str,
    ) -> tuple[int, str] | None:
        candidates: list[
            tuple[int, str]
        ] = []

        patterns = (
            (
                OUTLOOK_SEPARATOR_HEADER_RE,
                "outlook_separator_header",
            ),
            (
                OUTLOOK_HEADER_RE,
                "outlook_header",
            ),
            (
                CLASSIC_LINE_BOUNDARY_RE,
                "classic_line_boundary",
            ),
            (
                POLISH_DNIA_REPLY_RE,
                "polish_dnia_reply",
            ),
            (
                POLISH_W_DNIU_REPLY_RE,
                "polish_w_dniu_reply",
            ),
            (
                GMAIL_POLISH_REPLY_RE,
                "gmail_polish_reply",
            ),
            (
                POLISH_PISZE_RE,
                "polish_pisze_reply",
            ),
            (
                GENERIC_WROTE_RE,
                "generic_wrote_reply",
            ),
        )

        for pattern, method in patterns:
            match = pattern.search(
                text
            )

            if match is None:
                continue

            start = match.start()

            while (
                start < len(text)
                and text[start].isspace()
                and text[start] != "\n"
            ):
                start += 1

            candidates.append(
                (
                    start,
                    method,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0]
        )

        return candidates[0]

    # ========================================================
    # STRICT RELAY
    # ========================================================

    def _extract_relay_payload(
        self,
        current_content: str,
    ) -> RelayPayload | None:
        if not current_content:
            return None

        email_match = (
            RELAY_EMAIL_RE.search(
                current_content
            )
        )

        name_match = (
            RELAY_NAME_RE.search(
                current_content
            )
        )

        message_label_match = (
            RELAY_MESSAGE_LABEL_RE.search(
                current_content
            )
        )

        if (
            email_match is None
            or name_match is None
            or message_label_match is None
        ):
            return None

        email = (
            email_match.group(1)
            .strip()
            .casefold()
        )

        if not self._looks_email(
            email
        ):
            return None

        name = (
            name_match.group(1)
            .strip()
            .strip("{}")
            .strip()
        )

        if not name:
            return None

        message_match = (
            RELAY_MESSAGE_RE.search(
                current_content
            )
        )

        if message_match is None:
            return None

        message = (
            message_match.group(1)
            .strip()
        )

        if (
            message.startswith("{")
            and message.endswith("}")
        ):
            message = (
                message[1:-1]
                .strip()
            )

        if not message:
            return None

        return RelayPayload(
            email=email,
            name=name,
            message=message,
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _normalize_text(
        text: str | None,
    ) -> str:
        if not text:
            return ""

        return (
            str(text)
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )

    @staticmethod
    def _looks_email(
        value: str,
    ) -> bool:
        if not value:
            return False

        if "@" not in value:
            return False

        if any(
            character.isspace()
            for character in value
        ):
            return False

        local, _, domain = (
            value.partition("@")
        )

        return bool(
            local
            and domain
            and "." in domain
        )
