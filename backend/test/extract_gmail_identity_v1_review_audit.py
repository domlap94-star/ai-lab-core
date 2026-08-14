from __future__ import annotations

from pathlib import Path


REPORT = Path(
    "/app/test/reports/"
    "candidate_identity_gmail_layer_v1.txt"
)


def get_section(
    text: str,
    start_title: str,
    end_title: str,
) -> str:
    separator = "=" * 120

    start_marker = (
        separator
        + "\n"
        + start_title
        + "\n"
        + separator
    )

    end_marker = (
        separator
        + "\n"
        + end_title
        + "\n"
        + separator
    )

    start = text.find(start_marker)

    if start < 0:
        return f"<SECTION NOT FOUND: {start_title}>"

    start += len(start_marker)

    end = text.find(
        end_marker,
        start,
    )

    if end < 0:
        end = len(text)

    return text[start:end].strip()


def main() -> None:
    text = REPORT.read_text(
        encoding="utf-8"
    ).replace(
        "\r\n",
        "\n",
    )

    review = get_section(
        text,
        "REVIEW RESULTS - FIRST 100",
        "AMBIGUOUS RESULTS - FIRST 50",
    )

    ambiguous = get_section(
        text,
        "AMBIGUOUS RESULTS - FIRST 50",
        "CONTROL CANDIDATES",
    )

    print()
    print("=" * 120)
    print("REVIEW RESULTS")
    print("=" * 120)
    print(review)

    print()
    print("=" * 120)
    print("AMBIGUOUS RESULTS")
    print("=" * 120)
    print(ambiguous)

    print()
    print("=" * 120)
    print("AUDIT EXTRACTION COMPLETE")
    print("=" * 120)


if __name__ == "__main__":
    main()
