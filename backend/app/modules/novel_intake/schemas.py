"""Pydantic v2 request/response schemas for the Novel Intake module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared items
# ---------------------------------------------------------------------------


class ChapterItem(BaseModel):
    """A detected chapter."""

    title: str = Field(..., description="章节标题")
    start: int = Field(..., ge=0, description="起始段落索引（从 0 开始）")


class ChunkItem(BaseModel):
    """A semantic text chunk."""

    id: UUID
    chunk_index: int
    content: str
    start_char: int
    end_char: int
    word_count: int
    context_before: str = ""


class PreprocessReportItem(BaseModel):
    """Preprocessing statistics."""

    original_word_count: int = 0
    clean_word_count: int = 0
    ads_removed: int = 0
    page_numbers_removed: int = 0
    garbled_lines_removed: int = 0
    blank_lines_removed: int = 0
    encoding_detected: str = "utf-8"
    input_type: str = "text"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class NovelIntakeRequest(BaseModel):
    """Request to upload / paste a novel."""

    project_id: str | None = Field(default=None, description="项目 ID（UUID 字符串），可省略并使用 URL path")
    input_type: Literal["text", "txt", "docx"] = Field(..., description="输入类型：text | txt | docx")
    text: str | None = Field(default=None, description="直接粘贴的小说正文（input_type=text 时必填）")
    file_url: str | None = Field(default=None, description="文件下载 URL（input_type=txt|docx 时必填）")

    @field_validator("project_id")
    @classmethod
    def project_id_must_be_valid_uuid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            UUID(v)
        except ValueError as exc:
            raise ValueError("project_id must be a valid UUID") from exc
        return v

    @model_validator(mode="after")
    def _validate_input_requirements(self) -> NovelIntakeRequest:
        if self.input_type == "text" and not self.text:
            raise ValueError("text is required when input_type is 'text'")
        if self.input_type in ("txt", "docx") and not self.file_url:
            raise ValueError("file_url is required when input_type is 'txt' or 'docx'")
        return self


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class NovelIntakeResponse(BaseModel):
    """Response after successful novel intake."""

    novel_id: UUID
    title: str
    clean_text: str
    word_count: int
    chapter_list: list[ChapterItem]
    paragraph_list: list[str]
    text_chunks: list[ChunkItem]
    preprocess_report: PreprocessReportItem

    model_config = {"from_attributes": True}


class NovelDetailResponse(BaseModel):
    """Full novel detail."""

    id: UUID
    project_id: UUID
    title: str
    word_count: int
    clean_text: str
    chapter_list: dict[str, object]
    paragraph_list: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NovelChunkListResponse(BaseModel):
    """List of text chunks for a novel."""

    novel_id: UUID
    chunks: list[ChunkItem]
    total: int


# ---------------------------------------------------------------------------
# Error helpers (shared contract-style shapes)
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool


class ErrorResponse(BaseModel):
    error: ErrorDetail
