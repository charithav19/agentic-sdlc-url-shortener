# Phase 18 artifact lineage verification assertions

- Artifact payloads remain immutable, hashed and versioned; lineage records
  refer to exact artifact IDs rather than mutable logical names.
- The allowed relationship vocabulary is `DERIVED_FROM`, `IMPLEMENTS`,
  `VALIDATES`, `DOCUMENTS`, and `SUPERSEDES` in both application and database
  validation.
- Parent and child queries return typed edges with exact artifact version/hash,
  producer stage, requirement IDs and component IDs.
- Transitive descendants are breadth-first, deterministic, de-duplicated and
  report minimum depth across a multi-level branching graph.
- Self-links, cross-workflow links, missing artifacts, unknown relationship
  values, cycle-producing links and reversed `SUPERSEDES` versions are rejected.
- Repeating the same relationship is idempotent and does not create duplicate
  edges.
- Lineage creation writes an audit event carrying the edge, relationship and
  stable requirement/component IDs in the same unit of work.
- The database migration normalizes historical `REVISES` rows to `SUPERSEDES`,
  adds the relationship constraint and indexes both traversal directions.

This evidence covers artifact versioning and typed lineage. It does not claim
the planned artifact/lineage HTTP API, decision lineage, lifecycle API, CLI tree
rendering, impact analysis or selective replanning.
