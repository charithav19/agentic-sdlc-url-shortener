"""Stable failure taxonomy used by retry and safe-stop policy."""

from dataclasses import dataclass
from enum import StrEnum

from app.agents.errors import AgentTimeout, AgentToolDenied, AgentTransientError


class FailureCode(StrEnum):
    OPENAI_TIMEOUT = "OPENAI_TIMEOUT"
    TEMPORARY_EXTERNAL_PROVIDER_ERROR = "TEMPORARY_EXTERNAL_PROVIDER_ERROR"
    TEMPORARY_WORKSPACE_TOOL_FAILURE = "TEMPORARY_WORKSPACE_TOOL_FAILURE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    FAILED_TEST_ASSERTION = "FAILED_TEST_ASSERTION"
    INVALID_REQUIREMENT = "INVALID_REQUIREMENT"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    FORBIDDEN_TOOL_REQUEST = "FORBIDDEN_TOOL_REQUEST"
    INVALID_WORKFLOW_STATE = "INVALID_WORKFLOW_STATE"
    CORRUPTED_LINEAGE = "CORRUPTED_LINEAGE"
    UNCLASSIFIED_EXECUTION_ERROR = "UNCLASSIFIED_EXECUTION_ERROR"


class ClassifiedStageFailure(RuntimeError):
    code: FailureCode


class TemporaryWorkspaceToolFailure(ClassifiedStageFailure):
    code = FailureCode.TEMPORARY_WORKSPACE_TOOL_FAILURE


class PolicyViolationFailure(ClassifiedStageFailure):
    code = FailureCode.POLICY_VIOLATION


class FailedTestAssertion(ClassifiedStageFailure):
    code = FailureCode.FAILED_TEST_ASSERTION


class InvalidRequirementFailure(ClassifiedStageFailure):
    code = FailureCode.INVALID_REQUIREMENT


class SecurityViolationFailure(ClassifiedStageFailure):
    code = FailureCode.SECURITY_VIOLATION


class ForbiddenToolRequestFailure(ClassifiedStageFailure):
    code = FailureCode.FORBIDDEN_TOOL_REQUEST


class InvalidWorkflowStateFailure(ClassifiedStageFailure):
    code = FailureCode.INVALID_WORKFLOW_STATE


class CorruptedLineageFailure(ClassifiedStageFailure):
    code = FailureCode.CORRUPTED_LINEAGE


@dataclass(frozen=True)
class FailureClassification:
    code: FailureCode
    retryable: bool
    safe_stop: bool
    recommended_human_action: str


_ACTIONS = {
    FailureCode.OPENAI_TIMEOUT: "Check provider availability, then retry the stopped stage.",
    FailureCode.TEMPORARY_EXTERNAL_PROVIDER_ERROR: (
        "Check external provider availability, then retry the stopped stage."
    ),
    FailureCode.TEMPORARY_WORKSPACE_TOOL_FAILURE: (
        "Restore the isolated workspace tool, then retry the stopped stage."
    ),
    FailureCode.POLICY_VIOLATION: "Review and resolve the blocking policy decision.",
    FailureCode.FAILED_TEST_ASSERTION: "Fix the candidate or test expectation before resuming.",
    FailureCode.INVALID_REQUIREMENT: "Correct or clarify the requirement before resuming.",
    FailureCode.SECURITY_VIOLATION: "Investigate and remediate the security violation.",
    FailureCode.FORBIDDEN_TOOL_REQUEST: "Review the denied tool request and workflow policy.",
    FailureCode.INVALID_WORKFLOW_STATE: "Repair the workflow state before requesting recovery.",
    FailureCode.CORRUPTED_LINEAGE: "Repair and verify artifact lineage before recovery.",
    FailureCode.UNCLASSIFIED_EXECUTION_ERROR: "Inspect the failure and choose a safe recovery.",
}


class FailureClassifier:
    """Classify exceptions without relying on mutable error text."""

    _retryable = frozenset(
        {
            FailureCode.OPENAI_TIMEOUT,
            FailureCode.TEMPORARY_EXTERNAL_PROVIDER_ERROR,
            FailureCode.TEMPORARY_WORKSPACE_TOOL_FAILURE,
        }
    )

    def classify(self, error: BaseException) -> FailureClassification:
        if isinstance(error, AgentTimeout):
            code = FailureCode.OPENAI_TIMEOUT
        elif isinstance(error, AgentTransientError):
            code = FailureCode.TEMPORARY_EXTERNAL_PROVIDER_ERROR
        elif isinstance(error, AgentToolDenied):
            code = FailureCode.FORBIDDEN_TOOL_REQUEST
        elif isinstance(error, ClassifiedStageFailure):
            code = error.code
        elif isinstance(error, AssertionError):
            code = FailureCode.FAILED_TEST_ASSERTION
        elif isinstance(error, TimeoutError):
            code = FailureCode.TEMPORARY_WORKSPACE_TOOL_FAILURE
        else:
            code = FailureCode.UNCLASSIFIED_EXECUTION_ERROR
        return FailureClassification(
            code=code,
            retryable=code in self._retryable,
            safe_stop=code not in self._retryable,
            recommended_human_action=_ACTIONS[code],
        )


def classification_for_code(code: FailureCode) -> FailureClassification:
    return FailureClassification(
        code=code,
        retryable=code in FailureClassifier._retryable,
        safe_stop=code not in FailureClassifier._retryable,
        recommended_human_action=_ACTIONS[code],
    )
