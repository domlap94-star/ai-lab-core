from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["norms", "technical_datasheets", "manuals", "producer_materials", "formulas", "reference_calculations", "other"]


class KnowledgeBaseMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(None, max_length=255)
    version: str | None = Field(None, max_length=100)
    effective_date: date | None = None
    category: Category
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["current", "superseded"] = "current"
    supersedes_id: int | None = Field(None, gt=0)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in value:
            tag = " ".join(raw.split()).strip()
            if not tag or len(tag) > 50:
                raise ValueError("knowledge_base_tag_invalid")
            key = tag.casefold()
            if key not in seen:
                seen.add(key); result.append(tag)
        return result


class KnowledgeBasePatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    source: str | None = Field(None, min_length=1, max_length=500)
    publisher: str | None = Field(None, max_length=255)
    version: str | None = Field(None, max_length=100)
    effective_date: date | None = None
    category: Category | None = None
    tags: list[str] | None = Field(None, max_length=20)
    status: Literal["current", "superseded"] | None = None
    supersedes_id: int | None = Field(None, gt=0)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else KnowledgeBaseMetadata.normalize_tags(value)


class KnowledgeBasePageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; page_number: int; text: str | None; extraction_method: str; confidence: float | None


class KnowledgeBaseItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; title: str; source: str; publisher: str | None; version: str | None
    effective_date: date | None; category: str; tags: list[str]; status: str; supersedes_id: int | None
    original_filename: str; content_type: str; file_size: int; checksum_sha256: str
    processing_status: str; processing_method: str | None; processing_error: str | None
    created_at: datetime; updated_at: datetime
    pages: list[KnowledgeBasePageRead] = Field(default_factory=list)


class KnowledgeBasePageResult(BaseModel):
    items: list[KnowledgeBaseItemRead]; total: int; skip: int; limit: int


class KnowledgeBaseUploadResponse(BaseModel):
    item: KnowledgeBaseItemRead
    duplicate_checksum_item_ids: list[int] = Field(default_factory=list)


class KnowledgeBaseSearchResult(BaseModel):
    knowledge_base_item_id: int; title: str; publisher: str | None; version: str | None
    effective_date: date | None; category: str; status: str; source_file: str
    page: int | None; excerpt: str; retrieval_method: Literal["lexical"] = "lexical"
