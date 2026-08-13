from __future__ import annotations

import re
import unicodedata


class FirstPartyIdentityRegistry:
    """
    First-Party Identity Registry 1.0.

    Explicit description of identities belonging to our own
    organization.

    This service deliberately does NOT:
    - parse Gmail quote boundaries,
    - infer customers,
    - modify ClientCandidate,
    - perform database writes.

    It answers only:
        "Does this identity belong to us?"

    Keeping this knowledge here prevents first-party rules
    from leaking into generic Gmail / entity parsers.
    """

    FIRST_PARTY_EMAILS = frozenset(
        {
            "kontakt@podnoszenieposadzek.pl",
            "podnoszenieposadzek@gmail.com",
            "domlap94@gmail.com",
            "pawcioou@gmail.com",
        }
    )

    FIRST_PARTY_DOMAINS = frozenset(
        {
            "podnoszenieposadzek.pl",
        }
    )

    FIRST_PARTY_TAX_IDS = frozenset(
        {
            # Historical business identity.
            "8211139503",

            # Current NEXT Stabil identity found in the corpus.
            "8212697553",
        }
    )

    FIRST_PARTY_PERSON_NAMES = frozenset(
        {
            "dominik lapinski",
            "wojciech lapinski",
        }
    )

    FIRST_PARTY_ENTITY_MARKERS = (
        "next stabil",
        "next podnoszenie posadzek",
        "podnoszenie posadzek",
    )

    @classmethod
    def is_first_party_email(
        cls,
        value: str | None,
    ) -> bool:
        email = cls.normalize_email(
            value
        )

        if not email:
            return False

        if email in cls.FIRST_PARTY_EMAILS:
            return True

        _, _, domain = email.partition("@")

        return (
            domain
            in cls.FIRST_PARTY_DOMAINS
        )

    @classmethod
    def is_first_party_tax_id(
        cls,
        value: str | None,
    ) -> bool:
        tax_id = cls.normalize_tax_id(
            value
        )

        return (
            bool(tax_id)
            and tax_id
            in cls.FIRST_PARTY_TAX_IDS
        )

    @classmethod
    def is_first_party_person(
        cls,
        value: str | None,
    ) -> bool:
        normalized = cls.normalize_identity(
            value
        )

        return (
            bool(normalized)
            and normalized
            in cls.FIRST_PARTY_PERSON_NAMES
        )

    @classmethod
    def is_first_party_entity(
        cls,
        value: str | None,
    ) -> bool:
        normalized = cls.normalize_identity(
            value
        )

        if not normalized:
            return False

        return any(
            marker in normalized
            for marker
            in cls.FIRST_PARTY_ENTITY_MARKERS
        )

    @classmethod
    def is_first_party_identity(
        cls,
        value: str | None,
    ) -> bool:
        if not value:
            return False

        return (
            cls.is_first_party_email(
                value
            )
            or cls.is_first_party_tax_id(
                value
            )
            or cls.is_first_party_person(
                value
            )
            or cls.is_first_party_entity(
                value
            )
        )

    @staticmethod
    def normalize_email(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        text = (
            str(value)
            .strip()
            .casefold()
        )

        if (
            "@" not in text
            or any(
                character.isspace()
                for character in text
            )
        ):
            return ""

        local, separator, domain = (
            text.partition("@")
        )

        if not (
            local
            and separator
            and domain
        ):
            return ""

        return text

    @staticmethod
    def normalize_tax_id(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        digits = re.sub(
            r"\D",
            "",
            str(value),
        )

        if len(digits) != 10:
            return ""

        return digits

    @staticmethod
    def normalize_identity(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        text = unicodedata.normalize(
            "NFKD",
            str(value),
        )

        text = "".join(
            character
            for character in text
            if not unicodedata.combining(
                character
            )
        )

        # Polish ł does not decompose under NFKD.
        text = (
            text
            .replace("Ł", "L")
            .replace("ł", "l")
        )

        text = text.casefold()

        text = re.sub(
            r"[^a-z0-9@.\- ]+",
            " ",
            text,
        )

        return " ".join(
            text.split()
        )
