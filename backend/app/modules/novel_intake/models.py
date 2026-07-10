"""SQLAlchemy ORM models for the Novel Intake module.

Owns: novels, text_chunks, novel_preprocess_reports (exclusive write).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Novel(Base, UUIDMixin, TimestampMixin):
    """小说主表 — 一条记录对应一个项目的小说文本。"""

    __tablename__ = "novels"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="未命名小说")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chapter_list: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    paragraph_list: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    chunks: Mapped[list[TextChunk]] = relationship(
        "TextChunk", back_populates="novel", cascade="all, delete-orphan", order_by="TextChunk.chunk_index"
    )
    preprocess_report: Mapped[NovelPreprocessReport | None] = relationship(
        "NovelPreprocessReport", back_populates="novel", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Novel id={self.id!s} project_id={self.project_id!s} word_count={self.word_count}>"


class TextChunk(Base, UUIDMixin, TimestampMixin):
    """语义切片 — 小说的分块文本，含上下文窗口。"""

    __tablename__ = "text_chunks"

    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_before: Mapped[str] = mapped_column(Text, nullable=False, default="")

    novel: Mapped[Novel] = relationship("Novel", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<TextChunk id={self.id!s} novel_id={self.novel_id!s} index={self.chunk_index} words={self.word_count}>"


class NovelPreprocessReport(Base, UUIDMixin, TimestampMixin):
    """预处理报告 — 记录清洗和解析阶段的统计信息。"""

    __tablename__ = "novel_preprocess_reports"

    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    original_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clean_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ads_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_numbers_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    garbled_lines_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blank_lines_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    encoding_detected: Mapped[str] = mapped_column(String(50), nullable=False, default="utf-8")
    input_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")

    novel: Mapped[Novel] = relationship("Novel", back_populates="preprocess_report")

    def __repr__(self) -> str:
        return f"<NovelPreprocessReport novel_id={self.novel_id!s} clean={self.clean_word_count}>"
