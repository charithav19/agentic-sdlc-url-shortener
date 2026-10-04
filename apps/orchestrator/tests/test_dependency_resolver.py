"""Deterministic sequential, fan-out and fan-in readiness cases."""

import pytest

from app.orchestration.contracts import StageStatus
from app.orchestration.dependencies import StageDependencyResolver
from app.orchestration.graph import RetryPolicy, StageDefinition, build_graph
from app.orchestration.readiness import StageSnapshot


def resolver(edges: dict[str, tuple[str, ...]]) -> StageDependencyResolver:
    stages = tuple(
        StageDefinition(
            name=name,
            dependencies=dependencies,
            executor="intake",
            entry_gate="always",
            exit_gate="intake_complete",
            retry_policy=RetryPolicy(max_attempts=1, retryable_errors=()),
            fallback=None,
            approval_required=False,
        )
        for name, dependencies in edges.items()
    )
    return StageDependencyResolver(build_graph("test-1", stages))


def test_a_success_makes_b_ready() -> None:
    # TEST 1: A -> B
    dependency_resolver = resolver({"A": (), "B": ("A",)})

    result = dependency_resolver.resolve({"A": StageStatus.SUCCEEDED, "B": StageStatus.BLOCKED})

    assert result["B"].status == StageStatus.READY
    assert result["B"].unmet_dependencies == ()


def test_a_success_fans_out_to_b_and_c() -> None:
    # TEST 2: A -> B and A -> C
    dependency_resolver = resolver({"A": (), "B": ("A",), "C": ("A",)})

    result = dependency_resolver.resolve({"A": StageStatus.SUCCEEDED})

    assert result["B"].status == StageStatus.READY
    assert result["C"].status == StageStatus.READY


def test_join_waits_for_both_b_and_c() -> None:
    # TEST 3: B,C -> D. A running predecessor cannot release the join.
    dependency_resolver = resolver({"B": (), "C": (), "D": ("B", "C")})

    waiting = dependency_resolver.resolve({"B": StageStatus.SUCCEEDED, "C": StageStatus.RUNNING})
    assert waiting["D"].status == StageStatus.BLOCKED
    assert waiting["D"].unmet_dependencies == ("C",)

    released = dependency_resolver.resolve({"B": StageStatus.SUCCEEDED, "C": StageStatus.SUCCEEDED})
    assert released["D"].status == StageStatus.READY
    assert released["D"].unmet_dependencies == ()


@pytest.mark.parametrize(
    "parent_status",
    [
        StageStatus.FAILED,
        StageStatus.STALE,
        StageStatus.ROLLED_BACK,
        StageStatus.SKIPPED,
        StageStatus.CANCELLED,
    ],
)
def test_only_succeeded_predecessor_satisfies_dependency(
    parent_status: StageStatus,
) -> None:
    dependency_resolver = resolver({"A": (), "B": ("A",)})

    result = dependency_resolver.resolve({"A": parent_status})

    assert result["B"].status == StageStatus.BLOCKED
    assert result["B"].unmet_dependencies == ("A",)


def test_prior_generation_success_does_not_release_current_generation() -> None:
    dependency_resolver = resolver({"A": (), "B": ("A",)})

    result = dependency_resolver.resolve(
        {"A": StageSnapshot(StageStatus.SUCCEEDED, generation=1)},
        generation=2,
    )

    assert result["A"].status == StageStatus.READY
    assert result["B"].status == StageStatus.BLOCKED
    assert result["B"].unmet_dependencies == ("A",)


def test_missing_parent_blocks_child() -> None:
    dependency_resolver = resolver({"A": (), "B": ("A",)})

    result = dependency_resolver.resolve({})

    assert result["A"].status == StageStatus.READY
    assert result["B"].status == StageStatus.BLOCKED


def test_resolution_is_deterministic_and_does_not_mutate_input() -> None:
    dependency_resolver = resolver({"D": ("B", "C"), "C": ("A",), "B": ("A",), "A": ()})
    states = {"C": StageStatus.RUNNING, "A": StageStatus.SUCCEEDED, "B": StageStatus.READY}
    original = dict(states)

    first = dependency_resolver.resolve(states)
    second = dependency_resolver.resolve(dict(reversed(list(states.items()))))

    assert list(first) == list(second) == list(dependency_resolver.graph.topological_order)
    assert first == second
    assert states == original
    assert first["C"].status == StageStatus.RUNNING
    assert first["D"].status == StageStatus.BLOCKED


def test_unknown_stage_or_invalid_generation_is_rejected() -> None:
    dependency_resolver = resolver({"A": ()})

    with pytest.raises(ValueError, match="Unknown stage states"):
        dependency_resolver.resolve({"UNKNOWN": StageStatus.SUCCEEDED})
    with pytest.raises(ValueError, match="Generation must be positive"):
        dependency_resolver.resolve({}, generation=0)
