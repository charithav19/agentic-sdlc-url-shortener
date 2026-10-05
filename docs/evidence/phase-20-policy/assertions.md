# Phase 20 policy assertions

- The code-owned policy set is version `1.0.0` and has a deterministic SHA-256
  identity. The packaged YAML manifest is descriptive and cannot execute rules.
- `WRITE_FILE` rejects traversal, targets outside the exact workflow workspace,
  and common fake credential shapes before mutation. Denied `apply_patch`
  operations preserve the previous file.
- `EXECUTE_COMMAND` allows only `mvn test`, `mvn package`, and `pytest`; command
  strings, arguments, shell syntax, and generated policy instructions cannot
  expand that set.
- `SCHEMA_CHANGE` requires an exact current approved `ARCHITECTURE` artifact.
  `BREAKING_API_CHANGE` requires an exact current approved
  `HIGH_IMPACT_CHANGE` artifact. A stale artifact version remains unauthorized.
- A mandatory test failure yields `MANDATORY_TESTS_PASS@1 DENY`. A failed
  security validation yields `SECURITY_RELEASE_BLOCK@1 DENY`. The release gate
  returns `FAIL` with the applicable versioned rule.
- Audited decisions persist the policy set, decisive rule, action, actor,
  sanitized evidence, and optional artifact/stage references. A denial and its
  `POLICY_VIOLATION` audit event commit in one transaction.
- Secret evidence stores category, line, and a truncated hash fingerprint. Test
  fixtures are visibly fake, and raw credential-like values are absent from
  policy and audit payloads.

The evidence establishes deterministic local guardrails. It does not establish
comprehensive secret detection, production identity or authorization,
regulatory compliance, or live-model security quality.
