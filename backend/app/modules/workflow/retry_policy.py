"""Retry policies for workflow activities.

Defines per-activity-type retry behaviour: max attempts, backoff, and
which error types are retryable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for a single activity or activity class.

    Attributes:
        max_attempts: Total number of attempts (1 initial + N retries).
        initial_interval: Seconds before first retry.
        backoff_coefficient: Multiplier for each subsequent retry interval.
        max_interval: Ceiling on the computed retry interval.
        non_retryable_errors: Error code prefixes that should NOT be retried.
    """

    max_attempts: int = 1
    initial_interval: float = 1.0
    backoff_coefficient: float = 2.0
    max_interval: float = 60.0
    non_retryable_errors: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"VALIDATION_ERROR", "FORBIDDEN", "NOT_FOUND", "WORKFLOW_CANCELLED"}
        )
    )

    def is_retryable(self, error_code: str) -> bool:
        """Return True if this error code allows a retry."""
        return error_code not in self.non_retryable_errors


# ---------------------------------------------------------------------------
# Canonical retry policies — matched to the requirements spec
# ---------------------------------------------------------------------------

# Text generation: re-generate prompt, 2 total attempts
TEXT_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    initial_interval=2.0,
    backoff_coefficient=2.0,
    max_interval=30.0,
)

# Image generation: re-generate prompt, 3 total attempts
IMAGE_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    initial_interval=3.0,
    backoff_coefficient=2.0,
    max_interval=60.0,
)

# Quality auto-fix: re-check after fix, 2 total attempts
QUALITY_AUTO_FIX_POLICY = RetryPolicy(
    max_attempts=2,
    initial_interval=1.0,
    backoff_coefficient=1.5,
    max_interval=10.0,
)

# Default policy: no retries
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=1,
    initial_interval=1.0,
    backoff_coefficient=2.0,
    max_interval=30.0,
)

# Lookup by activity category
RETRY_POLICIES: dict[str, RetryPolicy] = {
    "text": TEXT_RETRY_POLICY,
    "image": IMAGE_RETRY_POLICY,
    "quality_auto_fix": QUALITY_AUTO_FIX_POLICY,
    "default": DEFAULT_RETRY_POLICY,
}


def get_policy_for_activity(activity_name: str) -> RetryPolicy:
    """Map an activity name to its retry policy.

    Rules:
    - Text analysis activities → TEXT_RETRY_POLICY
    - Image generation activities → IMAGE_RETRY_POLICY
    - Quality check / fix activities → QUALITY_AUTO_FIX_POLICY
    - Everything else → DEFAULT_RETRY_POLICY (no retries)
    """
    image_keywords = (
        "generate_character",
        "generate_scene",
        "generate_prop",
        "image_",
    )
    text_keywords = (
        "build_",
        "extract_",
        "detect_",
        "parse_",
        "character_card",
        "scene_card",
        "prop_card",
    )
    quality_keywords = ("quality_", "auto_fix", "check_image", "retry_failed")

    for kw in quality_keywords:
        if kw in activity_name:
            return QUALITY_AUTO_FIX_POLICY
    for kw in image_keywords:
        if kw in activity_name:
            return IMAGE_RETRY_POLICY
    for kw in text_keywords:
        if kw in activity_name:
            return TEXT_RETRY_POLICY

    return DEFAULT_RETRY_POLICY
