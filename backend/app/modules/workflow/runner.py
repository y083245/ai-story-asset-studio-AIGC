"""FakeWorkflowRunner executes workflows locally with retry, signal, and cancel support.

- Runs activities with configurable retry policies.
- Supports wait_for_signal / send_signal for blocking points.
- Supports cancellation (raises WorkflowCancelledError).
- Records activity results for replay determinism (M15-18).
- Provides progress updates to the workflow state.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from app.modules.workflow.progress import build_progress_message
from app.modules.workflow.retry_policy import RetryPolicy, get_policy_for_activity
from app.modules.workflow.schemas import WorkflowContext


class WorkflowCancelledError(Exception):
    """Raised when a workflow is cancelled mid-execution."""

    def __init__(self, reason: str = "Workflow cancelled"):
        self.reason = reason
        super().__init__(reason)


class SignalTimeoutError(Exception):
    """Raised when wait_for_signal times out."""

    def __init__(self, signal_name: str, timeout: float):
        self.signal_name = signal_name
        self.timeout = timeout
        super().__init__(f"Timed out waiting for signal '{signal_name}' after {timeout}s")


class ActivityFailedError(Exception):
    """Raised when an activity exhausts all retry attempts."""

    def __init__(self, activity_name: str, attempts: int, last_error: str):
        self.activity_name = activity_name
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Activity '{activity_name}' failed after {attempts} attempts: {last_error}")


@dataclass
class ActivityRecord:
    """Record of an activity execution for replay determinism."""

    activity_name: str
    input_params: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0


def activity_input_hash(params: dict[str, Any] | None) -> str:
    """Return a stable hash for activity replay input validation."""
    raw = json.dumps(params or {}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FakeWorkflowRunner:
    """Runs workflows locally for development and Docker deployments.

    Manages:
    - Activity dispatch with retry logic
    - Signal handling (wait_for_signal / send_signal)
    - Cancellation
    - Activity recording for replay determinism (M15-18)
    - Progress callbacks
    """

    def __init__(self, activities: dict[str, Any] | None = None):
        """Initialise the runner with a map of activity_name -> async callable.

        Args:
            activities: Dict mapping activity names to async callables.
                        If None, use default fake activities.
        """
        if activities is None:
            from app.modules.workflow.fake_activities import create_default_fake_activities

            activities = create_default_fake_activities()
        self._activities: dict[str, Any] = activities
        self._cancelled: bool = False
        self._cancel_reason: str = ""
        self._signals: dict[str, asyncio.Event] = {}
        self._signal_data: dict[str, dict[str, Any]] = {}
        # For replay: record every activity execution
        self._activity_history: list[ActivityRecord] = []
        self._replay_mode: bool = False
        self._replay_history: dict[str, ActivityRecord] = {}
        # Progress callback
        self._on_progress: Any = None
        self._on_activity: Any = None
        # Retry counts per activity
        self._retry_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_progress_callback(self, callback: Any) -> None:
        """Register a callback invoked on every progress update.

        Signature: async callback(stage: str, progress: float, message: str) -> None
        """
        self._on_progress = callback

    def set_activity_callback(self, callback: Any) -> None:
        """Register a callback invoked when an activity starts or finishes.

        Signature: async callback(activity_name, status, attempt, result, error, input_hash) -> None
        """
        self._on_activity = callback

    def enable_replay(self, history: list[ActivityRecord]) -> None:
        """Enable replay mode using a previously recorded activity history."""
        self._replay_mode = True
        self._replay_history = {r.activity_name: r for r in history}

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    async def update_progress(self, stage: str, progress: float, message: str | None = None) -> None:
        """Update the current stage and progress percentage.

        Args:
            stage: Canonical stage name (e.g. "parsing_novel").
            progress: 0.0 to 1.0.
            message: Optional override for the progress message.
        """
        if message is None:
            message = build_progress_message(stage)
        if self._on_progress:
            await self._on_progress(stage, progress, message)

    # ------------------------------------------------------------------
    # Activity execution
    # ------------------------------------------------------------------

    async def run_activity(
        self,
        activity_name: str,
        context: WorkflowContext,
        params: dict[str, Any] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> dict[str, Any]:
        """Run a single activity with retry logic and cancellation checks.

        Args:
            activity_name: Name of the activity to run.
            context: Current workflow context (for cancellation checks).
            params: Dict of params to pass to the activity call.
            retry_policy: Optional explicit retry policy; auto-detected if omitted.

        Returns:
            Activity result dict.

        Raises:
            WorkflowCancelledError: If the workflow has been cancelled.
            ActivityFailedError: If all retry attempts are exhausted.
        """
        self._check_cancelled()

        if retry_policy is None:
            retry_policy = get_policy_for_activity(activity_name)

        if params is None:
            params = {}
        input_hash = activity_input_hash(params)

        # Replay mode: return recorded result
        if self._replay_mode and activity_name in self._replay_history:
            record = self._replay_history[activity_name]
            saved_hash = str(record.input_params.get("__input_hash") or activity_input_hash(record.input_params))
            if saved_hash == input_hash and record.result is not None:
                return record.result
            if saved_hash == input_hash:
                raise ActivityFailedError(activity_name, record.attempts, record.error or "replay error")

        activity_fn = self._activities.get(activity_name)
        if activity_fn is None:
            raise ActivityFailedError(activity_name, 0, f"Unknown activity: '{activity_name}'")

        record = ActivityRecord(
            activity_name=activity_name,
            input_params={**params, "__input_hash": input_hash},
            started_at=time.monotonic(),
        )

        last_error: str = ""
        for attempt in range(1, retry_policy.max_attempts + 1):
            self._check_cancelled()
            record.attempts = attempt
            if self._on_activity:
                await self._on_activity(activity_name, "running", attempt, None, None, input_hash)

            try:
                result: dict[str, Any] = await activity_fn(**params)
                record.result = result
                record.error = None  # Clear error from previous failed attempts
                record.finished_at = time.monotonic()
                self._activity_history.append(record)
                self._retry_counts[activity_name] = attempt
                if self._on_activity:
                    await self._on_activity(activity_name, "success", attempt, result, None, input_hash)
                return result
            except WorkflowCancelledError:
                raise
            except Exception as exc:
                last_error = str(exc)
                record.error = last_error

                if not retry_policy.is_retryable(getattr(exc, "code", "")):
                    raise ActivityFailedError(activity_name, attempt, last_error) from exc

                if attempt < retry_policy.max_attempts:
                    delay = min(
                        retry_policy.initial_interval * (retry_policy.backoff_coefficient ** (attempt - 1)),
                        retry_policy.max_interval,
                    )
                    await asyncio.sleep(delay)
                else:
                    record.finished_at = time.monotonic()
                    self._activity_history.append(record)
                    if self._on_activity:
                        await self._on_activity(activity_name, "failed", attempt, None, last_error, input_hash)
                    raise ActivityFailedError(activity_name, attempt, last_error) from exc

        raise ActivityFailedError(activity_name, retry_policy.max_attempts, last_error)

    # ------------------------------------------------------------------
    # Parallel activity support
    # ------------------------------------------------------------------

    async def run_activities_parallel(
        self,
        tasks: list[tuple[str, WorkflowContext, dict[str, Any] | None, RetryPolicy | None]],
    ) -> list[dict[str, Any] | BaseException]:
        """Run multiple activities in parallel, returning results or exceptions.

        Each item in *tasks* is (activity_name, context, params, retry_policy).

        Returns a list with the same length as *tasks*, where each element is
        either a result dict or an Exception (ActivityFailedError, etc.).
        """
        coros = [self.run_activity(activity_name, ctx, params, policy) for activity_name, ctx, params, policy in tasks]
        results: list[dict[str, Any] | BaseException] = await asyncio.gather(*coros, return_exceptions=True)
        return results

    # ------------------------------------------------------------------
    # Signal handling (M15-05)
    # ------------------------------------------------------------------

    async def wait_for_signal(self, signal_name: str, timeout: float = 3600) -> dict[str, Any]:
        """Block until a signal with the given name is received or timeout.

        Args:
            signal_name: Name of the signal to wait for (e.g. "style_confirmation").
            timeout: Maximum seconds to wait.

        Returns:
            Signal payload dict.

        Raises:
            SignalTimeoutError: If the timeout expires before the signal arrives.
            WorkflowCancelledError: If the workflow is cancelled while waiting.
        """
        if signal_name not in self._signals:
            self._signals[signal_name] = asyncio.Event()

        event = self._signals[signal_name]

        try:
            await asyncio.wait_for(self._wait_for_event(event, signal_name), timeout=timeout)
        except TimeoutError:
            raise SignalTimeoutError(signal_name, timeout) from None

        return self._signal_data.pop(signal_name, {})

    async def _wait_for_event(self, event: asyncio.Event, signal_name: str) -> None:
        """Wait for an event with cancellation checks."""
        while not event.is_set():
            self._check_cancelled()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(event.wait(), timeout=1.0)

    def send_signal(self, signal_name: str, data: dict[str, Any] | None = None) -> bool:
        """Send a signal to a waiting workflow.

        Args:
            signal_name: Name of the signal.
            data: Signal payload.

        Returns:
            True if there was a waiter for this signal, False otherwise.
        """
        if data is None:
            data = {}
        self._signal_data[signal_name] = data
        if signal_name in self._signals:
            self._signals[signal_name].set()
            return True
        # Create the event and set it so the next wait_for_signal picks it up
        self._signals[signal_name] = asyncio.Event()
        self._signals[signal_name].set()
        return True

    # ------------------------------------------------------------------
    # Cancellation (M15-13)
    # ------------------------------------------------------------------

    def cancel(self, reason: str = "user_cancelled") -> None:
        """Cancel the workflow.

        Running activities will be allowed to finish, but downstream tasks
        will be stopped. Callers should check _check_cancelled() at
        activity boundaries.
        """
        self._cancelled = True
        self._cancel_reason = reason

    def _check_cancelled(self) -> None:
        """Raise WorkflowCancelledError if the workflow has been cancelled."""
        if self._cancelled:
            raise WorkflowCancelledError(self._cancel_reason)

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------
    # Workflow execution
    # ------------------------------------------------------------------

    async def execute_workflow(self, workflow: Any, context: WorkflowContext) -> dict[str, Any]:
        """Execute a top-level workflow and return the final result.

        Args:
            workflow: A workflow instance with an async `execute(runner, context)` method.
            context: The initial WorkflowContext.

        Returns:
            The final context dict after workflow completion.
        """
        self._check_cancelled()
        result: dict[str, Any] = await workflow.execute(self, context)
        return result

    async def execute_sub_workflow(self, sub_workflow: Any, context: WorkflowContext) -> WorkflowContext:
        """Execute a sub-workflow within a parent workflow.

        The sub-workflow gets the same runner (so cancellation propagates).
        Returns an updated WorkflowContext reloaded from the result dict.

        Args:
            sub_workflow: A workflow instance.
            context: Current WorkflowContext.

        Returns:
            Reloaded WorkflowContext.
        """
        result = await sub_workflow.execute(self, context)
        # Rebuild context from the result dict so downstream stages see changes
        return WorkflowContext.model_validate(result)

    # ------------------------------------------------------------------
    # Activity history (for replay tests)
    # ------------------------------------------------------------------

    def get_history(self) -> list[ActivityRecord]:
        """Return the recorded activity execution history."""
        return list(self._activity_history)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all runner state for a fresh execution."""
        self._cancelled = False
        self._cancel_reason = ""
        self._signals.clear()
        self._signal_data.clear()
        self._activity_history.clear()
        self._retry_counts.clear()
