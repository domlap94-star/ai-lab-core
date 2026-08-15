from __future__ import annotations

import re
import unicodedata


class ClientIdentityNameQualityService:
    """Deterministic quality classification for client identity names."""

    EMAIL_RE = re.compile(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        re.IGNORECASE,
    )
    FILE_RE = re.compile(
        r"\.(?:pdf|png|jpe?g|docx?|xlsx?|zip|rar)\s*[])]?$",
        re.IGNORECASE,
    )
    PHONE_ALLOWED_RE = re.compile(r"^[\d\s()+./-]+$")
    URL_RE = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)
    TECHNICAL_ID_RE = re.compile(
        r"^(?:[0-9a-f]{24,}|[0-9a-f]{8}-[0-9a-f-]{27,})$",
        re.IGNORECASE,
    )
    ADDRESS_MARKER_RE = re.compile(
        r"(?<!\w)(?:ul(?:ica)?[.]?|al[.]|aleja|os[.]|osiedle|pl[.]|plac)(?!\w)",
        re.IGNORECASE,
    )
    BUILDING_NUMBER_RE = re.compile(
        r"\b\d+[a-z]?(?:\s*[/\-]\s*\d+[a-z]?)?\b",
        re.IGNORECASE,
    )
    PLACEHOLDERS = frozenset(
        {
            "brak",
            "brak danych",
            "nieznany",
            "nieznany klient",
            "unknown",
            "unknown client",
            "n a",
            "na",
            "test",
        }
    )

    @classmethod
    def suspicion_types(cls, value: str | None) -> tuple[str, ...]:
        name = cls._clean(value)
        result: list[str] = []

        if cls.EMAIL_RE.fullmatch(name):
            result.append("EMAIL_AS_NAME")

        digits = re.sub(r"\D", "", name)
        if (
            9 <= len(digits) <= 11
            and bool(cls.PHONE_ALLOWED_RE.fullmatch(name))
        ):
            result.append("PHONE_AS_NAME")

        if cls.FILE_RE.search(name):
            result.append("FILE_AS_NAME")

        return tuple(result)

    @classmethod
    def is_suspicious(cls, value: str | None) -> bool:
        return bool(cls.suspicion_types(value))

    @classmethod
    def additional_findings(cls, value: str | None) -> tuple[str, ...]:
        name = cls._clean(value)

        if not name:
            return ("EMPTY_OR_WHITESPACE_NAME",)

        result: list[str] = []
        normalized = cls.normalize_identity(name)

        if cls.URL_RE.match(name):
            result.append("URL_AS_NAME")
        if normalized in cls.PLACEHOLDERS:
            result.append("PLACEHOLDER_AS_NAME")
        if cls.TECHNICAL_ID_RE.fullmatch(name):
            result.append("TECHNICAL_IDENTIFIER_AS_NAME")
        if cls.is_address_or_location_name(name):
            result.append("ADDRESS_OR_LOCATION_AS_NAME")

        return tuple(result)

    @classmethod
    def is_address_or_location_name(cls, value: str | None) -> bool:
        """Recognize only explicit, high-precision Polish address shapes."""
        name = cls._clean(value)
        if cls.EMAIL_RE.fullmatch(name) or cls.URL_RE.match(name):
            return False
        marker = cls.ADDRESS_MARKER_RE.search(name)
        if marker is None:
            return False

        suffix = name[marker.end() :]
        if cls.BUILDING_NUMBER_RE.search(suffix):
            return True

        # A location before an explicit street marker is an address-like
        # construction even when the building number is missing. A marker at
        # the start without a number remains allowed to protect organization
        # names such as "Plac Zabaw Sp. z o.o.".
        prefix = name[: marker.start()].strip(" ,;:-")
        return bool(prefix and any(character.isalpha() for character in prefix))

    @staticmethod
    def normalize_identity(value: str | None) -> str:
        if not value:
            return ""

        text = unicodedata.normalize("NFKD", str(value))
        text = "".join(
            character
            for character in text
            if not unicodedata.combining(character)
        )
        text = text.replace("Ł", "L").replace("ł", "l").casefold()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    @staticmethod
    def normalize_email(value: str | None) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def normalize_phone(value: str | None) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 11 and digits.startswith("48"):
            return digits[2:]
        return digits

    @staticmethod
    def normalize_tax_id(value: str | None) -> str:
        return re.sub(r"\D", "", str(value or ""))

    @staticmethod
    def _clean(value: str | None) -> str:
        return " ".join(str(value or "").split())
