"""Deterministic policy evaluation and atomic durable policy/audit records."""

import uuid
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.governance.approvals import ApprovalStatus, ApprovalType
from app.governance.rules import (
    ALLOWED_COMMANDS,
    POLICY_RULES,
    POLICY_SET_HASH,
    POLICY_SET_VERSION,
)
from app.governance.security_findings import SecretScanner


class PolicyResult(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class PolicyAction(StrEnum):
    WRITE_FILE = "WRITE_FILE"
    EXECUTE_COMMAND = "EXECUTE_COMMAND"
    SCHEMA_CHANGE = "SCHEMA_CHANGE"
    BREAKING_API_CHANGE = "BREAKING_API_CHANGE"
    RELEASE = "RELEASE"


class ExactArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: uuid.UUID
    version: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PolicyApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    approval_type: ApprovalType
    status: ApprovalStatus
    artifact_id: uuid.UUID
    artifact_version: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    def matches(self, artifact: ExactArtifactReference, expected: ApprovalType) -> bool:
        return (
            self.approval_type is expected
            and self.status is ApprovalStatus.APPROVED
            and self.artifact_id == artifact.id
            and self.artifact_version == artifact.version
            and self.artifact_hash == artifact.sha256
        )


class PolicyInput(BaseModel):
    """Trusted facts supplied to policy; repository text cannot alter this schema."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    action: str = Field(min_length=1, max_length=128)
    actor_type: Literal["SYSTEM", "AGENT", "HUMAN"] = "SYSTEM"
    actor_id: str = Field(default="policy-engine", min_length=1, max_length=128)
    stage_run_id: uuid.UUID | None = None
    workspace_root: str | None = None
    target_path: str | None = None
    content: str | None = None
    command: str | None = None
    governed_artifact: ExactArtifactReference | None = None
    approvals: tuple[PolicyApproval, ...] = ()
    mandatory_test_failures: tuple[str, ...] = ()
    security_violations: tuple[str, ...] = ()
    artifact_refs: tuple[ExactArtifactReference, ...] = ()


class PolicyFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rule_id: str
    rule_version: str
    result: PolicyResult
    reason: str
    blocking: bool
    evidence: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    result: PolicyResult
    policy_set_version: str
    policy_set_hash: str
    findings: tuple[PolicyFinding, ...]

    @property
    def decisive_finding(self) -> PolicyFinding:
        return self.findings[0]


class PolicyEngine:
    """Evaluate code-owned rules and optionally persist the decision atomically."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        secret_scanner: SecretScanner | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.secret_scanner = secret_scanner or SecretScanner()

    def evaluate(self, policy_input: PolicyInput) -> PolicyDecision:
        try:
            action = PolicyAction(policy_input.action)
        except ValueError:
            return self._decision(
                self._finding(
                    "UNREGISTERED_CAPABILITY",
                    PolicyResult.DENY,
                    "Capability is not registered in the policy engine",
                )
            )

        if action is PolicyAction.WRITE_FILE:
            return self._evaluate_write(policy_input)
        if action is PolicyAction.EXECUTE_COMMAND:
            return self._evaluate_command(policy_input)
        if action is PolicyAction.SCHEMA_CHANGE:
            return self._evaluate_approval(
                policy_input,
                ApprovalType.ARCHITECTURE,
                "SCHEMA_CHANGE_APPROVAL",
                "Schema change requires approval for the exact architecture artifact",
            )
        if action is PolicyAction.BREAKING_API_CHANGE:
            return self._evaluate_approval(
                policy_input,
                ApprovalType.HIGH_IMPACT_CHANGE,
                "BREAKING_API_APPROVAL",
                "Breaking API change requires approval for the exact change artifact",
            )
        return self._evaluate_release(policy_input)

    async def evaluate_and_record(
        self, workflow_id: uuid.UUID, policy_input: PolicyInput
    ) -> PolicyDecision:
        if self.session_factory is None:
            raise RuntimeError("A session factory is required to persist policy decisions")
        decision = self.evaluate(policy_input)
        finding = decision.decisive_finding

        # Imported lazily so the UnitOfWork may expose the policy repository without
        # creating a module cycle during persistence model initialization.
        from app.persistence.unit_of_work import UnitOfWork

        async with UnitOfWork.open(self.session_factory) as unit:
            event = await unit.policies.add(
                workflow_id,
                stage_run_id=policy_input.stage_run_id,
                policy_set_version=decision.policy_set_version,
                policy_set_hash=decision.policy_set_hash,
                rule_id=finding.rule_id,
                rule_version=finding.rule_version,
                result=decision.result.value,
                action=policy_input.action,
                actor_type=policy_input.actor_type,
                actor_id=policy_input.actor_id,
                reason=finding.reason,
                blocking=finding.blocking,
                artifact_refs=[ref.model_dump(mode="json") for ref in policy_input.artifact_refs],
                evidence=finding.evidence,
            )
            audit_type = {
                PolicyResult.ALLOW: "POLICY_ALLOWED",
                PolicyResult.DENY: "POLICY_VIOLATION",
                PolicyResult.REQUIRE_APPROVAL: "POLICY_APPROVAL_REQUIRED",
            }[decision.result]
            await unit.audit.append(
                workflow_id,
                event_type=audit_type,
                actor_type=policy_input.actor_type,
                actor_id=policy_input.actor_id,
                stage_run_id=policy_input.stage_run_id,
                artifact_refs=[ref.model_dump(mode="json") for ref in policy_input.artifact_refs],
                reason=finding.reason,
                payload={
                    "policy_event_id": str(event.id),
                    "policy_set_version": decision.policy_set_version,
                    "policy_set_hash": decision.policy_set_hash,
                    "rule_id": finding.rule_id,
                    "rule_version": finding.rule_version,
                    "result": decision.result.value,
                    "action": policy_input.action,
                    "evidence": finding.evidence,
                },
            )
        return decision

    def _evaluate_write(self, policy_input: PolicyInput) -> PolicyDecision:
        path_finding = self._path_finding(policy_input)
        if path_finding is not None:
            return self._decision(path_finding)
        if policy_input.content is None:
            return self._decision(
                self._finding(
                    "FILE_NO_SECRETS",
                    PolicyResult.DENY,
                    "Generated file content is required for secret scanning",
                )
            )
        findings = self.secret_scanner.scan(policy_input.content)
        if findings:
            return self._decision(
                self._finding(
                    "FILE_NO_SECRETS",
                    PolicyResult.DENY,
                    "Generated file contains credential-like content",
                    evidence={
                        "path": policy_input.target_path,
                        "findings": [
                            {
                                "kind": finding.kind,
                                "line": finding.line,
                                "fingerprint": finding.fingerprint,
                            }
                            for finding in findings
                        ],
                    },
                )
            )
        return self._allow("FILE_NO_SECRETS", "Generated file passed workspace and secret policies")

    def _path_finding(self, policy_input: PolicyInput) -> PolicyFinding | None:
        path = policy_input.target_path
        root = policy_input.workspace_root
        if not path or not root:
            return self._finding(
                "WRITE_WORKSPACE_ONLY",
                PolicyResult.DENY,
                "Write target and workflow workspace are required",
            )
        target = Path(path)
        path_parts = PurePosixPath(path).parts
        if (
            "\\" in path
            or ":" in path
            or any(ord(character) < 32 for character in path)
            or any(part in {".", ".."} for part in path_parts)
            or (not target.is_absolute() and any(part == "" for part in path.split("/")))
        ):
            return self._finding(
                "PATH_NO_TRAVERSAL",
                PolicyResult.DENY,
                "Write path contains traversal or an alternate path spelling",
            )
        root_path = Path(root).resolve()
        if target.is_absolute():
            candidate = target.resolve(strict=False)
        else:
            # PurePosixPath rejects platform-specific normalization as policy input.
            candidate = root_path.joinpath(*PurePosixPath(path).parts).resolve(strict=False)
        try:
            candidate.relative_to(root_path)
        except ValueError:
            return self._finding(
                "WRITE_WORKSPACE_ONLY",
                PolicyResult.DENY,
                "Write target is outside the workflow workspace",
            )
        return None

    def _evaluate_command(self, policy_input: PolicyInput) -> PolicyDecision:
        if policy_input.command not in ALLOWED_COMMANDS:
            return self._decision(
                self._finding(
                    "COMMAND_ALLOWLIST",
                    PolicyResult.DENY,
                    "Command is not in the fixed execution allowlist",
                )
            )
        return self._allow("COMMAND_ALLOWLIST", "Command matches a fixed execution profile")

    def _evaluate_approval(
        self,
        policy_input: PolicyInput,
        approval_type: ApprovalType,
        rule_id: str,
        reason: str,
    ) -> PolicyDecision:
        artifact = policy_input.governed_artifact
        if artifact is not None and any(
            approval.matches(artifact, approval_type) for approval in policy_input.approvals
        ):
            return self._allow(rule_id, f"Exact {approval_type.value} approval is current")
        return self._decision(
            self._finding(
                rule_id,
                PolicyResult.REQUIRE_APPROVAL,
                reason,
                evidence={
                    "required_approval_type": approval_type.value,
                    "artifact": artifact.model_dump(mode="json") if artifact else None,
                },
            )
        )

    def _evaluate_release(self, policy_input: PolicyInput) -> PolicyDecision:
        if policy_input.security_violations:
            return self._decision(
                self._finding(
                    "SECURITY_RELEASE_BLOCK",
                    PolicyResult.DENY,
                    "Security violation blocks release",
                    evidence={"violations": list(policy_input.security_violations)},
                )
            )
        if policy_input.mandatory_test_failures:
            return self._decision(
                self._finding(
                    "MANDATORY_TESTS_PASS",
                    PolicyResult.DENY,
                    "Mandatory test failure blocks release",
                    evidence={"failed_checks": list(policy_input.mandatory_test_failures)},
                )
            )
        return self._allow(
            "MANDATORY_TESTS_PASS", "Mandatory tests and security policy checks passed"
        )

    def _allow(self, rule_id: str, reason: str) -> PolicyDecision:
        return self._decision(
            self._finding(
                rule_id,
                PolicyResult.ALLOW,
                reason,
                blocking=False,
            )
        )

    def _finding(
        self,
        rule_id: str,
        result: PolicyResult,
        reason: str,
        *,
        blocking: bool = True,
        evidence: dict[str, Any] | None = None,
    ) -> PolicyFinding:
        rule = POLICY_RULES[rule_id]
        return PolicyFinding(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            result=result,
            reason=reason,
            blocking=blocking,
            evidence=evidence or {},
        )

    @staticmethod
    def _decision(finding: PolicyFinding) -> PolicyDecision:
        return PolicyDecision(
            result=finding.result,
            policy_set_version=POLICY_SET_VERSION,
            policy_set_hash=POLICY_SET_HASH,
            findings=(finding,),
        )


DEFAULT_POLICY_ENGINE = PolicyEngine()
