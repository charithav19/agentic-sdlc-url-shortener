# ADR-002: Configurable, validated SDLC graph

**Status:** Accepted for the Phase 7 graph definition (2026-10-04)

The SDLC graph is declared in `apps/orchestrator/config/default_sdlc.yaml`.
The loader parses YAML with a safe loader, rejects duplicate mapping keys,
validates required stage fields and known symbolic executor/gate identifiers,
then rejects missing dependencies, duplicate stages and cycles. It produces
an immutable graph with a deterministic SHA-256 over normalized stage
definitions. Reordering YAML stages or a stage's dependency list does not
change the graph hash.

The ordinary graph has 16 stages. With blocking ambiguity, the configured
`CLARIFICATION` stage is inserted after `REQUIREMENT_ANALYSIS`, and
`TASK_DECOMPOSITION` depends on it. `requirements_unambiguous` remains the
entry gate for decomposition. A clarification answer must be followed by a
new requirements analysis generation before that gate can pass; this is
future orchestration behavior, not a back edge in this DAG.

Executor and gate identifiers are declarations, not executable registrations.
This phase neither invokes agents nor changes workflow/stage state. The graph
hash identifies configuration variants, but durable graph revisions and
workflow bindings must be added before execution is enabled. The user
requested the loader and validation in this phase; graph APIs and revision
storage remain outside this change.

The YAML is packaged into the Python wheel so the default loader works from
an installed distribution as well as a source checkout.
