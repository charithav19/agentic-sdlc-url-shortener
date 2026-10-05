# Brownfield scenario

The input is `Add custom aliases and expiration.` The seed is an existing Spring Boot service with basic random-code creation and HTTP 302 redirect behavior. It intentionally lacks aliases and expiration.

Before planning, `ScenarioFixtureRunner` copies the seed into the UUID-owned workflow workspace. `SourceImpactAnalyzer` reads the materialized files through the bounded workspace API and classifies responsibilities from source evidence: Spring controller and service annotations, JPA entity and repository declarations, redirect response calls, Flyway SQL, JUnit tests, and OpenAPI annotations. It never uses a list of expected Java class names. A rename test proves that an annotated service is still discovered under a different path and class name.

The persisted source-impact artifact contains the exact inspected paths. The planning and implementation-report artifacts must refer only to files present in that inspection. Expected responsibilities are controller, service, domain/entity, repository, redirect behavior, migration, tests, and OpenAPI documentation.

Run the seed regression and PostgreSQL scenario with:

```sh
JAVA_HOME=$(/usr/libexec/java_home -v 21) apps/url-shortener/mvnw \
  --batch-mode -f scenarios/brownfield/seed/pom.xml test
UV=/absolute/path/to/uv scripts/test-postgres.sh \
  tests/test_zz_required_scenarios.py::BrownfieldScenarioIT -q
```

The seed regression proves its original create and redirect behavior. The full product suite separately proves alias validation/conflicts, expiration `410`, migration behavior, regressions, and OpenAPI. The scenario uses deterministic specialist outputs and does not present those outputs as live code-generation evidence.
