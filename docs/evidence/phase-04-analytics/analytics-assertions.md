# Phase 4 analytics assertion record

Source: final `mvn verify` in the actual repository. API tests use Spring MockMvc and real PostgreSQL Testcontainers; this is local automated evidence, not a deployed-service transcript.

- `AnalyticsTest`: successful redirects persist link ID, controlled UTC timestamp, origin-only referrer, coarse user-agent category and matching request trace ID; persisted events aggregate into two UTC calendar days. Metadata, missing and expired redirects create no event. Missing analytics code returns `404`.
- `AnalyticsFailureIsolationTest`: a forced writer exception and a stalled worker both leave a valid redirect at `302` with the destination `Location`; failures increment the Micrometer counter.
- `AnalyticsTimeoutTest`: a PostgreSQL exclusive table lock forces the actual click-event INSERT to hit its write timeout while the redirect still returns `302`; failure counter increments.
- `AnalyticsRecorderTest`: rejected queue submission is dropped without throwing to the caller; dropped counter increments.
- `ObservabilityTest`: health/readiness, Prometheus, metrics and OpenAPI endpoints work; `/actuator/env` is unavailable; successful redirects increment a low-cardinality counter and the executor queue is bounded.
- All Phase 2–3 regression tests remain passing. Flyway V3 is applied during PostgreSQL application startup and click-event writes succeed.

The queue is per instance and in memory. Events can be lost on crash, rejection or write failure; totals can lag. No exactly-once or durable broker claim is made.
