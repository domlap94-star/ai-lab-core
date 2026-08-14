from __future__ import annotations

from pathlib import Path


REPORT = Path(
    "/app/test/reports/"
    "candidate_identity_gmail_layer_v1.txt"
)


def get_section(
    text: str,
    title: str,
    next_title: str | None = None,
) -> str:
    marker = (
        "=" * 120
        + "\n"
        + title
        + "\n"
        + "=" * 120
    )

    start = text.find(marker)

    if start < 0:
        return f"<SECTION NOT FOUND: {title}>"

    start += len(marker)

    if next_title is None:
        return text[start:].strip()

    next_marker = (
        "=" * 120
        + "\n"
        + next_title
        + "\n"
        + "=" * 120
    )

    end = text.find(
        next_marker,
        start,
    )

    if end < 0:
        end = len(text)

    return text[start:end].strip()


def main() -> None:
    text = REPORT.read_text(
        encoding="utf-8",
    ).replace(
        "\r\n",
        "\n",
    )

    print()
    print("=" * 120)
    print("SUMMARY")
    print("=" * 120)

    wanted_prefixes = (
        "secondary_insufficient:",
        "auto_safe:",
        "review:",
        "ambiguous:",
        "insufficient:",
    )

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith(
            wanted_prefixes
        ):
            print(stripped)

    print()
    print("=" * 120)
    print("TRANSITIONS")
    print("=" * 120)

    print(
        get_section(
            text,
            "TRANSITIONS",
            "AUTO_SAFE RESULTS",
        )
    )

    print()
    print("=" * 120)
    print("ALL AUTO_SAFE RESULTS")
    print("=" * 120)

    print(
        get_section(
            text,
            "AUTO_SAFE RESULTS",
            "REVIEW RESULTS - FIRST 100",
        )
    )

    print()
    print("=" * 120)
    print("FIRST 100 REVIEW RESULTS")
    print("=" * 120)

    print(
        get_section(
            text,
            "REVIEW RESULTS - FIRST 100",
            "AMBIGUOUS RESULTS - FIRST 50",
        )
    )

    print()
    print("=" * 120)
    print("FIRST 50 AMBIGUOUS RESULTS")
    print("=" * 120)

    print(
        get_section(
            text,
            "AMBIGUOUS RESULTS - FIRST 50",
            "CONTROL CANDIDATES",
        )
    )

    print()
    print("=" * 120)
    print("CONTROL CANDIDATES")
    print("=" * 120)

    print(
        get_section(
            text,
            "CONTROL CANDIDATES",
            "DATABASE NOT MODIFIED",
        )
    )

    print()
    print("=" * 120)
    print("RESULT EXTRACTION COMPLETE")
    print("=" * 120)


if __name__ == "__main__":
    main()
