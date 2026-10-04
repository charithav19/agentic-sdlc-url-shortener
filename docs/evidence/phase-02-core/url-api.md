# Phase 2 URL API assertion record

Source: `LinkApiTest` executed by both `mvn test` and `mvn package` against PostgreSQL Testcontainers with Spring MockMvc. This is automated controller-level evidence, not a deployed service transcript.

- POST `/api/v1/links` with an HTTPS URL: `201`, metadata including UUID, seven-character Base62 code, short URL, status `ACTIVE`, created time and null expiry; `Location` equals short URL.
- GET `/api/v1/links/{shortCode}`: `200` and matching metadata.
- GET `/{shortCode}`: `302` and `Location` equals the original URL.
- Unknown code at both lookup and redirect routes: structured `404` with matching response/header trace IDs.
- Unsupported scheme, credentials, empty URL and requests containing deferred `customAlias` or `expiresAt`: `400`, no rows created.
- GET `/v3/api-docs` and `/actuator/health`: `200`; `/actuator/env`: `404`.

These assertions establish Phase 2 behavior only. Alias, expiry, collision retry, idempotency, rate limiting and analytics are not demonstrated.
