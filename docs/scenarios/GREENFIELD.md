# Greenfield scenario

The input is `Build URL shortener with core APIs, analytics and reliability.` The seed is a minimal Java 21 Spring Boot application with one bootstrap test. It contains no URL API, domain, persistence, analytics, or reliability implementation.

The deterministic scenario test creates a persisted `GREENFIELD` workflow and executes the configured 16-stage DAG. It records structured fake-provider artifacts for requirement analysis, planning, architecture, implementation reporting, test design, security, documentation, and release readiness. Architecture and release both pause on exact-version human approvals. The implementation/test-design/documentation group and the unit/integration/security group overlap under bounded concurrency; the configured joins prevent early downstream work.

Run the fixture and its database-backed end-to-end test with:

```sh
JAVA_HOME=$(/usr/libexec/java_home -v 21) apps/url-shortener/mvnw \
  --batch-mode -f scenarios/greenfield/seed/pom.xml test
UV=/absolute/path/to/uv scripts/test-postgres.sh \
  tests/test_zz_required_scenarios.py::GreenfieldScenarioIT -q
```

Expected assertions include a buildable minimal seed, immutable artifacts for each lifecycle concern, two approval pauses, all 16 stages succeeding, both parallel groups overlapping, and a final `COMPLETED` workflow with a current release approval.

The deterministic fake provider verifies orchestration repeatability. It is not evidence of a live OpenAI engineering run or model-authored candidate changes. The completed URL-shortener product is validated separately by the root Java suite.
