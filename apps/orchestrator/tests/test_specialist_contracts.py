"""Schema validation and immutable authority boundary for all eight specialists."""

import ast
import copy
from pathlib import Path

import pytest
from agents.agent_output import AgentOutputSchema
from pydantic import ValidationError

from app.agents.output_schemas import PlanningOutput, RequirementOutput
from app.agents.registry import SPECIALISTS
from app.orchestration.registry import DEFAULT_REGISTRY
from tests.agent_fixtures import OUTPUTS


@pytest.mark.parametrize("specialist", SPECIALISTS.values(), ids=lambda item: item.name)
def test_specialist_contract(specialist) -> None:
    assert specialist.instructions
    assert "Never change workflow or stage status" in specialist.instructions
    assert 0 < specialist.max_turns <= 8
    assert 0 < specialist.timeout_seconds <= 60
    output = specialist.output_type.model_validate(copy.deepcopy(OUTPUTS[specialist.name]))
    assert output is not None
    schema = AgentOutputSchema(specialist.output_type).json_schema()
    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError):
        specialist.output_type.model_validate({**OUTPUTS[specialist.name], "status": "COMPLETED"})
    with pytest.raises(ValidationError):
        specialist.output_type.model_validate({})
    assert set(specialist.allowed_tools) <= {
        "read_artifact",
        "read_file",
        "list_files",
        "search_code",
    }


def test_specialists_bind_existing_graph_identifiers() -> None:
    assert len(SPECIALISTS) == 8
    assert set(SPECIALISTS) <= DEFAULT_REGISTRY.executors


def test_blocking_ambiguity_requires_questions() -> None:
    value = {**OUTPUTS["RequirementAgent"], "blocking_ambiguity": True}
    with pytest.raises(ValidationError, match="Blocking ambiguity"):
        RequirementOutput.model_validate(value)
    value.update(ambiguities=["Undefined policy"], clarifying_questions=["Which policy?"])
    assert RequirementOutput.model_validate(value).blocking_ambiguity


@pytest.mark.parametrize("case", ["duplicate", "unknown", "cycle", "parallel"])
def test_invalid_task_graph(case) -> None:
    value = copy.deepcopy(OUTPUTS["PlanningAgent"])
    if case == "duplicate":
        value["tasks"].append(value["tasks"][0])
    elif case == "unknown":
        value["dependencies"].append({"task_id": "B", "depends_on": "UNKNOWN"})
    elif case == "cycle":
        value["dependencies"].append({"task_id": "A", "depends_on": "B"})
    else:
        value["parallelizable_groups"] = [["A", "C"]]
    with pytest.raises(ValidationError):
        PlanningOutput.model_validate(value)


def test_agent_modules_have_no_persistence_or_status_authority_imports() -> None:
    root = Path(__file__).parents[1] / "app"
    for path in [*(root / "agents").glob("*.py"), root / "tools/snapshots.py"]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("app.persistence", "app.orchestration", "app.observability.audit_store")
                ), path
