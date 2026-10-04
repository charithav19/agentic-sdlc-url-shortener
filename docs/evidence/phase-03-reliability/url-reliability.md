# Phase 3 URL reliability assertion record

All assertions below ran in the final `mvn verify` suite. MockMvc API cases use the Spring application and PostgreSQL Testcontainers; the limiter also has a direct unit test. This is automated local test evidence, not a deployed service transcript.

- `AliasTest`: 3- and 32-character boundaries, case sensitivity, invalid/reserved alias `400`, duplicate alias `409`.
- `ExpiryTest`: future-only `expiresAt`, `302` before expiration and `410` at the exact controlled-clock boundary.
- `DisableLinkTest`: repeatable `DELETE` returns `204`, missing code `404`, disabled redirect `410`, concurrent disable succeeds.
- `CollisionTest`: injected generator forces collision then recovery; five total failed attempts exhaust; next request still succeeds in PostgreSQL.
- `IdempotencyTest`: same key/request replays the original response even after link disable; changed request conflicts; two concurrent identical requests create one link and one record.
- `RateLimitTest` and `RateLimitApiTest`: bounded capacity/window, create-route-only count, HTTP `429` and `Retry-After`.
- `LinkPersistenceTest`: Flyway V1 and V2 are recorded successful and database uniqueness remains enforced.

The limiter is global per process, resets on restart and uses no client IP or proxy headers. The idempotency scope is anonymous and durable records have no automatic eviction. Analytics and agentic scenarios are later phases.
