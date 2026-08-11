from __future__ import annotations

import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import xlrd


@dataclass(frozen=True)
class LegacyOfficeResult:
    status: str
    text: str | None

    raw_metadata: dict[str, Any] | None
    normalized_metadata: dict[str, Any] | None

    extractor: str

    character_count: int

    error: str | None = None


class DocumentLegacyOfficeService:
    def extract(
        self,
        *,
        path: Path,
        content_type: str | None,
        original_filename: str | None,
    ) -> LegacyOfficeResult:
        if not path.exists():
            return LegacyOfficeResult(
                status="failed",
                text=None,
                raw_metadata=None,
                normalized_metadata=None,
                extractor="legacy-office",
                character_count=0,
                error=f"File does not exist: {path}",
            )

        extension = Path(
            original_filename or path.name
        ).suffix.lower()

        normalized_content_type = (
            content_type or ""
        ).strip().lower()

        try:
            if (
                extension == ".xls"
                or normalized_content_type
                == "application/vnd.ms-excel"
            ):
                return self._extract_xls(
                    path
                )

            if (
                extension == ".doc"
                or normalized_content_type
                == "application/msword"
            ):
                return self._extract_doc(
                    path
                )

            return LegacyOfficeResult(
                status="unsupported",
                text=None,
                raw_metadata=None,
                normalized_metadata=None,
                extractor="legacy-office",
                character_count=0,
                error=None,
            )

        except Exception as error:
            return LegacyOfficeResult(
                status="failed",
                text=None,
                raw_metadata=None,
                normalized_metadata=None,
                extractor="legacy-office",
                character_count=0,
                error=str(error),
            )

    def _extract_xls(
        self,
        path: Path,
    ) -> LegacyOfficeResult:
        workbook = xlrd.open_workbook(
            filename=str(path),
            on_demand=True,
        )

        try:
            text_parts: list[str] = []

            sheet_names = list(
                workbook.sheet_names()
            )

            sheet_stats: list[
                dict[str, Any]
            ] = []

            total_nonempty_cells = 0

            for sheet_name in sheet_names:
                sheet = workbook.sheet_by_name(
                    sheet_name
                )

                text_parts.append(
                    f"[SHEET] {sheet_name}"
                )

                nonempty_cells = 0

                for row_index in range(
                    sheet.nrows
                ):
                    row_values: list[str] = []

                    for col_index in range(
                        sheet.ncols
                    ):
                        cell = sheet.cell(
                            row_index,
                            col_index,
                        )

                        value = self._xls_cell_to_text(
                            workbook=workbook,
                            cell=cell,
                        )

                        if value:
                            nonempty_cells += 1
                            total_nonempty_cells += 1

                        row_values.append(
                            value
                        )

                    if any(
                        value
                        for value in row_values
                    ):
                        text_parts.append(
                            " | ".join(
                                row_values
                            )
                        )

                sheet_stats.append(
                    {
                        "name": sheet_name,
                        "rows": sheet.nrows,
                        "columns": sheet.ncols,
                        "nonempty_cells": (
                            nonempty_cells
                        ),
                    }
                )

            text = self._normalize_text(
                "\n".join(
                    text_parts
                )
            )

            raw_metadata = {
                "sheet_names": sheet_names,
                "sheet_count": len(
                    sheet_names
                ),
                "sheets": sheet_stats,
                "total_nonempty_cells": (
                    total_nonempty_cells
                ),
                "datemode": workbook.datemode,
                "biff_version": (
                    workbook.biff_version
                ),
                "codepage": getattr(
                    workbook,
                    "codepage",
                    None,
                ),
                "encoding": getattr(
                    workbook,
                    "encoding",
                    None,
                ),
            }

            normalized_metadata = {
                "format": "xls",
                "sheet_names": sheet_names,
                "sheet_count": len(
                    sheet_names
                ),
                "total_nonempty_cells": (
                    total_nonempty_cells
                ),
                "biff_version": (
                    workbook.biff_version
                ),
                "encoding": getattr(
                    workbook,
                    "encoding",
                    None,
                ),
            }

            return LegacyOfficeResult(
                status="extracted",
                text=(
                    text
                    if text
                    else None
                ),
                raw_metadata=raw_metadata,
                normalized_metadata=(
                    normalized_metadata
                ),
                extractor="xlrd",
                character_count=len(
                    text
                ),
                error=None,
            )

        finally:
            workbook.release_resources()

    def _extract_doc(
        self,
        path: Path,
    ) -> LegacyOfficeResult:
        process = subprocess.run(
            [
                "antiword",
                str(path),
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )

        stdout = (
            process.stdout
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        stderr = (
            process.stderr
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        text = self._normalize_text(
            stdout
        )

        raw_metadata = {
            "return_code": (
                process.returncode
            ),
            "stderr": (
                stderr.strip()
                if stderr.strip()
                else None
            ),
        }

        normalized_metadata = {
            "format": "doc",
            "extractor": "antiword",
        }

        if (
            process.returncode != 0
            and not text
        ):
            return LegacyOfficeResult(
                status="failed",
                text=None,
                raw_metadata=raw_metadata,
                normalized_metadata=(
                    normalized_metadata
                ),
                extractor="antiword",
                character_count=0,
                error=(
                    stderr.strip()
                    or (
                        "antiword returned "
                        f"exit code "
                        f"{process.returncode}"
                    )
                ),
            )

        return LegacyOfficeResult(
            status="extracted",
            text=(
                text
                if text
                else None
            ),
            raw_metadata=raw_metadata,
            normalized_metadata=(
                normalized_metadata
            ),
            extractor="antiword",
            character_count=len(
                text
            ),
            error=(
                stderr.strip()
                if stderr.strip()
                else None
            ),
        )

    def _xls_cell_to_text(
        self,
        *,
        workbook: xlrd.book.Book,
        cell: xlrd.sheet.Cell,
    ) -> str:
        value = cell.value

        if value is None:
            return ""

        if cell.ctype == xlrd.XL_CELL_EMPTY:
            return ""

        if cell.ctype == xlrd.XL_CELL_TEXT:
            return self._clean_string(
                str(value)
            )

        if cell.ctype == xlrd.XL_CELL_NUMBER:
            return self._format_number(
                float(value)
            )

        if cell.ctype == xlrd.XL_CELL_DATE:
            try:
                parsed = xlrd.xldate_as_datetime(
                    value,
                    workbook.datemode,
                )

                return parsed.isoformat()

            except Exception:
                return str(
                    value
                )

        if cell.ctype == xlrd.XL_CELL_BOOLEAN:
            return (
                "TRUE"
                if bool(value)
                else "FALSE"
            )

        if cell.ctype == xlrd.XL_CELL_ERROR:
            return (
                f"[XLS_ERROR:{value}]"
            )

        return self._clean_string(
            str(value)
        )

    @staticmethod
    def _format_number(
        value: float,
    ) -> str:
        rounded = round(
            value,
            10,
        )

        if rounded.is_integer():
            return str(
                int(rounded)
            )

        return (
            f"{rounded:.10f}"
            .rstrip("0")
            .rstrip(".")
        )

    @staticmethod
    def _clean_string(
        value: str,
    ) -> str:
        return " ".join(
            value
            .replace(
                "\r",
                " "
            )
            .replace(
                "\n",
                " "
            )
            .split()
        ).strip()

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        lines: list[str] = []

        for raw_line in (
            value
            .replace(
                "\r\n",
                "\n"
            )
            .replace(
                "\r",
                "\n"
            )
            .split(
                "\n"
            )
        ):
            normalized_line = (
                " ".join(
                    raw_line.split()
                ).strip()
            )

            if normalized_line:
                lines.append(
                    normalized_line
                )

        return "\n".join(
            lines
        ).strip()