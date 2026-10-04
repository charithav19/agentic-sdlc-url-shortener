"""Deterministic entry and exit gates for evidence-backed workflow stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from app.agents.output_schemas import ArchitectureOutput, PlanningOutput, RequirementOutput
from app.orchestration.contracts import StageStatus
from app.orchestration.evidence_validation import (
    ApprovalStatus,
    GateContext,
    InvalidEvidence,
    has_nonblank_values,
    validate_artifact,
)


class GateResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WAIT = "WAIT"


@dataclass(frozen=True)
class GateEvaluation:
    result: GateResult
    reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.result is GateResult.PASS and self.reasons:
            raise ValueError("PASS evaluation cannot contain blocking reasons")
        if self.result is not GateResult.PASS and not self.reasons:
            raise ValueError("FAIL and WAIT evaluations require a reason")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("Evidence references must be unique")


class StageGate(ABC):
    """Read-only boundary check. A gate cannot mutate workflow or stage state."""

    gate_id: str
    version = "1"

    @abstractmethod
    def evaluate(self, context: GateContext) -> GateEvaluation:
        """Return a deterministic verdict for the supplied evidence snapshot."""


def _pass(*evidence_refs: str) -> GateEvaluation:
    return GateEvaluation(GateResult.PASS, evidence_refs=tuple(dict.fromkeys(evidence_refs)))


def _fail(reason: str, *evidence_refs: str) -> GateEvaluation:
    return GateEvaluation(
        GateResult.FAIL,
        reasons=(reason,),
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
    )


def _wait(reason: str, *evidence_refs: str) -> GateEvaluation:
    return GateEvaluation(
        GateResult.WAIT,
        reasons=(reason,),
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
    )


class RequirementExitGate(StageGate):
    gate_id = "requirements_analyzed"

    def evaluate(self, context: GateContext) -> GateEvaluation:
        artifact = context.requirement
        if artifact is None:
            return _fail("Requirement analysis did not produce an artifact")
        try:
            output = validate_artifact(artifact, RequirementOutput, label="Requirement")
        except InvalidEvidence as error:
            return _fail(str(error), artifact.reference)
        if not output.normalized_requirement.strip():
            return _fail("Normalized requirement is blank", artifact.reference)
        if not has_nonblank_values(output.acceptance_criteria):
            return _fail("Acceptance criteria are missing or blank", artifact.reference)
        # Pydantic validation proves that ambiguity status and assumptions are explicit fields.
        return _pass(artifact.reference)


class ArchitectureEntryGate(StageGate):
    gate_id = "architecture_entry"

    def evaluate(self, context: GateContext) -> GateEvaluation:
        requirement = context.requirement
        task_plan = context.task_plan
        if requirement is None:
            return _wait("Current normalized requirement is not available")
        if task_plan is None:
            return _wait("Current task plan is not available", requirement.reference)
        references = (requirement.reference, task_plan.reference)
        try:
            requirement_output = validate_artifact(
                requirement, RequirementOutput, label="Requirement"
            )
            planning_output = validate_artifact(task_plan, PlanningOutput, label="Task plan")
        except InvalidEvidence as error:
            return _fail(str(error), *references)
        if not requirement_output.normalized_requirement.strip():
            return _fail("Normalized requirement is blank", *references)
        if requirement_output.blocking_ambiguity:
            return _wait("Blocking requirement ambiguity must be clarified", *references)
        if not planning_output.tasks:
            return _fail("Task plan contains no tasks", *references)
        return _pass(*references)


class ArchitectureExitGate(StageGate):
    gate_id = "architecture_ready"

    _required_sections = {
        "components": "components",
        "api_changes": "API impact",
        "data_changes": "data impact",
        "security_considerations": "security considerations",
        "failure_modes": "failure modes",
        "testing_implications": "testing implications",
        "tradeoffs": "tradeoffs",
    }

    def evaluate(self, context: GateContext) -> GateEvaluation:
        artifact = context.architecture
        if artifact is None:
            return _fail("Architecture stage did not produce an artifact")
        try:
            output = validate_artifact(artifact, ArchitectureOutput, label="Architecture")
        except InvalidEvidence as error:
            return _fail(str(error), artifact.reference)
        for field_name, label in self._required_sections.items():
            if not has_nonblank_values(getattr(output, field_name)):
                return _fail(f"Architecture {label} is missing or blank", artifact.reference)
        return _pass(artifact.reference)


class ImplementationEntryGate(StageGate):
    gate_id = "architecture_approved"

    def evaluate(self, context: GateContext) -> GateEvaluation:
        architecture = context.architecture
        if architecture is None:
            return _wait("Current architecture artifact is not available")
        try:
            validate_artifact(architecture, ArchitectureOutput, label="Architecture")
        except InvalidEvidence as error:
            if not architecture.current:
                return _wait(str(error), architecture.reference)
            return _fail(str(error), architecture.reference)

        approvals = tuple(
            approval for approval in context.approvals if approval.approval_type == "ARCHITECTURE"
        )
        exact = tuple(approval for approval in approvals if approval.matches(architecture))
        if exact:
            statuses = {approval.status for approval in exact}
            references = (architecture.reference, *(approval.reference for approval in exact))
            if len(statuses) > 1:
                return _fail("Conflicting decisions exist for the architecture", *references)
            status = next(iter(statuses))
            if status is ApprovalStatus.APPROVED:
                return _pass(*references)
            if status is ApprovalStatus.PENDING:
                return _wait("Architecture approval is pending", *references)
            return _fail(f"Architecture approval is {status.value.lower()}", *references)

        stale_approvals = tuple(
            approval for approval in approvals if approval.status is ApprovalStatus.APPROVED
        )
        if stale_approvals:
            return _fail(
                "Approved architecture version does not match the current artifact",
                architecture.reference,
                *(approval.reference for approval in stale_approvals),
            )
        return _wait(
            "Approval for the current architecture version is not available",
            architecture.reference,
        )


class ReleaseReadinessEntryGate(StageGate):
    gate_id = "release_readiness_prerequisites"

    _required_stages = (
        "BUILD_VALIDATION",
        "UNIT_TEST",
        "INTEGRATION_TEST",
        "SECURITY_VALIDATION",
        "DOCUMENTATION_FINALIZATION",
    )
    _waiting_statuses = {
        StageStatus.PENDING,
        StageStatus.BLOCKED,
        StageStatus.READY,
        StageStatus.RUNNING,
        StageStatus.WAITING_APPROVAL,
        StageStatus.RETRY_PENDING,
        StageStatus.FALLBACK_RUNNING,
    }

    def evaluate(self, context: GateContext) -> GateEvaluation:
        stages_by_name = {stage.stage_name: stage for stage in context.stages}
        duplicate_names = len(stages_by_name) != len(context.stages)
        if duplicate_names:
            return _fail("Release evidence contains duplicate stage records")

        references: list[str] = []
        for stage_name in self._required_stages:
            stage = stages_by_name.get(stage_name)
            if stage is None:
                return _wait(f"{stage_name} evidence is not available", *references)
            references.append(stage.reference)
            if not stage.current:
                return _fail(f"{stage_name} evidence is stale", *references)
            if stage.status is StageStatus.SUCCEEDED:
                continue
            if stage.status in self._waiting_statuses:
                return _wait(f"{stage_name} has not succeeded", *references)
            return _fail(f"{stage_name} ended with {stage.status.value}", *references)

        active_blockers = tuple(
            violation
            for violation in context.policy_violations
            if violation.active and violation.blocking
        )
        if active_blockers:
            return _fail(
                "Blocking policy violations remain unresolved",
                *references,
                *(violation.reference for violation in active_blockers),
            )
        references.extend(
            violation.reference for violation in context.policy_violations if violation.active
        )
        return _pass(*references)
