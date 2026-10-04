"""Executable registry for deterministic stage gates."""

from collections.abc import Iterable
from types import MappingProxyType

from app.orchestration.evidence_validation import GateContext
from app.orchestration.gates import (
    ArchitectureEntryGate,
    ArchitectureExitGate,
    GateEvaluation,
    ImplementationEntryGate,
    ReleaseReadinessEntryGate,
    RequirementExitGate,
    StageGate,
)


class StageGateRegistry:
    def __init__(self, bindings: Iterable[tuple[str, StageGate]]) -> None:
        gates: dict[str, StageGate] = {}
        for name, gate in bindings:
            if name in gates:
                raise ValueError(f"Duplicate executable gate binding: {name}")
            gates[name] = gate
        self._gates = MappingProxyType(gates)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._gates)

    def get(self, name: str) -> StageGate:
        try:
            return self._gates[name]
        except KeyError as error:
            raise KeyError(f"No executable stage gate registered for {name}") from error

    def evaluate(self, name: str, context: GateContext) -> GateEvaluation:
        return self.get(name).evaluate(context)


_architecture_entry = ArchitectureEntryGate()

DEFAULT_GATE_REGISTRY = StageGateRegistry(
    (
        ("requirements_analyzed", RequirementExitGate()),
        # TASK_DECOMPOSITION's exit and ARCHITECTURE_DESIGN's entry share this evidence boundary.
        ("tasks_defined", _architecture_entry),
        ("architecture_ready", ArchitectureExitGate()),
        ("architecture_approved", ImplementationEntryGate()),
        ("release_readiness_prerequisites", ReleaseReadinessEntryGate()),
    )
)
