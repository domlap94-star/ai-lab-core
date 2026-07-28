from pathlib import Path

DATA_PATH = Path("/data")
PROJECTS_PATH = DATA_PATH / "projects"


def create_case_structure(case_number: str) -> Path:
    """
    Tworzy pełną strukturę katalogów dla sprawy.
    """

    case_path = PROJECTS_PATH / case_number

    folders = [
        "documents",
        "images",
        "analysis",
        "offers",
        "exports",
        "mail",
        "temp",
    ]

    for folder in folders:
        (case_path / folder).mkdir(parents=True, exist_ok=True)

    return case_path
