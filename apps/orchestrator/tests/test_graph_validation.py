"""The configured SDLC graph is explicit, acyclic and safe to load."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from app.orchestration.graph import GraphValidationError
from app.orchestration.graph_loader import load_graph, parse_graph

GRAPH_PATH = Path(__file__).resolve().parents[1] / "config" / "default_sdlc.yaml"


def document() -> dict:
    return yaml.safe_load(GRAPH_PATH.read_text(encoding="utf-8"))


def parse_document(data: dict, *, blocking_ambiguity: bool = False):
    return parse_graph(yaml.safe_dump(data), blocking_ambiguity=blocking_ambiguity)


def test_default_graph_has_required_fan_out_joins_and_approval_checkpoints() -> None:
    graph = load_graph()
    assert len(graph.stages) == 16
    assert graph.topological_order[0] == "INTAKE"
    assert graph.topological_order[-1] == "COMPLETED"
    assert graph.stage("REQUIREMENT_ANALYSIS").dependencies == ("INTAKE",)
    assert graph.stage("TASK_DECOMPOSITION").dependencies == ("REQUIREMENT_ANALYSIS",)
    assert graph.stage("ARCHITECTURE_DESIGN").dependencies == ("TASK_DECOMPOSITION",)
    assert graph.stage("ARCHITECTURE_APPROVAL").dependencies == ("ARCHITECTURE_DESIGN",)
    for name in ("IMPLEMENTATION", "TEST_DESIGN", "DOCUMENTATION_DRAFT"):
        assert graph.stage(name).dependencies == ("ARCHITECTURE_APPROVAL",)
    assert set(graph.stage("BUILD_VALIDATION").dependencies) == {"IMPLEMENTATION", "TEST_DESIGN"}
    for name in ("UNIT_TEST", "INTEGRATION_TEST", "SECURITY_VALIDATION"):
        assert graph.stage(name).dependencies == ("BUILD_VALIDATION",)
    assert set(graph.stage("DOCUMENTATION_FINALIZATION").dependencies) == {
        "UNIT_TEST",
        "INTEGRATION_TEST",
        "SECURITY_VALIDATION",
        "DOCUMENTATION_DRAFT",
    }
    assert graph.stage("RELEASE_READINESS").dependencies == ("DOCUMENTATION_FINALIZATION",)
    assert graph.stage("RELEASE_READINESS").entry_gate == "release_readiness_prerequisites"
    assert graph.stage("RELEASE_APPROVAL").dependencies == ("RELEASE_READINESS",)
    assert graph.stage("COMPLETED").dependencies == ("RELEASE_APPROVAL",)
    assert graph.stage("ARCHITECTURE_APPROVAL").approval_required
    assert graph.stage("RELEASE_APPROVAL").approval_required
    assert all(
        stage.executor and stage.entry_gate and stage.exit_gate and stage.retry_policy
        for stage in graph.stages
    )


def test_blocking_ambiguity_inserts_clarification_without_cycle() -> None:
    ordinary = load_graph()
    ambiguous = load_graph(blocking_ambiguity=True)
    assert "CLARIFICATION" not in ordinary.topological_order
    assert len(ambiguous.stages) == 17
    assert ambiguous.stage("CLARIFICATION").dependencies == ("REQUIREMENT_ANALYSIS",)
    assert ambiguous.stage("TASK_DECOMPOSITION").dependencies == ("CLARIFICATION",)
    assert ambiguous.topological_order.index("REQUIREMENT_ANALYSIS") < (
        ambiguous.topological_order.index("CLARIFICATION")
    )
    assert ambiguous.topological_order.index("CLARIFICATION") < (
        ambiguous.topological_order.index("TASK_DECOMPOSITION")
    )
    assert ordinary.sha256 != ambiguous.sha256


def test_hash_is_deterministic_for_equivalent_yaml_ordering() -> None:
    original = document()
    reordered = deepcopy(original)
    reordered["stages"].reverse()
    for stage in reordered["stages"]:
        stage["dependencies"].reverse()
    assert parse_document(original).sha256 == parse_document(reordered).sha256
    assert parse_document(original).topological_order == parse_document(reordered).topological_order


def test_unknown_dependency_is_rejected() -> None:
    data = document()
    data["stages"][8]["dependencies"] = ["IMPLEMENTATION", "UNKNOWN_STAGE"]
    with pytest.raises(GraphValidationError, match="Unknown dependency UNKNOWN_STAGE"):
        parse_document(data)


def test_duplicate_stage_name_is_rejected() -> None:
    data = document()
    data["stages"].append(deepcopy(data["stages"][0]))
    with pytest.raises(GraphValidationError, match="Duplicate stage name: INTAKE"):
        parse_document(data)


def test_cycle_is_rejected_before_execution() -> None:
    data = document()
    data["stages"][0]["dependencies"] = ["COMPLETED"]
    with pytest.raises(GraphValidationError, match="Graph cycle"):
        parse_document(data)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("executor", "import:os.system", "Unknown executor"),
        ("entry_gate", "not_registered", "Unknown gate"),
        ("exit_gate", "not_registered", "Unknown gate"),
        ("fallback", "not_registered", "Unknown fallback"),
    ],
)
def test_unknown_registry_identifiers_are_rejected(field: str, value: str, message: str) -> None:
    data = document()
    data["stages"][0][field] = value
    with pytest.raises(GraphValidationError, match=message):
        parse_document(data)


def test_invalid_retry_policy_is_rejected() -> None:
    data = document()
    data["stages"][0]["retry_policy"]["max_attempts"] = 0
    with pytest.raises(GraphValidationError, match="Invalid graph document"):
        parse_document(data)


def test_duplicate_yaml_keys_are_rejected() -> None:
    source = 'version: "1"\nversion: "2"\nstages: []\n'
    with pytest.raises(GraphValidationError, match="Duplicate YAML key: version"):
        parse_graph(source)


def test_unsafe_yaml_tags_are_rejected() -> None:
    source = '!!python/object/apply:os.system ["false"]'
    with pytest.raises(GraphValidationError, match="Invalid graph document"):
        parse_graph(source)


def test_invalid_conditional_insertion_is_rejected_even_without_ambiguity() -> None:
    data = document()
    data["conditional_insertions"][0]["before"] = "DOES_NOT_EXIST"
    with pytest.raises(GraphValidationError, match="Unknown insertion target"):
        parse_document(data)
