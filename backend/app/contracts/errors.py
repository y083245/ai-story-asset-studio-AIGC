"""Unified error-code structure shared across Story Asset Studio modules.

Every module MUST use these error codes (or extend them) rather than
returning ad-hoc string error messages. Each error code carries:
- code:        stable machine-readable identifier
- message:     human-readable description
- retryable:   whether the operation can be retried
- module:      the originating module (for observability)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ErrorCode:
    """A stable, machine-readable error code."""

    code: str
    message: str
    retryable: bool
    module: str

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Standard error codes
# ---------------------------------------------------------------------------

VALIDATION_ERROR = ErrorCode(
    code="VALIDATION_ERROR",
    message="Input validation failed. Check the request payload against the schema.",
    retryable=False,
    module="contracts",
)

PROVIDER_TIMEOUT = ErrorCode(
    code="PROVIDER_TIMEOUT",
    message="External AI provider did not respond within the timeout window.",
    retryable=True,
    module="contracts",
)

PROVIDER_RATE_LIMITED = ErrorCode(
    code="PROVIDER_RATE_LIMITED",
    message="External AI provider rate limit exceeded. Back off and retry.",
    retryable=True,
    module="contracts",
)

STORAGE_ERROR = ErrorCode(
    code="STORAGE_ERROR",
    message="Object storage operation failed (upload, download, or delete).",
    retryable=True,
    module="contracts",
)

WORKFLOW_CANCELLED = ErrorCode(
    code="WORKFLOW_CANCELLED",
    message="The workflow was cancelled by the user or system.",
    retryable=False,
    module="contracts",
)

ANALYSIS_NOT_READY = ErrorCode(
    code="ANALYSIS_NOT_READY",
    message="Story analysis has not completed yet.",
    retryable=True,
    module="workflow",
)

ANALYSIS_FAILED = ErrorCode(
    code="ANALYSIS_FAILED",
    message="Story analysis failed.",
    retryable=True,
    module="workflow",
)

NEEDS_REVIEW = ErrorCode(
    code="NEEDS_REVIEW",
    message="The generated output requires manual review before proceeding.",
    retryable=False,
    module="contracts",
)

NOT_FOUND = ErrorCode(
    code="NOT_FOUND",
    message="The requested resource was not found.",
    retryable=False,
    module="project",
)

FORBIDDEN = ErrorCode(
    code="FORBIDDEN",
    message="You do not have permission to access this resource.",
    retryable=False,
    module="project",
)

PROJECT_LOCKED = ErrorCode(
    code="PROJECT_LOCKED",
    message="The project is in a locked state and cannot be modified.",
    retryable=False,
    module="project",
)

UNSUPPORTED_FORMAT = ErrorCode(
    code="UNSUPPORTED_FORMAT",
    message="The file format is not supported for this operation.",
    retryable=False,
    module="novel_intake",
)

WORD_COUNT_OUT_OF_RANGE = ErrorCode(
    code="WORD_COUNT_OUT_OF_RANGE",
    message="The word count is outside the allowed range (1000-10000).",
    retryable=False,
    module="novel_intake",
)

# Convenience mapping for lookup
ALL_ERROR_CODES: dict[str, ErrorCode] = {
    e.code: e
    for e in (
        VALIDATION_ERROR,
        PROVIDER_TIMEOUT,
        PROVIDER_RATE_LIMITED,
        STORAGE_ERROR,
        WORKFLOW_CANCELLED,
        ANALYSIS_NOT_READY,
        ANALYSIS_FAILED,
        NEEDS_REVIEW,
        NOT_FOUND,
        FORBIDDEN,
        PROJECT_LOCKED,
        UNSUPPORTED_FORMAT,
        WORD_COUNT_OUT_OF_RANGE,
    )
}
