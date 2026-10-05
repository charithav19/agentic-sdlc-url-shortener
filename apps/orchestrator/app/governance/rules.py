"""Versioned metadata for deterministic, code-owned policy rules."""

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    version: str
    description: str


POLICY_SET_VERSION = "1.0.0"

_RULES = (
    PolicyRule("FILE_NO_SECRETS", "1", "Generated files must not contain credential material"),
    PolicyRule("PATH_NO_TRAVERSAL", "1", "Workspace paths must not contain traversal"),
    PolicyRule("WRITE_WORKSPACE_ONLY", "1", "Writes must remain in the workflow workspace"),
    PolicyRule("COMMAND_ALLOWLIST", "1", "Only registered command profiles may execute"),
    PolicyRule(
        "SCHEMA_CHANGE_APPROVAL",
        "1",
        "Schema changes require exact current architecture approval",
    ),
    PolicyRule(
        "BREAKING_API_APPROVAL",
        "1",
        "Breaking API changes require exact high-impact-change approval",
    ),
    PolicyRule("MANDATORY_TESTS_PASS", "1", "Mandatory test failures block release"),
    PolicyRule("SECURITY_RELEASE_BLOCK", "1", "Security violations block release"),
    PolicyRule("UNREGISTERED_CAPABILITY", "1", "Unregistered capabilities are denied"),
)

POLICY_RULES = MappingProxyType({rule.rule_id: rule for rule in _RULES})

_canonical = json.dumps(
    {
        "version": POLICY_SET_VERSION,
        "rules": [
            {"id": rule.rule_id, "version": rule.version, "description": rule.description}
            for rule in _RULES
        ],
    },
    sort_keys=True,
    separators=(",", ":"),
)
POLICY_SET_HASH = hashlib.sha256(_canonical.encode("utf-8")).hexdigest()

ALLOWED_COMMANDS = frozenset({"mvn test", "mvn package", "pytest"})
