from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from app.services.document_extraction_service import (
    DocumentExtractionResult,
    ExtractedDocumentPage,
)
from app.services.unified_document_content_service import (
    FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE,
    FILE_FOUND_NATIVE_TEXT_AVAILABLE,
    FILE_FOUND_REQUIRES_OCR,
    FILE_FOUND_UNSUPPORTED,
    FILE_NOT_FOUND,
    INTEGRITY_MISMATCH,
    UnifiedDocumentContentService,
)


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.rows


class _ReadOnlyDb:
    def __init__(self, pages=()):
        self.pages = list(pages)
        self.writes = 0

    def query(self, *args):
        return _Query(self.pages)

    def add(self, *args):
        self.writes += 1

    def flush(self, *args):
        self.writes += 1


class _Extractor:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def extract(self, **kwargs):
        self.calls += 1
        return self.result


def _document(path, *, checksum=None, extracted_text=None, status="stored"):
    return SimpleNamespace(
        id=91, storage_path=path.name if path else None,
        content_type="application/pdf", original_filename="fixture.pdf",
        filename="stored.pdf", checksum_sha256=checksum,
        extracted_text=extracted_text, processing_status=status,
    )


def test_persisted_page_text_has_priority_and_does_not_read_original(tmp_path):
    page = SimpleNamespace(page_number=2, extracted_text="Zweryfikowany tekst strony", ocr_text=None)
    db = _ReadOnlyDb([page])
    extractor = _Extractor(pytest.fail)
    service = UnifiedDocumentContentService(db, data_root=tmp_path, extractor=extractor)

    result = service.access(_document(None), query="tekst")

    assert result.state == FILE_FOUND_NATIVE_TEXT_AVAILABLE
    assert result.pages[0].page_number == 2
    assert result.pages[0].origin == "persisted_page"
    assert extractor.calls == 0
    assert db.writes == 0


def test_persisted_ocr_text_is_available_without_file_access(tmp_path):
    page = SimpleNamespace(page_number=1, extracted_text=None, ocr_text="Tekst OCR strony")
    result = UnifiedDocumentContentService(_ReadOnlyDb([page]), data_root=tmp_path).access(
        _document(None)
    )
    assert result.state == FILE_FOUND_NATIVE_TEXT_AVAILABLE
    assert result.pages[0].text == "Tekst OCR strony"


def test_unprocessed_native_pdf_uses_read_only_ephemeral_pages(tmp_path):
    path = tmp_path / "fixture.pdf"
    path.write_bytes(b"synthetic-pdf-bytes")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    extractor = _Extractor(DocumentExtractionResult(
        status="extracted", text="grunt gliniasty osiadanie lokalne", extractor="pypdf",
        character_count=34,
        pages=(
            ExtractedDocumentPage(1, "wprowadzenie"),
            ExtractedDocumentPage(4, "grunt gliniasty osiadanie lokalne"),
        ),
    ))
    db = _ReadOnlyDb()
    result = UnifiedDocumentContentService(
        db, data_root=tmp_path, extractor=extractor
    ).access(_document(path, checksum=checksum), query="grunt osiadanie")

    assert result.state == FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE
    assert result.pages[0].page_number == 4
    assert result.pages[0].origin == "ephemeral_native"
    assert extractor.calls == 1
    assert db.writes == 0


@pytest.mark.parametrize("status,expected", [
    ("requires_ocr", FILE_FOUND_REQUIRES_OCR),
    ("unsupported", FILE_FOUND_UNSUPPORTED),
])
def test_terminal_extraction_states_are_distinct_and_do_not_write(tmp_path, status, expected):
    path = tmp_path / "fixture.pdf"
    path.write_bytes(b"fixture")
    extractor = _Extractor(DocumentExtractionResult(
        status=status, text=None, extractor="pypdf", character_count=0
    ))
    db = _ReadOnlyDb()
    result = UnifiedDocumentContentService(db, data_root=tmp_path, extractor=extractor).access(
        _document(path)
    )
    assert result.state == expected
    assert db.writes == 0


def test_missing_file_fails_before_extractor(tmp_path):
    missing = tmp_path / "missing.pdf"
    extractor = _Extractor(pytest.fail)
    result = UnifiedDocumentContentService(
        _ReadOnlyDb(), data_root=tmp_path, extractor=extractor
    ).access(_document(missing))
    assert result.state == FILE_NOT_FOUND
    assert extractor.calls == 0


def test_checksum_mismatch_fails_closed_before_extraction(tmp_path):
    path = tmp_path / "fixture.pdf"
    path.write_bytes(b"changed")
    extractor = _Extractor(pytest.fail)
    result = UnifiedDocumentContentService(
        _ReadOnlyDb(), data_root=tmp_path, extractor=extractor
    ).access(_document(path, checksum="0" * 64))
    assert result.state == INTEGRITY_MISMATCH
    assert result.error_code == "DOCUMENT_STORAGE_INTEGRITY_MISMATCH"
    assert extractor.calls == 0


def test_same_cached_content_is_bounded_to_eight_pages(tmp_path):
    path = tmp_path / "fixture.pdf"
    path.write_bytes(b"fixture")
    pages = tuple(ExtractedDocumentPage(index, f"strona {index} grunt") for index in range(1, 12))
    extractor = _Extractor(DocumentExtractionResult(
        status="extracted", text=" ".join(page.text for page in pages),
        extractor="pypdf", character_count=200, pages=pages,
    ))
    result = UnifiedDocumentContentService(
        _ReadOnlyDb(), data_root=tmp_path, extractor=extractor
    ).access(_document(path), query="grunt")
    assert len(result.pages) == 8
    assert sum(len(page.text) for page in result.pages) <= 12_000
