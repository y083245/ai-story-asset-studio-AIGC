"""FastAPI router for the Character Library module.

Prefix: /api
All endpoints require X-User-ID header (inherited from M01 pattern).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND, VALIDATION_ERROR
from app.db.session import get_session
from app.modules.character_library.deps import get_current_user_id
from app.modules.character_library.schemas import (
    CharacterListResponse,
    CharacterRegenerateResponse,
    CharacterResponse,
    CharacterUpdateRequest,
    ErrorResponse,
    ExtractedCharactersRequest,
    ExtractedCharactersResponse,
)
from app.modules.character_library.service import CharacterLibraryService
from app.modules.project.models import Project
from app.modules.provider_adapter.registry import ProviderRegistry

router = APIRouter(prefix="/api", tags=["character-library"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_provider() -> ProviderRegistry:
    """Return a ProviderRegistry for the current environment."""
    return ProviderRegistry()


# ---------------------------------------------------------------------------
# Ownership check helper
# ---------------------------------------------------------------------------


async def _check_project_ownership(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: str,
) -> Project:
    """Verify project exists and is owned by the current user.

    Raises 404 if not found, 403 if wrong user.
    """
    from sqlalchemy import select as _select

    stmt = _select(Project).where(Project.id == project_id)
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Project {project_id} not found",
                "retryable": False,
            },
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": FORBIDDEN.code,
                "message": "You do not have access to this project",
                "retryable": False,
            },
        )
    return project


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/characters/extract
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/characters/extract",
    response_model=ExtractedCharactersResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def extract_characters(
    project_id: uuid.UUID,
    body: ExtractedCharactersRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    registry: Annotated[ProviderRegistry, Depends(_get_provider)],
) -> ExtractedCharactersResponse:
    """Extract, deduplicate, and formalise character profiles from M05 candidates.

    Expects the output of M05 Text Understanding's StoryStructureAgent
    as input.  Runs the full pipeline:
    1. Alias merging (exact match + LLM-assisted semantic merge)
    2. Character ID assignment (CH_001, CH_002, ...)
    3. Consistency tag + forbidden_changes generation
    4. Reference-image plan generation
    5. Persistence to database
    """
    await _check_project_ownership(session, project_id, user_id)

    provider = registry.get_text_generator()

    try:
        result = await CharacterLibraryService.extract_characters(
            session=session,
            provider=provider,
            project_id=str(project_id),
            candidates=body.candidates,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return result


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/characters
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/characters",
    response_model=CharacterListResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_characters(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> CharacterListResponse:
    """List all characters belonging to a project."""
    await _check_project_ownership(session, project_id, user_id)

    items, total = await CharacterLibraryService.list_characters(session, project_id)

    return CharacterListResponse(
        project_id=project_id,
        characters=[CharacterResponse.model_validate(c) for c in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/characters/{character_id}
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/characters/{character_id}",
    response_model=CharacterResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_character(
    project_id: uuid.UUID,
    character_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> CharacterResponse:
    """Get a single character by project and character_id."""
    await _check_project_ownership(session, project_id, user_id)

    character = await CharacterLibraryService.get_character(session, project_id, character_id)
    if character is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Character {character_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    return CharacterResponse.model_validate(character)


# ---------------------------------------------------------------------------
# PATCH /api/projects/{project_id}/characters/{character_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/projects/{project_id}/characters/{character_id}",
    response_model=CharacterResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def update_character(
    project_id: uuid.UUID,
    character_id: str,
    body: CharacterUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> CharacterResponse:
    """Partial update of a character. Creates a version snapshot before mutating.

    Only supplied fields are updated.  The previous values are stored
    in a CharacterVersion row so history is never lost.
    """
    await _check_project_ownership(session, project_id, user_id)

    # Verify character exists and belongs to this project
    existing = await CharacterLibraryService.get_character(session, project_id, character_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Character {character_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    try:
        updated = await CharacterLibraryService.update_character(session, project_id, character_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return CharacterResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/characters/{character_id}/regenerate
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/characters/{character_id}/regenerate",
    response_model=CharacterRegenerateResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def regenerate_character(
    project_id: uuid.UUID,
    character_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> CharacterRegenerateResponse:
    """Request regeneration of character reference assets.

    This endpoint creates a pending generation_task record.
    The actual image generation is dispatched by the Workflow module
    calling M11 Image Asset — this module does NOT generate images.
    """
    await _check_project_ownership(session, project_id, user_id)

    task = await CharacterLibraryService.regenerate_character(session, project_id, character_id)

    return CharacterRegenerateResponse(
        task_id=task.id,
        character_id=character_id,
        status=task.status,
    )


# ---------------------------------------------------------------------------
# DELETE /api/projects/{project_id}/characters/{character_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}/characters/{character_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def delete_character(
    project_id: uuid.UUID,
    character_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Delete a character and its version history."""
    await _check_project_ownership(session, project_id, user_id)

    existing = await CharacterLibraryService.get_character(session, project_id, character_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Character {character_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    await CharacterLibraryService.delete_character(session, project_id, character_id)
