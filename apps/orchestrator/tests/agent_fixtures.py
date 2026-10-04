"""Deterministic agent responses, explicitly test-only and not execution evidence."""

OUTPUTS = {
    "RequirementAgent": {
        "normalized_requirement": "Create HTTP and HTTPS short links.",
        "acceptance_criteria": ["HTTP redirect returns 302."],
        "ambiguities": [],
        "clarifying_questions": [],
        "assumptions": [],
        "blocking_ambiguity": False,
        "risks": ["Destination availability is external."],
    },
    "PlanningAgent": {
        "tasks": [
            {"id": "A", "description": "Define API", "affected_components": ["api"]},
            {"id": "B", "description": "Implement API", "affected_components": ["api"]},
            {"id": "C", "description": "Design tests", "affected_components": ["tests"]},
        ],
        "dependencies": [
            {"task_id": "B", "depends_on": "A"},
            {"task_id": "C", "depends_on": "A"},
        ],
        "parallelizable_groups": [["B", "C"]],
        "affected_components": ["api", "tests"],
        "risks": [],
    },
    "ArchitectureAgent": {
        "components": ["Spring Boot URL service"],
        "api_changes": ["POST /api/v1/links"],
        "data_changes": ["links table"],
        "security_considerations": ["Validate URL schemes."],
        "failure_modes": ["Missing link returns 404."],
        "tradeoffs": ["In-memory rate limit is per instance."],
        "testing_implications": ["PostgreSQL integration tests."],
    },
    "ImplementationAgent": {
        "changed_files": [],
        "created_files": [],
        "summary": "Fixture only; no candidate changes executed.",
        "tests_requested": ["Create and redirect integration test"],
        "risks": ["No implementation evidence supplied."],
    },
    "TestAgent": {
        "test_plan": ["Verify redirect 302."],
        "acceptance_criterion_mapping": ["302 redirect -> redirect test"],
        "generated_tests": [],
        "evidence_references": [],
        "uncovered_risks": ["No test execution."],
    },
    "SecurityAgent": {
        "findings": [],
        "blocking": True,
        "limitations": ["No scanner evidence supplied."],
    },
    "DocumentationAgent": {
        "documentation_artifacts": ["Proposed API guide: POST /api/v1/links creates a link."],
        "api_changes": ["POST /api/v1/links"],
        "run_instructions": ["See service README."],
        "test_instructions": ["mvn test"],
        "limitations": ["Instructions not executed by fixture."],
    },
    "ReleaseReadinessAgent": {
        "candidate_reference": "not-supplied",
        "evidence_references": [],
        "readiness_assessment": "Execution evidence is missing.",
        "unresolved_risks": ["No release candidate."],
        "release_recommendation": "NOT_READY",
    },
}
