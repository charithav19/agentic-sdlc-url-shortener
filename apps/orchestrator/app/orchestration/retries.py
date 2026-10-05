"""Bounded deterministic retry scheduling."""

from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class RetrySchedule:
    next_attempt: int
    due_at: datetime
    delay_seconds: float


class RetryPlanner:
    def __init__(
        self,
        *,
        base_delay_seconds: float = 1.0,
        maximum_delay_seconds: float = 30.0,
        jitter_ratio: float = 0.2,
    ) -> None:
        if base_delay_seconds < 0 or maximum_delay_seconds < base_delay_seconds:
            raise ValueError("Retry delay bounds are invalid")
        if not 0 <= jitter_ratio <= 1:
            raise ValueError("Retry jitter ratio must be between zero and one")
        self.base_delay_seconds = base_delay_seconds
        self.maximum_delay_seconds = maximum_delay_seconds
        self.jitter_ratio = jitter_ratio

    def schedule(
        self,
        *,
        completed_attempt: int,
        now: datetime,
        jitter_fraction: float = 0.0,
    ) -> RetrySchedule:
        if completed_attempt < 1:
            raise ValueError("Completed attempt must be positive")
        if not 0 <= jitter_fraction <= 1:
            raise ValueError("Jitter fraction must be between zero and one")
        exponential = self.base_delay_seconds * (2 ** (completed_attempt - 1))
        bounded = min(exponential, self.maximum_delay_seconds)
        delay = min(
            bounded * (1 + self.jitter_ratio * jitter_fraction),
            self.maximum_delay_seconds,
        )
        return RetrySchedule(
            next_attempt=completed_attempt + 1,
            due_at=now + timedelta(seconds=delay),
            delay_seconds=delay,
        )
