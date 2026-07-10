"""Threshold enforcement (M13-08).

Defines quality thresholds for image inspection and evaluates
scores against them. "Must-pass" issues are blocking regardless of
numerical score.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Threshold values for numerical scores
THRESHOLDS: dict[str, float] = {
    "face_consistency": 0.78,
    "outfit_consistency": 0.75,
    "scene_consistency": 0.70,
}

# Issue codes that are "must-pass" — block regardless of score
MUST_PASS_ISSUES: set[str] = {
    "EXTRA_CHARACTER",
    "WATERMARK",
    "PROP_MISSING",
    "AI_GLITCH",
    "IMAGE_UNUSABLE",
}


def is_must_pass_issue(issue_code: str) -> bool:
    """Check if an issue code is a must-pass (blocking) issue.

    Args:
        issue_code: The issue code to check (e.g., "EXTRA_CHARACTER").

    Returns:
        True if the issue is a must-pass (always causes retry).
    """
    return issue_code in MUST_PASS_ISSUES


def evaluate_thresholds(
    scores: Mapping[str, float | None],
    issues: Sequence[Mapping[str, Any]],
) -> tuple[bool, list[str]]:
    """Evaluate scores against thresholds.

    Args:
        scores: Dict with keys face_consistency, outfit_consistency,
                scene_consistency, prop_presence.
        issues: List of issue dicts, each with at least a "code" key.

    Returns:
        Tuple of (passed: bool, failed_checks: list[str]).
        passed is True only if ALL checks pass.
        failed_checks contains names of failed threshold checks.
    """
    failed: list[str] = []

    # Check numerical thresholds
    for key, threshold in THRESHOLDS.items():
        score = scores.get(key)
        if score is None:
            continue
        if score < threshold:
            failed.append(f"{key}_below_threshold")

    # Check must-pass issues
    for issue in issues:
        code = issue.get("code", "")
        if is_must_pass_issue(code):
            failed.append(f"must_pass_{code}")

    # Any critical issue that is not must-pass still counts as a failure
    for issue in issues:
        code = issue.get("code", "")
        severity = issue.get("severity", "warning")
        if severity == "critical" and not is_must_pass_issue(code):
            failed.append(f"issue_{code}")

    return (len(failed) == 0, failed)


def check_threshold(score: float | None, threshold: float) -> bool:
    """Check a single score against its threshold.

    Args:
        score: The score value, or None if not assessed.
        threshold: The minimum acceptable value.

    Returns:
        True if the score meets or exceeds the threshold.
    """
    if score is None:
        return True  # Not assessed — pass by default
    return score >= threshold
