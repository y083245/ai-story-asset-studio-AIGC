"""Stable ID factory for Story Asset Studio domain entities.

Every domain entity within a project receives a stable, human-readable ID
that follows a fixed format: PREFIX_NNN (e.g. CH_001, SC_001).

The factory maintains per-project, per-type counters so that IDs increment
independently for each entity type within a single project.

ID Format Rules:
- Character:  CH_001, CH_002, ...
- Scene:      SC_001, SC_002, ...
- Prop:       PR_001, PR_002, ...

All IDs are zero-padded to three digits.
"""

from __future__ import annotations

from collections import defaultdict

# Per-project counters: _counters[project_id][prefix] -> next sequence number
_counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(lambda: 1))


def _next_id(project_id: str, prefix: str) -> str:
    """Return the next available ID for the given project and prefix."""
    seq = _counters[project_id][prefix]
    _counters[project_id][prefix] = seq + 1
    return f"{prefix}_{seq:03d}"


def generate_character_id(project_id: str) -> str:
    """Generate a stable character ID, e.g. CH_001."""
    return _next_id(project_id, "CH")


def generate_scene_id(project_id: str) -> str:
    """Generate a stable scene ID, e.g. SC_001."""
    return _next_id(project_id, "SC")


def generate_prop_id(project_id: str) -> str:
    """Generate a stable prop ID, e.g. PR_001."""
    return _next_id(project_id, "PR")


def reset_counters(project_id: str | None = None) -> None:
    """Reset ID counters for a specific project or all projects.

    Args:
        project_id: If provided, reset only that project's counters.
                    If None, reset all counters.
    """
    if project_id is None:
        _counters.clear()
    else:
        _counters.pop(project_id, None)
