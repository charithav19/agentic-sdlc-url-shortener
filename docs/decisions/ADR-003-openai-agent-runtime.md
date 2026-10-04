# ADR-003: Typed SDK providers and bounded specialists

Status: accepted for the requested Phase 10–11 provider/specialist scope.

The application uses the real Python OpenAI Agents SDK 0.23.1 behind
`AgentProvider`. The adapter constructs an SDK `Agent` with a Pydantic
output type and a fixed list of function tools, then calls `Runner.run`
with a turn ceiling. A surrounding asyncio deadline bounds total runtime.
The OpenAI client has zero retries; transient errors are classified for the
future orchestration retry policy. Cancellation propagates unchanged.
Provider failures never switch to a fake response.

This follows the [official SDK quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart?lang=python)
and [agent definitions guide](https://developers.openai.com/api/docs/guides/agents/define-agents).
Python constructor, runner, tool context and exception signatures were
also checked against the installed pinned package.

Each specialist owns instructions, a strict output schema, a tool allowlist,
a 4–8 turn ceiling and a 60-second deadline. Per-run grants must be a subset
of the allowlist. SDK handoffs, MCP servers and workflow/approval tools are
absent. Schemas reject extra keys; deterministic validators reject inconsistent
blocking ambiguity and invalid task dependency/parallel groups.

Inputs are frozen, versioned snapshots with size bounds and UUID context.
Tools only read the supplied snapshots; they never open a host path. The
trusted caller must select and sanitize snapshot content before invocation.
The agent receives no session, repository, state mutation callback, credential
object or approval authority. Output metadata identifies provider, configured
model, SDK version, schema/instruction/context hashes and invocation identity.
The configured model name is recorded; an underlying resolved model snapshot
is not independently reported by this adapter.

SDK tracing export is disabled to avoid exporting requirement/code contents.
API errors expose classified messages rather than raw response bodies.
The secret key lives only in the trusted provider/client and is not included
in inputs, output metadata, tools or fixture evidence.

`FakeAgentProvider` plays explicitly supplied test responses. It deep-copies
fixtures and validates through the same output schema. There is no heuristic
fake reasoning and no implicit successful response for a missing fixture.
Ordinary tests use fake outputs; adapter tests use the actual SDK loop with
a local inference stub and deny HTTP requests. The live smoke is separately
opted in with `RUN_LIVE_AGENT_TESTS=1`.

Scope limits: these specialists provide structured reasoning/reporting on
supplied evidence. Candidate workspace edits, build/test execution, isolated
runner provisioning, tool invocation persistence, durable provider result
attachment and scheduler invocation are still outstanding full-plan work.
The ImplementationAgent must not invent changed files when no change
evidence was supplied. Model test/security/release prose is advisory and
cannot become execution proof or human approval. This delivery does not
satisfy the plan's live engineering demonstration requirement.

