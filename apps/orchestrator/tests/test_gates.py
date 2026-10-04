import uuid

import pytest

from app.artifacts.store import canonical_content
from app.orchestration.contracts import StageStatus
from app.orchestration.evidence_validation import (
    ApprovalEvidence,
    ApprovalStatus,
    ArtifactEvidence,
    GateContext,
    PolicyViolationEvidence,
    StageEvidence,
)
from app.orchestration.gate_registry import DEFAULT_GATE_REGISTRY, StageGateRegistry
from app.orchestration.gates import (
    ArchitectureEntryGate,
    ArchitectureExitGate,
    GateResult,
    ImplementationEntryGate,
    ReleaseReadinessEntryGate,
    RequirementExitGate,
)


def artifact(content: dict, artifact_type: str, **changes: object) -> ArtifactEvidence:
    _, digest = canonical_content(content)
    values = {
        "id": uuid.uuid4(),
        "version": 1,
        "sha256": digest,
        "artifact_type": artifact_type,
        "content": content,
        "current": True,
    }
    values.update(changes)
    return ArtifactEvidence(**values)


def requirement_content(*, blocking: bool = False) -> dict:
    return {
        "normalized_requirement": "Create a deterministic delivery workflow",
        "acceptance_criteria": ["Every stage is evidence gated"],
        "ambiguities": ["Reviewer identity is unknown"] if blocking else [],
        "clarifying_questions": ["Who reviews?"] if blocking else [],
        "assumptions": ["PostgreSQL is available"],
        "blocking_ambiguity": blocking,
        "risks": ["Stale evidence"],
    }


def task_plan_content() -> dict:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": "Implement the workflow",
                "affected_components": ["orchestrator"],
            }
        ],
        "dependencies": [],
        "parallelizable_groups": [["T1"]],
        "affected_components": ["orchestrator"],
        "risks": ["Concurrent updates"],
    }


def architecture_content() -> dict:
    return {
        "components": ["orchestrator"],
        "api_changes": ["No external API change"],
        "data_changes": ["No schema change"],
        "security_considerations": ["Validate immutable evidence"],
        "failure_modes": ["Stale approval"],
        "tradeoffs": ["Fail closed on malformed evidence"],
        "testing_implications": ["Test exact artifact approval"],
    }


def architecture_approval(
    architecture: ArtifactEvidence,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
    **changes: object,
) -> ApprovalEvidence:
    values = {
        "id": uuid.uuid4(),
        "approval_type": "ARCHITECTURE",
        "status": status,
        "artifact_id": architecture.id,
        "artifact_version": architecture.version,
        "artifact_hash": architecture.sha256,
    }
    values.update(changes)
    return ApprovalEvidence(**values)


def release_stages(
    *,
    override_name: str | None = None,
    override_status: StageStatus = StageStatus.SUCCEEDED,
    current: bool = True,
) -> tuple[StageEvidence, ...]:
    names = (
        "BUILD_VALIDATION",
        "UNIT_TEST",
        "INTEGRATION_TEST",
        "SECURITY_VALIDATION",
        "DOCUMENTATION_FINALIZATION",
    )
    return tuple(
        StageEvidence(
            stage_name=name,
            status=override_status if name == override_name else StageStatus.SUCCEEDED,
            generation=2,
            current=current if name == override_name else True,
        )
        for name in names
    )


def test_gate_result_has_exact_public_vocabulary() -> None:
    assert [result.value for result in GateResult] == ["PASS", "FAIL", "WAIT"]


def test_requirement_exit_requires_complete_structured_output() -> None:
    current = artifact(requirement_content(), "requirement_analysis")
    assert (
        RequirementExitGate().evaluate(GateContext(requirement=current)).result is GateResult.PASS
    )

    incomplete = dict(requirement_content())
    incomplete.pop("assumptions")
    verdict = RequirementExitGate().evaluate(
        GateContext(requirement=artifact(incomplete, "requirement_analysis"))
    )
    assert verdict.result is GateResult.FAIL
    assert "RequirementOutput" in verdict.reasons[0]


def test_requirement_exit_rejects_missing_acceptance_criteria_and_corrupt_hash() -> None:
    no_criteria = requirement_content()
    no_criteria["acceptance_criteria"] = []
    assert (
        RequirementExitGate()
        .evaluate(GateContext(requirement=artifact(no_criteria, "requirement_analysis")))
        .result
        is GateResult.FAIL
    )

    corrupted = artifact(requirement_content(), "requirement_analysis", sha256="0" * 64)
    verdict = RequirementExitGate().evaluate(GateContext(requirement=corrupted))
    assert verdict.result is GateResult.FAIL
    assert "hash" in verdict.reasons[0]


def test_architecture_entry_waits_for_inputs_or_blocking_clarification() -> None:
    gate = ArchitectureEntryGate()
    requirement = artifact(requirement_content(), "requirement_analysis")
    plan = artifact(task_plan_content(), "task_plan")

    assert gate.evaluate(GateContext()).result is GateResult.WAIT
    assert gate.evaluate(GateContext(requirement=requirement)).result is GateResult.WAIT
    assert (
        gate.evaluate(GateContext(requirement=requirement, task_plan=plan)).result
        is GateResult.PASS
    )

    ambiguous = artifact(requirement_content(blocking=True), "requirement_analysis")
    verdict = gate.evaluate(GateContext(requirement=ambiguous, task_plan=plan))
    assert verdict.result is GateResult.WAIT
    assert "ambiguity" in verdict.reasons[0]


def test_architecture_entry_rejects_malformed_or_empty_task_plan() -> None:
    requirement = artifact(requirement_content(), "requirement_analysis")
    empty_plan = task_plan_content()
    empty_plan["tasks"] = []
    empty_plan["parallelizable_groups"] = []
    verdict = ArchitectureEntryGate().evaluate(
        GateContext(requirement=requirement, task_plan=artifact(empty_plan, "task_plan"))
    )
    assert verdict.result is GateResult.FAIL
    assert "no tasks" in verdict.reasons[0]


@pytest.mark.parametrize(
    "missing_field",
    [
        "components",
        "api_changes",
        "data_changes",
        "security_considerations",
        "failure_modes",
        "testing_implications",
        "tradeoffs",
    ],
)
def test_architecture_exit_requires_each_design_section(missing_field: str) -> None:
    content = architecture_content()
    content[missing_field] = []
    verdict = ArchitectureExitGate().evaluate(
        GateContext(architecture=artifact(content, "architecture"))
    )
    assert verdict.result is GateResult.FAIL


def test_architecture_exit_passes_complete_current_artifact() -> None:
    design = artifact(architecture_content(), "architecture")
    verdict = ArchitectureExitGate().evaluate(GateContext(architecture=design))
    assert verdict.result is GateResult.PASS
    assert verdict.evidence_refs == (design.reference,)


def test_implementation_entry_requires_exact_approved_architecture_version() -> None:
    design = artifact(architecture_content(), "architecture", version=3)
    approval = architecture_approval(design)
    gate = ImplementationEntryGate()

    assert gate.evaluate(GateContext()).result is GateResult.WAIT
    assert (
        gate.evaluate(GateContext(architecture=design, approvals=(approval,))).result
        is GateResult.PASS
    )

    stale = architecture_approval(design, artifact_version=2)
    verdict = gate.evaluate(GateContext(architecture=design, approvals=(stale,)))
    assert verdict.result is GateResult.FAIL
    assert "version" in verdict.reasons[0]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ApprovalStatus.PENDING, GateResult.WAIT),
        (ApprovalStatus.REJECTED, GateResult.FAIL),
        (ApprovalStatus.INVALIDATED, GateResult.FAIL),
    ],
)
def test_implementation_entry_respects_current_approval_state(
    status: ApprovalStatus, expected: GateResult
) -> None:
    design = artifact(architecture_content(), "architecture")
    approval = architecture_approval(design, status)
    assert (
        ImplementationEntryGate()
        .evaluate(GateContext(architecture=design, approvals=(approval,)))
        .result
        is expected
    )


def test_implementation_entry_waits_for_current_artifact_and_rejects_wrong_hash() -> None:
    stale_design = artifact(architecture_content(), "architecture", current=False)
    assert (
        ImplementationEntryGate().evaluate(GateContext(architecture=stale_design)).result
        is GateResult.WAIT
    )

    design = artifact(architecture_content(), "architecture")
    wrong_hash = architecture_approval(design, artifact_hash="f" * 64)
    verdict = ImplementationEntryGate().evaluate(
        GateContext(architecture=design, approvals=(wrong_hash,))
    )
    assert verdict.result is GateResult.FAIL


def test_release_readiness_requires_all_successful_current_evidence() -> None:
    gate = ReleaseReadinessEntryGate()
    passed = gate.evaluate(GateContext(stages=release_stages()))
    assert passed.result is GateResult.PASS
    assert len(passed.evidence_refs) == 5

    missing = gate.evaluate(GateContext(stages=release_stages()[:-1]))
    assert missing.result is GateResult.WAIT
    assert "DOCUMENTATION_FINALIZATION" in missing.reasons[0]

    running = gate.evaluate(
        GateContext(
            stages=release_stages(override_name="UNIT_TEST", override_status=StageStatus.RUNNING)
        )
    )
    assert running.result is GateResult.WAIT


@pytest.mark.parametrize(
    "status",
    [
        StageStatus.FAILED,
        StageStatus.ROLLED_BACK,
        StageStatus.STALE,
        StageStatus.SKIPPED,
        StageStatus.SAFE_STOPPED,
        StageStatus.CANCELLED,
    ],
)
def test_release_readiness_fails_for_unsuccessful_terminal_evidence(status: StageStatus) -> None:
    verdict = ReleaseReadinessEntryGate().evaluate(
        GateContext(
            stages=release_stages(override_name="SECURITY_VALIDATION", override_status=status)
        )
    )
    assert verdict.result is GateResult.FAIL


def test_release_readiness_rejects_stale_or_blocked_policy_evidence() -> None:
    stale = ReleaseReadinessEntryGate().evaluate(
        GateContext(stages=release_stages(override_name="BUILD_VALIDATION", current=False))
    )
    assert stale.result is GateResult.FAIL

    blocker = PolicyViolationEvidence(rule_id="SEC-12", blocking=True)
    blocked = ReleaseReadinessEntryGate().evaluate(
        GateContext(stages=release_stages(), policy_violations=(blocker,))
    )
    assert blocked.result is GateResult.FAIL
    assert blocker.reference in blocked.evidence_refs

    advisory = PolicyViolationEvidence(rule_id="DOC-2", blocking=False)
    assert (
        ReleaseReadinessEntryGate()
        .evaluate(GateContext(stages=release_stages(), policy_violations=(advisory,)))
        .result
        is GateResult.PASS
    )


def test_executable_gate_registry_binds_phase_12_boundaries() -> None:
    assert DEFAULT_GATE_REGISTRY.names == {
        "requirements_analyzed",
        "tasks_defined",
        "architecture_ready",
        "architecture_approved",
        "release_readiness_prerequisites",
    }
    assert isinstance(DEFAULT_GATE_REGISTRY.get("tasks_defined"), ArchitectureEntryGate)
    with pytest.raises(KeyError, match="No executable stage gate"):
        DEFAULT_GATE_REGISTRY.get("not_registered")


def test_executable_gate_registry_rejects_duplicate_bindings() -> None:
    with pytest.raises(ValueError, match="Duplicate executable gate"):
        StageGateRegistry((("same", RequirementExitGate()), ("same", ArchitectureExitGate())))
