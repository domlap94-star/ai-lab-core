from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage


VisionClassification = Literal[
    "text_sufficient", "vision_required", "vision_optional", "unsupported"
]


@dataclass(frozen=True)
class VisionSourceCandidate:
    page: DocumentPage | None = None
    asset: DocumentAsset | None = None
    use_document_file: bool = False


@dataclass(frozen=True)
class VisionClassificationResult:
    classification: VisionClassification
    reason: str
    sources: tuple[VisionSourceCandidate, ...] = ()
    partial: bool = False


class VisionNeedClassifier:
    MAX_AUTOMATIC_PAGES = 8
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}
    IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif", "image/tiff", "image/bmp"}
    PDF_TYPES = {"application/pdf"}
    VISUAL_CLUES = {
        "rysunek", "rys.", "schemat", "wykres", "mapa", "plan", "rzut",
        "przekrój", "przekroj", "profil", "fundament", "warstwy gruntu",
        "figura", "diagram", "detal konstrukcyjny",
    }

    def classify(
        self, *, document: Document, pages: list[DocumentPage], assets: list[DocumentAsset]
    ) -> VisionClassificationResult:
        extension = Path(document.original_filename or document.filename or "").suffix.casefold()
        content_type = (document.content_type or "").casefold()
        if extension in self.IMAGE_EXTENSIONS or content_type in self.IMAGE_TYPES:
            if not pages:
                return VisionClassificationResult("vision_optional", "IMAGE_AWAITS_NORMAL_PROCESSING")
            page = pages[0]
            if page.width and page.height and page.width <= 96 and page.height <= 96 and not document.inspection_id:
                return VisionClassificationResult("text_sufficient", "TINY_DECORATIVE_IMAGE")
            required = bool(document.inspection_id or document.client_id)
            return VisionClassificationResult(
                "vision_required" if required else "vision_optional",
                "TECHNICAL_OR_SCOPED_IMAGE" if required else "STANDALONE_IMAGE",
                (VisionSourceCandidate(page=page, use_document_file=True),),
            )
        is_pdf_or_rendered = extension == ".pdf" or content_type in self.PDF_TYPES or bool(pages)
        if is_pdf_or_rendered:
            if not pages:
                return VisionClassificationResult("vision_optional", "DOCUMENT_AWAITS_PAGE_RENDER")
            candidates: list[VisionSourceCandidate] = []
            for page in pages:
                text = " ".join(filter(None, (page.extracted_text, page.ocr_text))).casefold()
                weak_text = len(text.strip()) < 80
                weak_ocr = page.ocr_confidence is not None and page.ocr_confidence < 55
                clue = any(token in text for token in self.VISUAL_CLUES)
                page_visual = (page.page_type or "").casefold() in {"scan", "drawing", "diagram", "map", "chart", "plan"}
                if page.render_path and (weak_text or weak_ocr or clue or page_visual):
                    candidates.append(VisionSourceCandidate(page=page))
            for asset in assets:
                if self._valuable_asset(asset):
                    candidates.append(VisionSourceCandidate(asset=asset))
            if not candidates:
                return VisionClassificationResult("text_sufficient", "EXTRACTED_TEXT_SUFFICIENT")
            bounded = tuple(candidates[: self.MAX_AUTOMATIC_PAGES])
            return VisionClassificationResult(
                "vision_required" if any((item.page and len(" ".join(filter(None, (item.page.extracted_text, item.page.ocr_text)))) < 80) for item in bounded) else "vision_optional",
                "VISUAL_PAGES_OR_ASSETS_SELECTED",
                bounded,
                len(candidates) > len(bounded),
            )
        if extension in {".txt", ".csv", ".json", ".xml", ".eml", ".html", ".md"} or (document.extracted_text or "").strip():
            return VisionClassificationResult("text_sufficient", "TEXT_DOCUMENT")
        return VisionClassificationResult("unsupported", "NO_SAFE_VISUAL_RENDER")

    @staticmethod
    def _valuable_asset(asset: DocumentAsset) -> bool:
        mime = (asset.mime_type or "").casefold()
        if not mime.startswith("image/"):
            return False
        if asset.width and asset.height and asset.width <= 96 and asset.height <= 96:
            return False
        return asset.processing_status not in {"failed", "unsupported"}
