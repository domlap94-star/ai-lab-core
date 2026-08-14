from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.models.candidate_source import CandidateSource


KEYWORDS = (
    "powiat",
    "starost",
    "urząd",
    "urzad",
    "miasto",
    "gmina",
    "oddział",
    "oddzial",
    "spółdziel",
    "spoldziel",
    "wspólnot",
    "wspolnot",
    "zarząd",
    "zarzad",
    "zakład",
    "zaklad",
    "przedsiębior",
    "przedsiebior",
    "firma",
    "sp. z",
    "sp z",
    "s.a.",
    "sa ",
    "s.c.",
    "sc ",
    "fundacja",
    "stowarzyszenie",
    "szkoła",
    "szkola",
    "szpital",
    "parafia",
    "deweloper",
    "development",
    "bud",
    "invest",
)


def looks_organizational(value: str | None) -> bool:
    if not value:
        return False

    lowered = value.casefold()

    return any(
        keyword in lowered
        for keyword in KEYWORDS
    )


def main() -> None:
    db = SessionLocal()

    try:
        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None)
            )
            .order_by(
                ClientCandidate.id.asc()
            )
            .all()
        )

        print()
        print("=" * 120)
        print("CLIENT TYPE DISTRIBUTION")
        print("=" * 120)

        type_counts = Counter(
            str(candidate.client_type)
            for candidate in candidates
        )

        for value, count in sorted(
            type_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):
            print(
                repr(value),
                ":",
                count,
            )

        print()
        print("=" * 120)
        print("CANDIDATES WITH LEGAL_NAME")
        print("=" * 120)

        legal_name_candidates = [
            candidate
            for candidate in candidates
            if candidate.legal_name
        ]

        print(
            "count:",
            len(legal_name_candidates),
        )

        for candidate in legal_name_candidates[:100]:
            print(
                candidate.id,
                "| name:",
                repr(candidate.name),
                "| legal_name:",
                repr(candidate.legal_name),
                "| client_type:",
                repr(candidate.client_type),
            )

        print()
        print("=" * 120)
        print("ORGANIZATIONAL / PUBLIC-BODY LOOKING NAMES")
        print("=" * 120)

        organizational = [
            candidate
            for candidate in candidates
            if (
                looks_organizational(
                    candidate.name
                )
                or looks_organizational(
                    candidate.legal_name
                )
            )
        ]

        print(
            "count:",
            len(organizational),
        )

        for candidate in organizational[:250]:
            print(
                candidate.id,
                "|",
                repr(candidate.name),
                "| legal:",
                repr(candidate.legal_name),
                "| type:",
                repr(candidate.client_type),
                "| status:",
                repr(candidate.status),
            )

        print()
        print("=" * 120)
        print("KNOWN CONTROL ENTITIES")
        print("=" * 120)

        controls = (
            "Powiat",
            "Oddział",
            "Oddzial",
            "Starost",
            "Urząd",
            "Urzad",
            "Spółdz",
            "Spoldz",
            "Wspólnot",
            "Wspolnot",
        )

        found = 0

        for candidate in candidates:
            combined = " ".join(
                value
                for value in (
                    candidate.name,
                    candidate.legal_name,
                )
                if value
            )

            if any(
                token.casefold()
                in combined.casefold()
                for token in controls
            ):
                print(
                    candidate.id,
                    "|",
                    repr(candidate.name),
                    "| legal:",
                    repr(candidate.legal_name),
                    "| type:",
                    repr(candidate.client_type),
                )

                found += 1

        print(
            "control_entity_count:",
            found,
        )

        print()
        print("=" * 120)
        print("SOURCE TYPES FOR ORGANIZATIONAL CANDIDATES")
        print("=" * 120)

        source_counts = Counter()

        organizational_ids = {
            candidate.id
            for candidate in organizational
        }

        sources = (
            db.query(CandidateSource)
            .filter(
                CandidateSource.deleted_at.is_(None)
            )
            .all()
        )

        for source in sources:
            if source.candidate_id in organizational_ids:
                source_counts[
                    source.source_type
                ] += 1

        for source_type, count in sorted(
            source_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):
            print(
                source_type,
                ":",
                count,
            )

        print()
        print("=" * 120)
        print("DATABASE NOT MODIFIED")
        print("=" * 120)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
