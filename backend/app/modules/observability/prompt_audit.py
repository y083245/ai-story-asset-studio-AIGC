"""Prompt audit JSONL writer.

The audit file is intended for local inspection of prompt decisions. It must
never include credentials or raw provider secrets.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.observability.sanitize import sanitize_log_context


@dataclass
class PromptAuditRecord:
    project_id: str
    entity_type: str
    entity_id: str
    asset_type: str
    stage: str
    source_prompt: str = ""
    final_prompt: str = ""
    negative_prompt: str = ""
    provider: str = ""
    model: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


def write_prompt_audit_record(
    record: PromptAuditRecord,
    *,
    storage_root: str | Path = "local_storage",
) -> Path:
    """Append one sanitized prompt audit record and return the JSONL path."""
    payload = sanitize_log_context(asdict(record))
    project_id = _safe_path_segment(str(payload.get("project_id") or "unknown"))
    audit_dir = Path(storage_root) / "audit" / project_id
    audit_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(UTC).strftime("%Y%m%d")
    audit_path = audit_dir / f"prompts_{day}.jsonl"
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    return audit_path


def _safe_path_segment(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned[:120] or "unknown"
