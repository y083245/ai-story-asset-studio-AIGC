from __future__ import annotations

from typing import Any

import pytest

from app.modules.observability.provider_log import log_provider_call


class _FakeLogger:
    def __init__(self) -> None:
        self.info_calls: list[tuple[str, dict[str, Any]]] = []
        self.error_calls: list[tuple[str, dict[str, Any]]] = []

    def info(self, message: str, **kwargs: Any) -> None:
        self.info_calls.append((message, kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self.error_calls.append((message, kwargs))


@pytest.mark.asyncio
async def test_provider_log_keeps_synth_stage_and_asset_type_in_safe_extra():
    logger = _FakeLogger()

    await log_provider_call(
        logger=logger,  # type: ignore[arg-type]
        provider="fake",
        model_name="fake-model",
        latency_ms=12,
        status="success",
        module_id="prompt_synthesizer",
        stage="synth",
        asset_type="character",
        input_chars=120,
        output_chars=240,
    )

    assert logger.error_calls == []
    message, payload = logger.info_calls[0]
    assert message == "provider call completed"
    assert payload["extra"]["module_id"] == "prompt_synthesizer"
    assert payload["extra"]["stage"] == "synth"
    assert payload["extra"]["asset_type"] == "character"
    assert payload["extra"]["input_chars"] == 120
    assert payload["extra"]["output_chars"] == 240
