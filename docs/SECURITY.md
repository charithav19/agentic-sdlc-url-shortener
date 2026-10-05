# Engineering tool security boundary

The seven engineering tools are `list_files`, `read_file`, `search_code`,
`write_file`, `apply_patch`, `run_build` and `run_tests`. They receive a
trusted capability for exactly `workspaces/<workflow-UUID>/`, derived from
the context UUID rather than a model-supplied root. The creation service
allocates that directory and stores its canonical relative reference. Its
legacy `workspace_ref` input is a seed label recorded in the creation audit;
it cannot redirect file access. An empty orphan directory can remain after a
database rollback; no candidate content is automatically deleted.

Every SDK function checks its per-run authorization and exact context.
The granted tool set must be a subset of the specialist allowlist.
Implementation can edit/build/test; testing can edit/test; documentation can
edit. Requirement/release specialists remain artifact-only. No tool receives
workflow-state, database, human-approval or Docker control capabilities.

## Filesystem enforcement

Paths are validated before access. Traversal components, outside absolute
paths, Windows/alternate path spellings, control characters and credential
names are rejected. Absolute paths inside the assigned workspace are accepted.
Directory-relative file descriptors and `O_NOFOLLOW` prevent symlink traversal;
reads check the opened descriptor is a single-link regular file. Writes use
a temporary file and atomic rename. Existing symlinks, hardlinks and special
files cannot be read or overwritten.

Listings, searches and candidate archives exclude credential paths, symlinks,
hardlinks, sockets and FIFOs. Denials include `.env*`, credential/secret files,
private-key extensions, SSH/AWS/Docker/Kubernetes/configuration directories,
Git credentials, service-account JSON, token JSON and Docker socket paths.
The trusted caller must avoid putting secrets in ordinary source files: path
filters are not general secret-content detection.

Limits are 256,000 bytes per file, 512 files, 1,024 traversed entries, 16 path
components, and 8,000,000 bytes per candidate snapshot. Searches are literal
rather than regular expressions and return at most 100 lines of 512 characters.
`apply_patch(path, old_text, new_text)` performs one exact unique replacement.
Empty, missing or ambiguous matches fail without changing the file. The tool
does not invoke a host patch utility or accept a multi-file shell patch.

Tools assume a trusted control plane and one active writer per workflow.
Parallel stage overlays/assembly and distributed write coordination remain
future orchestration work. Local users with host/Docker administrator
privileges are outside this boundary.

## Isolated commands

The command allowlist is exact:

| Tool | Input | Fixed execution |
|---|---|---|
| `run_build` | `mvn package` | `mvn -o -B -Dmaven.repo.local=/tmp/m2 package` |
| `run_tests` | `mvn test` | `mvn -o -B -Dmaven.repo.local=/tmp/m2 test` |
| `run_tests` | `pytest` | `/opt/venv/bin/python -I -m pytest` |

No extra arguments, environment variables, executable paths or shell strings
are accepted. `project` is a validated relative subdirectory or `.`.
The container entry point checks the profile again and uses an argument
array with `execve`.

Build scripts/tests can execute arbitrary candidate code, so the allowlist is
paired with a Docker boundary. The trusted runner copies a bounded regular-file
archive over stdin into a fresh container tmpfs. There are no host bind mounts,
volumes, secrets or Docker sockets in the container. The root filesystem is
read-only; the candidate user is UID/GID 10001; capabilities are dropped and
new privileges disabled. Network is disabled. The limits are one CPU, 768 MiB
memory without swap, 128 processes, 256 open files and no core dumps.
Writable tmpfs is restricted to `/workspace` (64 MiB) and `/tmp` (256 MiB).
The Docker configuration is inspected and rejected before candidate execution
when required restrictions are absent. See the
[Docker runtime reference](https://docs.docker.com/engine/containers/run/)
for the underlying controls.

Execution has a 30-second default deadline (trusted configuration up to 120)
and captures at most 64,000 raw output bytes. Failure, timeout, output overflow
and cancellation remove the container. Startup/policy failures never fall back
to host execution. The receipt records command, workflow, candidate hash,
resolved image ID, timestamps, actual container exit code and error class.
An exited container is required; a container that never started cannot be
reported as successful. Candidate-generated output remains untrusted, and a
zero exit code alone is not release approval or comprehensive test evidence.

Human approval uses a separate local bearer credential configured through
`ORCHESTRATOR_LOCAL_REVIEWER_TOKEN` plus an explicit `X-Reviewer-Id`. The token
belongs only in the trusted orchestrator process and is never provided to agent
tools or workspaces. This prototype credential establishes a local trust
boundary; production deployment still requires a real identity provider,
authorization policy, transport security, credential rotation, and protected
audit access.

The image includes Java 21/Maven, Python/pytest and a small prepared Maven
dependency cache. Candidate execution is offline. Other dependencies require
a trusted image rebuild; agents cannot install them or enable network access.
Build outputs are ephemeral and not copied back to the host workspace.
Tool receipts are attached to provider results; durable invocation storage,
broader redaction/governance and candidate artifact retention remain planned.

## Verification

`make test-runner` builds the image and runs actual Maven test/package and
pytest fixtures. Security tests verify host-secret exclusion, inaccessible
Docker socket/host paths, read-only root, disabled network, capability and
resource settings, real failure exit codes, timeout/output limits, cancellation,
and cleanup after rejected isolation. `tests/test_tools.py` verifies filesystem
and SDK allowlist denials. This is local Docker isolation evidence, not a claim
of protection from Docker/kernel vulnerabilities or hostile host administrators.
