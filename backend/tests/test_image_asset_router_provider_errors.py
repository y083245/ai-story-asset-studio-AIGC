from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.image_asset.schemas import GenerateAssetRequest, GenerationTaskResponse
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode


class _FailingGenerateService:
    def __init__(self, error: ProviderError) -> None:
        self.error = error

    async def generate_asset(self, request: GenerateAssetRequest, session: object) -> object:
        raise self.error


class _CommitTrackingSession:
    def __init__(self) -> None:
        self.committed = False
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")
        self.committed = True


class _CreateGenerationJobService:
    def __init__(self, task_id: uuid.UUID, project_id: uuid.UUID) -> None:
        self.task_id = task_id
        self.project_id = project_id

    async def create_generation_job(self, request: GenerateAssetRequest, session: _CommitTrackingSession) -> object:
        session.events.append("create_task_record")
        return SimpleNamespace(id=self.task_id, project_id=self.project_id)


class _TaskStatusService:
    def __init__(self, response: GenerationTaskResponse) -> None:
        self.response = response

    async def get_task(self, task_id: uuid.UUID, session: object) -> GenerationTaskResponse:
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_status"),
    [
        (
            ProviderError(
                code=ProviderErrorCode.INVALID_REQUEST,
                message="[seedream] reference image count exceeds 10",
                provider="seedream",
                retryable=False,
                raw_error="secret-key-should-not-leak",
            ),
            400,
        ),
        (
            ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="[seedream] request failed with HTTP 500: upstream unavailable",
                provider="seedream",
                retryable=True,
                raw_error="secret-key-should-not-leak",
            ),
            502,
        ),
    ],
)
async def test_generate_asset_maps_provider_errors_to_client_safe_http_status(
    monkeypatch: pytest.MonkeyPatch,
    provider_error: ProviderError,
    expected_status: int,
) -> None:
    from app.modules.image_asset import router as router_module

    async def _skip_project_ownership(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(router_module, "_check_project_ownership", _skip_project_ownership)

    with pytest.raises(HTTPException) as exc_info:
        await router_module.generate_asset(
            body=GenerateAssetRequest(
                project_id=uuid.uuid4(),
                asset_type="character_front",
                related_id="CH_001",
            ),
            session=object(),
            user_id="user-1",
            service=_FailingGenerateService(provider_error),
        )

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == {
        "code": provider_error.code.value,
        "message": provider_error.message,
        "retryable": provider_error.retryable,
    }
    assert "secret-key-should-not-leak" not in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_generate_asset_does_not_wrap_provider_item_error_as_500(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.image_asset import router as router_module

    async def _skip_project_ownership(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(router_module, "_check_project_ownership", _skip_project_ownership)
    error = ProviderError(
        code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
        message="[seedream] image generation item failed: internal service error",
        provider="seedream",
        retryable=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await router_module.generate_asset(
            body=GenerateAssetRequest(
                project_id=uuid.uuid4(),
                asset_type="character_front",
                related_id="CH_001",
            ),
            session=object(),
            user_id="user-1",
            service=_FailingGenerateService(error),
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["code"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_create_generation_job_commits_before_scheduling_background_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.image_asset import router as router_module

    project_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = _CommitTrackingSession()
    scheduled_after_commit: list[bool] = []

    async def _skip_project_ownership(*args: object, **kwargs: object) -> None:
        return None

    async def _fake_execute_generation_job(task_id_arg: str) -> None:
        return None

    def _fake_create_task(coro: object) -> object:
        session.events.append("schedule_background")
        scheduled_after_commit.append(session.committed)
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return object()

    monkeypatch.setattr(router_module, "_check_project_ownership", _skip_project_ownership)
    monkeypatch.setattr(router_module, "execute_generation_job", _fake_execute_generation_job)
    monkeypatch.setattr(router_module.asyncio, "create_task", _fake_create_task)

    response = await router_module.create_generation_job(
        body=GenerateAssetRequest(
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
        ),
        session=session,  # type: ignore[arg-type]
        user_id="user-1",
        service=_CreateGenerationJobService(task_id, project_id),  # type: ignore[arg-type]
    )

    assert response.task_id == task_id
    assert response.project_id == project_id
    assert response.polling_url == f"/api/image-asset/tasks/{task_id}"
    assert session.events == ["create_task_record", "commit", "schedule_background"]
    assert scheduled_after_commit == [True]


@pytest.mark.asyncio
async def test_get_task_checks_project_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.image_asset import router as router_module

    project_id = uuid.uuid4()
    task_id = uuid.uuid4()
    checked: list[tuple[uuid.UUID, str]] = []

    async def _record_project_ownership(session: object, project_id_arg: uuid.UUID, user_id: str) -> None:
        checked.append((project_id_arg, user_id))

    monkeypatch.setattr(router_module, "_check_project_ownership", _record_project_ownership)

    response = GenerationTaskResponse(
        task_id=task_id,
        project_id=project_id,
        asset_type="character_front",
        related_id="CH_001",
        provider="seedream",
        model_name="seedream-4.0",
        status="success",
        retry_count=0,
        max_retries=3,
        error_message=None,
        quality_status=None,
        quality_report_id=None,
        asset_id=uuid.uuid4(),
        storage_path="projects/demo/front.png",
    )

    result = await router_module.get_task(
        task_id=task_id,
        session=object(),  # type: ignore[arg-type]
        user_id="user-1",
        service=_TaskStatusService(response),  # type: ignore[arg-type]
    )

    assert result.storage_path == "projects/demo/front.png"
    assert checked == [(project_id, "user-1")]
