from pathlib import Path


REPORT = Path(
    "/app/test/reports/"
    "candidate_identity_gmail_layer_v1.txt"
)


def section(text, start_title, end_title=None):
    marker = (
        "=" * 120
        + "\n"
        + start_title
        + "\n"
        + "=" * 120
    )

    start = text.find(marker)

    if start < 0:
        return f"<NOT FOUND: {start_title}>"

    start += len(marker)

    if end_title is None:
        return text[start:].strip()

    end_marker = (
        "=" * 120
        + "\n"
        + end_title
        + "\n"
        + "=" * 120
    )

    end = text.find(
        end_marker,
        start,
    )

    if end < 0:
        end = len(text)

    return text[start:end].strip()


def main():
    text = REPORT.read_text(
        encoding="utf-8"
    ).replace(
        "\r\n",
        "\n",
    )

    print()
    print("=" * 120)
    print("SUMMARY")
    print("=" * 120)

    prefixes = (
        "secondary_insufficient:",
        "auto_safe:",
        "review:",
        "ambiguous:",
        "insufficient:",
    )

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith(prefixes):
            print(stripped)

    print()
    print("=" * 120)
    print("TRANSITIONS")
    print("=" * 120)

    print(
        section(
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
        section(
            text,
            "AUTO_SAFE RESULTS",
            "REVIEW RESULTS - FIRST 100",
        )
    )

    print()
    print("=" * 120)
    print("CONTROL CANDIDATES")
    print("=" * 120)

    print(
        section(
            text,
            "CONTROL CANDIDATES",
            "DATABASE NOT MODIFIED",
        )
    )


if __name__ == "__main__":
    main()
