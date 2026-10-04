"""Internal guard preventing status mutation outside WorkflowOrchestrator."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_transition_authorized: ContextVar[bool] = ContextVar(
    "workflow_transition_authorized", default=False
)


def transition_is_authorized() -> bool:
    return _transition_authorized.get()


@contextmanager
def orchestrator_transition() -> Iterator[None]:
    token = _transition_authorized.set(True)
    try:
        yield
    finally:
        _transition_authorized.reset(token)
