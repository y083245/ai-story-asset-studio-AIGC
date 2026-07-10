"""FastAPI router for the Novel Intake module.

Prefix: /api
All endpoints require X-User-ID header.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND, UNSUPPORTED_FORMAT, VALIDATION_ERROR
from app.db.session import get_session
from app.modules.novel_intake.deps import get_current_user_id
from app.modules.novel_intake.parser import PdfRejectedError
from app.modules.novel_intake.schemas import (
    ChapterItem,
    ChunkItem,
    ErrorDetail,
    ErrorResponse,
    NovelChunkListResponse,
    NovelDetailResponse,
    NovelIntakeRequest,
    NovelIntakeResponse,
    PreprocessReportItem,
)
from app.modules.novel_intake.service import NovelIntakeError, NovelIntakeService

router = APIRouter(prefix="/api", tags=["novel-intake"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _check_project_ownership(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: str,
) -> None:
    """Verify the project exists and belongs to the user. Raise HTTPException otherwise."""
    from app.modules.novel_intake.service import NovelIntakeService

    try:
        project = await NovelIntakeService._require_project(session, project_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        ) from None

    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/novel
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/novel",
    response_model=NovelIntakeResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def upload_novel(
    project_id: uuid.UUID,
    body: NovelIntakeRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> NovelIntakeResponse:
    """Upload or paste a novel for a project.

    Supports input_type:
    - ``text``: Paste the novel text directly in the ``text`` field.
    - ``txt``: Provide a ``file_url`` pointing to a .txt file.
    - ``docx``: Provide a ``file_url`` pointing to a .docx file.

    PDF files are explicitly rejected.
    The novel text must be between 1000 and 10000 Chinese characters.
    """
    if body.project_id is not None and uuid.UUID(body.project_id) != project_id:
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=VALIDATION_ERROR.code,
                    message="project_id in request body must match the URL path project_id",
                    retryable=False,
                )
            ).model_dump()["error"],
        )

    # Ownership check
    await _check_project_ownership(session, project_id, user_id)

    # If file_url is provided, download the file bytes
    file_bytes: bytes | None = None
    file_name: str = ""
    if body.file_url:
        file_name = body.file_url.rsplit("/", 1)[-1] if "/" in body.file_url else body.file_url

        # Check for PDF before downloading
        if file_name.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=UNSUPPORTED_FORMAT.code,
                        message=UNSUPPORTED_FORMAT.message + f" PDF is not supported. File: {file_name}",
                        retryable=False,
                    )
                ).model_dump()["error"],
            )

        # Download file via StorageService
        from app.modules.storage.service import StorageService

        storage = StorageService.create()
        try:
            file_bytes = await storage.download(body.file_url)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=NOT_FOUND.code,
                        message=f"Failed to download file: {exc}",
                        retryable=False,
                    )
                ).model_dump()["error"],
            ) from exc
        finally:
            await storage.close()

    # Run intake pipeline
    try:
        novel = await NovelIntakeService.intake_novel(
            session=session,
            project_id=project_id,
            input_type=body.input_type,
            text=body.text,
            file_name=file_name,
            file_bytes=file_bytes,
        )
    except PdfRejectedError as exc:
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=UNSUPPORTED_FORMAT.code,
                    message=str(exc),
                    retryable=False,
                )
            ).model_dump()["error"],
        ) from exc
    except NovelIntakeError as exc:
        status_code = 422
        raise HTTPException(
            status_code=status_code,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=exc.error_code.code,
                    message=str(exc),
                    retryable=exc.error_code.retryable,
                )
            ).model_dump()["error"],
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=UNSUPPORTED_FORMAT.code,
                    message=str(exc),
                    retryable=False,
                )
            ).model_dump()["error"],
        ) from exc

    # Build chunk items
    chunks = await NovelIntakeService.get_chunks(session, novel.id)
    chunk_items = [
        ChunkItem(
            id=c.id,
            chunk_index=c.chunk_index,
            content=c.content,
            start_char=c.start_char,
            end_char=c.end_char,
            word_count=c.word_count,
            context_before=c.context_before,
        )
        for c in chunks
    ]

    # Build chapter items
    chapter_dict: dict[str, object] = novel.chapter_list if isinstance(novel.chapter_list, dict) else {}
    chapter_list_raw: list[dict[str, object]] = chapter_dict.get("chapters", [])  # type: ignore[assignment]
    chapter_items = [
        ChapterItem(
            title=str(ch.get("title", "")),
            start=int(ch.get("start", 0)),  # type: ignore[call-overload]
        )
        for ch in chapter_list_raw
    ]

    # Build report
    report = await NovelIntakeService.get_preprocess_report(session, novel.id)
    report_item = PreprocessReportItem(
        original_word_count=report.original_word_count if report else 0,
        clean_word_count=report.clean_word_count if report else 0,
        ads_removed=report.ads_removed if report else 0,
        page_numbers_removed=report.page_numbers_removed if report else 0,
        garbled_lines_removed=report.garbled_lines_removed if report else 0,
        blank_lines_removed=report.blank_lines_removed if report else 0,
        encoding_detected=report.encoding_detected if report else "utf-8",
        input_type=report.input_type if report else body.input_type,
    )

    return NovelIntakeResponse(
        novel_id=novel.id,
        title=novel.title,
        clean_text=novel.clean_text,
        word_count=novel.word_count,
        chapter_list=chapter_items,
        paragraph_list=novel.paragraph_list if isinstance(novel.paragraph_list, list) else [],
        text_chunks=chunk_items,
        preprocess_report=report_item,
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/novel
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/novel",
    response_model=NovelDetailResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_novel(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> NovelDetailResponse:
    """Get the novel detail for a project."""
    await _check_project_ownership(session, project_id, user_id)

    novel = await NovelIntakeService.get_novel_by_project(session, project_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"No novel found for project {project_id}",
                    retryable=False,
                )
            ).model_dump()["error"],
        )

    return NovelDetailResponse(
        id=novel.id,
        project_id=novel.project_id,
        title=novel.title,
        word_count=novel.word_count,
        clean_text=novel.clean_text,
        chapter_list=novel.chapter_list if isinstance(novel.chapter_list, dict) else {},
        paragraph_list=novel.paragraph_list if isinstance(novel.paragraph_list, list) else [],
        status=novel.status,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/novel/chunks
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/novel/chunks",
    response_model=NovelChunkListResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_novel_chunks(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> NovelChunkListResponse:
    """Get the text chunk list for a project's novel."""
    await _check_project_ownership(session, project_id, user_id)

    novel = await NovelIntakeService.get_novel_by_project(session, project_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"No novel found for project {project_id}",
                    retryable=False,
                )
            ).model_dump()["error"],
        )

    chunks = await NovelIntakeService.get_chunks(session, novel.id)
    chunk_items = [
        ChunkItem(
            id=c.id,
            chunk_index=c.chunk_index,
            content=c.content,
            start_char=c.start_char,
            end_char=c.end_char,
            word_count=c.word_count,
            context_before=c.context_before,
        )
        for c in chunks
    ]

    return NovelChunkListResponse(
        novel_id=novel.id,
        chunks=chunk_items,
        total=len(chunk_items),
    )
