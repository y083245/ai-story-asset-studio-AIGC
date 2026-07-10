from __future__ import annotations

import json

from app.modules.observability.prompt_audit import PromptAuditRecord, write_prompt_audit_record


def test_prompt_audit_writes_sanitized_jsonl(tmp_path) -> None:
    path = write_prompt_audit_record(
        PromptAuditRecord(
            project_id="project-1",
            entity_type="image_asset",
            entity_id="asset-1",
            asset_type="character_front",
            stage="final_generation",
            source_prompt="source prompt",
            final_prompt="final prompt",
            negative_prompt="negative prompt",
            provider="openai",
            model="gpt-image-1",
            metadata={"api_key": "sk-secret", "reference_asset_ids": ["ref-1"]},
        ),
        storage_root=tmp_path,
    )

    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert path.parent == tmp_path / "audit" / "project-1"
    assert record["stage"] == "final_generation"
    assert record["metadata"]["api_key"] == "***REDACTED***"
    assert "sk-secret" not in path.read_text(encoding="utf-8")
