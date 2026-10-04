"""Declared graph identifiers; executable bindings arrive in later phases."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphRegistry:
    executors: frozenset[str]
    gates: frozenset[str]
    retryable_errors: frozenset[str]


DEFAULT_REGISTRY = GraphRegistry(
    executors=frozenset(
        {
            "intake",
            "requirements_specialist",
            "task_decomposition_specialist",
            "architecture_specialist",
            "human_checkpoint",
            "implementation_specialist",
            "test_design_specialist",
            "documentation_specialist",
            "build_runner",
            "unit_test_runner",
            "integration_test_runner",
            "security_specialist",
            "release_specialist",
            "system_marker",
            "clarification",
        }
    ),
    gates=frozenset(
        {
            "always",
            "intake_complete",
            "requirements_analyzed",
            "requirements_unambiguous",
            "tasks_defined",
            "architecture_ready",
            "architecture_approved",
            "implementation_complete",
            "test_design_complete",
            "documentation_draft_complete",
            "candidate_and_test_plan_current",
            "build_passed",
            "unit_tests_passed",
            "integration_tests_passed",
            "security_validation_passed",
            "documentation_finalized",
            "release_ready",
            "release_approved",
            "workflow_complete",
            "blocking_ambiguity_detected",
            "clarification_answered",
        }
    ),
    retryable_errors=frozenset({"TRANSIENT_TOOL_ERROR", "RATE_LIMIT", "TIMEOUT"}),
)
