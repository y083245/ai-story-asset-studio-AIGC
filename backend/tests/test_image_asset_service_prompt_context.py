from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from app.contracts.enums import TaskStatus
from app.modules.image_asset import service as image_asset_service
from app.modules.image_asset.lifecycle import compute_expires_at
from app.modules.image_asset.prompt_builder import build_scene_empty_prompt
from app.modules.image_asset.schemas import GenerateAssetRequest
from app.modules.image_asset.service import ImageAssetService, _GenerateContext, execute_generation_job
from app.modules.provider_adapter.base import ImageGenerationResponse


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value


class _FakeSession:
    def __init__(self, results: list[Any]) -> None:
        self._results = [_FakeResult(result) for result in results]
        self.flushed = False
        self.added: list[Any] = []

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def execute(self, _statement: Any) -> _FakeResult:
        return self._results.pop(0)

    async def flush(self) -> None:
        self.flushed = True


class _FakeGenerationJobSession:
    def __init__(self, task: SimpleNamespace) -> None:
        self.task = task
        self.events: list[str] = []
        self.commit_count = 0
        self.added: list[Any] = []

    async def __aenter__(self) -> _FakeGenerationJobSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: Any) -> _FakeResult:
        self.events.append("execute")
        return _FakeResult(self.task)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.events.append(f"flush:{_task_status_value(self.task.status)}")

    async def commit(self) -> None:
        self.commit_count += 1
        self.events.append(f"commit:{_task_status_value(self.task.status)}")

    async def rollback(self) -> None:
        self.events.append("rollback")


def _task_status_value(status: Any) -> str:
    return str(getattr(status, "value", status))


class _FakeStorage:
    async def upload(self, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            url="/local-storage/projects/demo/characters/CH_001/front.png",
            asset_id="projects/demo/characters/CH_001/front.png",
        )

    async def download(self, _asset_id: str) -> bytes:
        return b""


@pytest.mark.asyncio
async def test_image_asset_service_passes_latest_story_bible_snapshot_to_prompt_builder(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, Any] = {}

    def fake_build_character_image_prompt(**kwargs: Any) -> tuple[str, str]:
        seen.update(kwargs)
        return "prompt", "negative"

    monkeypatch.setattr(image_asset_service, "build_character_image_prompt", fake_build_character_image_prompt)
    project_id = uuid.uuid4()
    session = _FakeSession(
        [
            SimpleNamespace(character_id="CH_001", name="苏晚晴"),
            SimpleNamespace(snapshot={"style_id": "cyberpunk", "story_summary": "雨夜追踪"}),
        ]
    )
    service = ImageAssetService(image_provider=SimpleNamespace(), storage_service=SimpleNamespace())

    prompt, negative = await service._build_character_prompt(
        _GenerateContext(
            project_id=str(project_id),
            asset_type="character_front",
            related_id="CH_001",
            reference_asset_ids=[],
            extra_constraints=None,
        ),
        session,  # type: ignore[arg-type]
    )

    assert (prompt, negative) == ("prompt", "negative")
    assert seen["story_bible"] == {"style_id": "cyberpunk", "story_summary": "雨夜追踪"}
    assert seen["image_type"] == "character_front"


@pytest.mark.asyncio
async def test_image_asset_service_build_prompt_preview_uses_generation_prompt_builder(
    monkeypatch: pytest.MonkeyPatch,
):
    seen: dict[str, Any] = {}

    async def fake_build_prompt(ctx: _GenerateContext, _session: Any) -> tuple[str, str]:
        seen["ctx"] = ctx
        return "最终正向 prompt", "最终负向 prompt"

    service = ImageAssetService(image_provider=SimpleNamespace(), storage_service=SimpleNamespace())
    monkeypatch.setattr(service, "_build_prompt", fake_build_prompt)
    project_id = uuid.uuid4()

    preview = await service.build_prompt_preview(
        GenerateAssetRequest(
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            reference_asset_ids=["projects/p1/characters/CH_001/front.png"],
            extra_constraints="保持电影写实",
        ),
        SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert preview.prompt == "最终正向 prompt"
    assert preview.negative_prompt == "最终负向 prompt"
    assert seen["ctx"] == _GenerateContext(
        project_id=str(project_id),
        asset_type="character_front",
        related_id="CH_001",
        reference_asset_ids=["projects/p1/characters/CH_001/front.png"],
        extra_constraints="保持电影写实",
    )


@pytest.mark.asyncio
async def test_image_asset_service_replaces_previous_same_character_reference_asset():
    project_id = uuid.uuid4()
    owner = SimpleNamespace(
        reference_assets=[
            f"projects/{project_id}/characters/CH_001/front.png",
            f"projects/{project_id}/characters/CH_001/turnaround.jpg",
        ]
    )
    session = _FakeSession([owner])
    service = ImageAssetService(image_provider=SimpleNamespace(), storage_service=SimpleNamespace())

    await service._append_reference_to_owner(
        _GenerateContext(
            project_id=str(project_id),
            asset_type="character_front",
            related_id="CH_001",
            reference_asset_ids=[],
            extra_constraints=None,
        ),
        f"projects/{project_id}/characters/CH_001/front.jpg",
        session,  # type: ignore[arg-type]
    )

    assert owner.reference_assets == [
        f"projects/{project_id}/characters/CH_001/front.jpg",
        f"projects/{project_id}/characters/CH_001/turnaround.jpg",
    ]
    assert session.flushed is True


@pytest.mark.asyncio
async def test_upload_and_create_asset_sets_lifecycle_expiry():
    project_id = uuid.uuid4()
    session = _FakeSession([])
    task = SimpleNamespace(id=uuid.uuid4())
    service = ImageAssetService(image_provider=SimpleNamespace(), storage_service=_FakeStorage())  # type: ignore[arg-type]

    asset = await service._upload_and_create_asset(
        ctx=_GenerateContext(
            project_id=str(project_id),
            asset_type="character_front",
            related_id="CH_001",
            reference_asset_ids=[],
            extra_constraints=None,
        ),
        db=session,  # type: ignore[arg-type]
        task=task,  # type: ignore[arg-type]
        prompt="prompt",
        negative_prompt="negative",
        model_name="fake-model",
        provider_task_id="provider-task",
        image_bytes=b"\x89PNG\r\n\x1a\nfake",
        width=1440,
        height=2560,
    )

    assert session.added == [asset]
    assert asset.created_at is not None
    assert asset.updated_at == asset.created_at
    assert asset.expires_at == compute_expires_at(asset.created_at)
    assert asset.expires_at - asset.created_at > timedelta(days=170)


@pytest.mark.asyncio
async def test_execute_generation_job_commits_running_status_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.modules.provider_adapter import registry as registry_module
    from app.modules.storage import service as storage_module

    task_id = uuid.uuid4()
    project_id = uuid.uuid4()
    task = SimpleNamespace(
        id=task_id,
        project_id=project_id,
        asset_type="character_front",
        related_id="CH_001",
        request_json={
            "prompt": "prompt",
            "negative_prompt": "negative",
            "width": 1440,
            "height": 2560,
            "timeout_seconds": 120,
            "reference_asset_ids": [],
        },
        status=TaskStatus.PENDING,
        model_name="fake-model",
        error_message=None,
    )
    session = _FakeGenerationJobSession(task)

    class _InspectingProvider:
        provider_id = "fake-seedream"
        model_name = "fake-model"

        async def generate(self, _request: Any) -> object:
            session.events.append(f"generate_after_commits:{session.commit_count}")
            raise RuntimeError("stop after running")

    class _Registry:
        def get_image_generator(self) -> _InspectingProvider:
            return _InspectingProvider()

    monkeypatch.setattr(image_asset_service, "async_session_factory", lambda: session)
    monkeypatch.setattr(registry_module, "ProviderRegistry", _Registry)
    monkeypatch.setattr(storage_module.StorageService, "create", lambda: SimpleNamespace())

    await execute_generation_job(str(task_id))

    assert "commit:running" in session.events
    assert "generate_after_commits:1" in session.events
    assert session.events[-1] == "commit:failed"


@pytest.mark.asyncio
async def test_execute_generation_job_sets_lifecycle_expiry_on_created_asset(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.modules.provider_adapter import registry as registry_module
    from app.modules.storage import service as storage_module

    task_id = uuid.uuid4()
    project_id = uuid.uuid4()
    task = SimpleNamespace(
        id=task_id,
        project_id=project_id,
        asset_type="character_front",
        related_id=None,
        request_json={
            "prompt": "prompt",
            "negative_prompt": "negative",
            "width": 1440,
            "height": 2560,
            "timeout_seconds": 120,
            "reference_asset_ids": [],
        },
        status=TaskStatus.PENDING,
        model_name="fake-model",
        error_message=None,
    )
    session = _FakeGenerationJobSession(task)

    class _SuccessfulProvider:
        provider_id = "fake-seedream"
        model_name = "fake-model"

        async def generate(self, _request: Any) -> ImageGenerationResponse:
            return ImageGenerationResponse(
                images=[b"\x89PNG\r\n\x1a\nfake"],
                image_urls=["/local-storage/projects/demo/characters/CH_001/front.png"],
                model="fake-model",
                provider_task_id="provider-task",
            )

    class _Registry:
        def get_image_generator(self) -> _SuccessfulProvider:
            return _SuccessfulProvider()

    monkeypatch.setattr(image_asset_service, "async_session_factory", lambda: session)
    monkeypatch.setattr(registry_module, "ProviderRegistry", _Registry)
    monkeypatch.setattr(storage_module.StorageService, "create", lambda: _FakeStorage())

    await execute_generation_job(str(task_id))

    assert task.status == TaskStatus.SUCCESS
    assert len(session.added) == 1
    asset = session.added[0]
    assert asset.created_at is not None
    assert asset.updated_at == asset.created_at
    assert asset.expires_at == compute_expires_at(asset.created_at)


@pytest.mark.asyncio
async def test_image_asset_service_legacy_mode_does_not_load_story_bible_context(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, Any] = {}

    def fake_build_character_image_prompt(**kwargs: Any) -> tuple[str, str]:
        seen.update(kwargs)
        return "prompt", "negative"

    monkeypatch.setattr(settings, "prompt_engine_mode", "legacy")
    monkeypatch.setattr(image_asset_service, "build_character_image_prompt", fake_build_character_image_prompt)
    project_id = uuid.uuid4()
    session = _FakeSession([SimpleNamespace(character_id="CH_001", name="苏晚晴")])
    service = ImageAssetService(image_provider=SimpleNamespace(), storage_service=SimpleNamespace())

    await service._build_character_prompt(
        _GenerateContext(
            project_id=str(project_id),
            asset_type="character_front",
            related_id="CH_001",
            reference_asset_ids=[],
            extra_constraints=None,
        ),
        session,  # type: ignore[arg-type]
    )

    assert seen["story_bible"] is None


@pytest.mark.asyncio
async def test_story_bible_context_fallback_preserves_visual_style_without_version_snapshot():
    project_id = uuid.uuid4()
    service = ImageAssetService(image_provider=SimpleNamespace(), storage_service=SimpleNamespace())
    session = _FakeSession(
        [
            None,
            SimpleNamespace(
                project_id=project_id,
                version=3,
                title="",
                genre="小说",
                visual_style="未来科幻电影类",
                aspect_ratio="16:9",
                story_summary="",
                main_conflict="",
                emotional_tone="",
                world_setting="",
                time_period="",
                color_palette=[],
                composition_language=[],
                characters=[],
                scenes=[],
                props=[],
                negative_prompt_rules=[],
            ),
        ]
    )

    context = await service._load_story_bible_context(project_id, session)  # type: ignore[arg-type]
    prompt, _ = build_scene_empty_prompt(
        SimpleNamespace(scene_name="空港机库", scene_type="室内", fixed_anchors=[]),
        story_bible=context,
    )

    assert context["genre"] == "小说"
    assert context["visual_style"] == "未来科幻电影类"
    assert "未来科幻" in prompt
