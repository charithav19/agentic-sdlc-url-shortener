# Phase 2 PostgreSQL assertion record

`LinkPersistenceTest` starts a real PostgreSQL 17.7 Testcontainers instance and verifies Flyway V1 is recorded as successful, `links` exists, a saved link survives JPA persistence-context clearing, and inserting a duplicate `short_code` raises `DataIntegrityViolationException` from the database uniqueness constraint.

`LinkRestartTest` creates a link, closes the Spring application context, opens another context against the same PostgreSQL container, and verifies the link remains available. The database container remains live across the two contexts; this is application restart evidence, not durable container volume restart evidence.
