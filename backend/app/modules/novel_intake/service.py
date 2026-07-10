"""Business logic for the Novel Intake module.

All database access goes through a single SQLAlchemy AsyncSession.
Handles novel parsing, cleaning, chapter detection, chunking, and persistence.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.enums import ProjectStatus
from app.contracts.errors import WORD_COUNT_OUT_OF_RANGE, ErrorCode
from app.modules.novel_intake.chapter_detector import chapters_to_dict, detect_chapters
from app.modules.novel_intake.chunker import chunk_text
from app.modules.novel_intake.cleaning import clean_text
from app.modules.novel_intake.models import Novel, NovelPreprocessReport, TextChunk
from app.modules.novel_intake.parser import parse_input
from app.modules.project.models import Project

# ---------------------------------------------------------------------------
# MVP word-count limits
# ---------------------------------------------------------------------------

MIN_WORD_COUNT: int = 1000
MAX_WORD_COUNT: int = 10000


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class NovelIntakeError(ValueError):
    """Base exception for novel intake errors."""

    def __init__(self, error_code: ErrorCode, message: str | None = None) -> None:
        self.error_code = error_code
        self._message = message or error_code.message
        super().__init__(self._message)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class NovelIntakeService:
    """Stateless novel intake service.

    All methods receive an open AsyncSession and return domain objects.
    Callers (router layer) convert to Pydantic response schemas.
    """

    # ------------------------------------------------------------------
    # Intake (the main pipeline)
    # ------------------------------------------------------------------

    @staticmethod
    async def intake_novel(
        session: AsyncSession,
        project_id: uuid.UUID,
        input_type: str,
        text: str | None = None,
        file_name: str = "",
        file_bytes: bytes | None = None,
    ) -> Novel:
        """Run the full novel intake pipeline.

        1. Parse input text
        2. Clean text
        3. Detect chapters
        4. Split into paragraphs
        5. Create semantic chunks
        6. Validate word count
        7. Persist to database
        8. Update project status to UPLOADED

        Returns the created Novel ORM object.
        """
        # --- Step 0: Verify project exists ---
        project = await NovelIntakeService._require_project(session, project_id)
        await NovelIntakeService._delete_existing_novel(session, project_id)

        # --- Step 1: Parse ---
        parse_result = parse_input(
            input_type=input_type,
            text=text,
            file_bytes=file_bytes,
            file_name=file_name,
        )

        # --- Step 2: Clean ---
        cleaned_text, cleaning_report = clean_text(parse_result.raw_text)

        # --- Step 3: Word count validation ---
        if cleaning_report.clean_word_count < MIN_WORD_COUNT:
            raise NovelIntakeError(
                WORD_COUNT_OUT_OF_RANGE,
                f"Novel text is too short: {cleaning_report.clean_word_count} words. Minimum is {MIN_WORD_COUNT}.",
            )
        if cleaning_report.clean_word_count > MAX_WORD_COUNT:
            raise NovelIntakeError(
                WORD_COUNT_OUT_OF_RANGE,
                f"Novel text is too long: {cleaning_report.clean_word_count} words. Maximum is {MAX_WORD_COUNT}.",
            )

        # --- Step 4: Paragraph list ---
        paragraph_list = [p for p in cleaned_text.split("\n") if p.strip()]

        # --- Step 5: Chapter detection ---
        chapters = detect_chapters(paragraph_list)
        chapter_dict = chapters_to_dict(chapters)

        # --- Step 6: Semantic chunking ---
        chunk_results = chunk_text(cleaned_text)

        # --- Step 7: Persist Novel ---
        novel = Novel(
            project_id=project_id,
            title=parse_result.raw_text[:100].strip().replace("\n", " ") or "未命名小说",
            word_count=cleaning_report.clean_word_count,
            clean_text=cleaned_text,
            chapter_list=chapter_dict,
            paragraph_list=paragraph_list,
            status="active",
        )
        session.add(novel)
        await session.flush()

        # --- Step 8: Persist chunks ---
        for cr in chunk_results:
            chunk = TextChunk(
                novel_id=novel.id,
                chunk_index=cr.chunk_index,
                content=cr.content,
                start_char=cr.start_char,
                end_char=cr.end_char,
                word_count=cr.word_count,
                context_before=cr.context_before,
            )
            session.add(chunk)

        # --- Step 9: Persist preprocess report ---
        report = NovelPreprocessReport(
            novel_id=novel.id,
            original_word_count=cleaning_report.original_word_count,
            clean_word_count=cleaning_report.clean_word_count,
            ads_removed=cleaning_report.ads_removed,
            page_numbers_removed=cleaning_report.page_numbers_removed,
            garbled_lines_removed=cleaning_report.garbled_lines_removed,
            blank_lines_removed=cleaning_report.blank_lines_removed,
            encoding_detected=parse_result.encoding,
            input_type=parse_result.input_type,
        )
        session.add(report)

        # --- Step 10: Update project status ---
        project.status = ProjectStatus.UPLOADED

        await session.flush()

        return novel

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    async def get_novel_by_project(session: AsyncSession, project_id: uuid.UUID) -> Novel | None:
        """Return the novel for a project, or None."""
        stmt = select(Novel).where(Novel.project_id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_chunks(session: AsyncSession, novel_id: uuid.UUID) -> list[TextChunk]:
        """Return all text chunks for a novel, ordered by chunk_index."""
        stmt = select(TextChunk).where(TextChunk.novel_id == novel_id).order_by(TextChunk.chunk_index)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_preprocess_report(session: AsyncSession, novel_id: uuid.UUID) -> NovelPreprocessReport | None:
        """Return the preprocess report for a novel."""
        stmt = select(NovelPreprocessReport).where(NovelPreprocessReport.novel_id == novel_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _require_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
        """Fetch a project or raise ValueError."""
        stmt = select(Project).where(Project.id == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id!s} not found")
        return project

    @staticmethod
    async def _delete_existing_novel(session: AsyncSession, project_id: uuid.UUID) -> None:
        """Delete the existing project novel so re-upload replaces it cleanly."""
        existing = await NovelIntakeService.get_novel_by_project(session, project_id)
        if existing is None:
            return
        await session.delete(existing)
        await session.flush()
