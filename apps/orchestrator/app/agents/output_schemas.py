"""Strict specialist outputs. Recommendations are not execution or approval evidence."""

from graphlib import CycleError, TopologicalSorter
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RequirementOutput(AgentOutput):
    normalized_requirement: str = Field(min_length=1)
    acceptance_criteria: list[str]
    ambiguities: list[str]
    clarifying_questions: list[str]
    assumptions: list[str]
    blocking_ambiguity: bool
    risks: list[str]

    @model_validator(mode="after")
    def require_blocking_questions(self) -> Self:
        if self.blocking_ambiguity and (not self.ambiguities or not self.clarifying_questions):
            raise ValueError("Blocking ambiguity requires ambiguities and clarifying questions")
        return self


class Task(AgentOutput):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    affected_components: list[str]


class TaskDependency(AgentOutput):
    task_id: str
    depends_on: str


class PlanningOutput(AgentOutput):
    tasks: list[Task]
    dependencies: list[TaskDependency]
    parallelizable_groups: list[list[str]]
    affected_components: list[str]
    risks: list[str]

    @model_validator(mode="after")
    def validate_task_graph(self) -> Self:
        names = {task.id for task in self.tasks}
        if len(names) != len(self.tasks):
            raise ValueError("Duplicate task IDs")
        graph: dict[str, set[str]] = {name: set() for name in names}
        for edge in self.dependencies:
            if edge.task_id not in names or edge.depends_on not in names:
                raise ValueError("Unknown task dependency")
            graph[edge.task_id].add(edge.depends_on)
        try:
            order = tuple(TopologicalSorter(graph).static_order())
        except CycleError as error:
            raise ValueError("Task dependency cycle") from error
        ancestors: dict[str, set[str]] = {}
        for name in order:
            ancestors[name] = set(graph[name])
            for parent in graph[name]:
                ancestors[name].update(ancestors[parent])
        for group in self.parallelizable_groups:
            if len(set(group)) != len(group) or not set(group) <= names:
                raise ValueError("Invalid parallelizable group")
            if any(ancestors[name].intersection(group) for name in group):
                raise ValueError("Dependent tasks cannot be parallelized")
        return self


class ArchitectureOutput(AgentOutput):
    components: list[str]
    api_changes: list[str]
    data_changes: list[str]
    security_considerations: list[str]
    failure_modes: list[str]
    tradeoffs: list[str]
    testing_implications: list[str]


class ImplementationOutput(AgentOutput):
    changed_files: list[str]
    created_files: list[str]
    summary: str = Field(min_length=1)
    tests_requested: list[str]
    risks: list[str]


class TestOutput(AgentOutput):
    test_plan: list[str]
    acceptance_criterion_mapping: list[str]
    generated_tests: list[str]
    evidence_references: list[str]
    uncovered_risks: list[str]


class SecurityFinding(AgentOutput):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rule: str
    evidence: str
    affected_files: list[str]
    remediation: str


class SecurityOutput(AgentOutput):
    findings: list[SecurityFinding]
    blocking: bool
    limitations: list[str]


class DocumentationOutput(AgentOutput):
    documentation_artifacts: list[str]
    api_changes: list[str]
    run_instructions: list[str]
    test_instructions: list[str]
    limitations: list[str]


class ReleaseReadinessOutput(AgentOutput):
    candidate_reference: str
    evidence_references: list[str]
    readiness_assessment: str
    unresolved_risks: list[str]
    release_recommendation: Literal["READY_FOR_REVIEW", "NOT_READY"]
