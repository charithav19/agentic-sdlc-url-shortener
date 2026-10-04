# Verified bounded-tool assertions

- File writes, reads, literal searches and unique exact patches operate on real
  workspace files; receipts contain path and content hash.
- Traversal, outside absolute paths, credential paths, symlinked directories/files,
  hardlinks, FIFOs and other workflow paths are denied.
- Secret paths do not appear in listings, searches or candidate archives.
- Malformed/stale patches preserve original contents; size/search limits reject
  excess work without accepting an unbounded result.
- SDK wrappers deny ungranted operations and mismatched workflow contexts.
- Command strings containing shells, separators, substitutions, extra flags or
  alternate executables fail before Docker is invoked.
- Real isolated `mvn test`, `mvn package` and `pytest` fixtures succeed.
- Candidate code cannot see a host API-key canary, host paths or Docker socket.
  It cannot write the root filesystem or connect externally.
- In-container capability, no-new-privileges and resource settings match policy.
- An assertion failure yields an actual nonzero exit and COMMAND_FAILED.
- Slow/noisy candidates produce TIMEOUT/OUTPUT_LIMIT and are destroyed.
- Cancellation and pre-execution isolation rejection leave no test containers.
- New workflows receive `workspaces/<UUID>/` while their status remains
  controlled by WorkflowOrchestrator.

The results cover local file operations and disposable Docker fixtures.
They do not claim a live model-generated application or persistent build artifacts.

