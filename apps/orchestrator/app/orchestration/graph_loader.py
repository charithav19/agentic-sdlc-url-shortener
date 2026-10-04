"""Load a safe YAML SDLC graph and resolve its conditional clarification branch."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from app.orchestration.graph import (
    GraphValidationError,
    StageDefinition,
    WorkflowGraph,
    build_graph,
)
from app.orchestration.registry import DEFAULT_REGISTRY, GraphRegistry

SOURCE_GRAPH_PATH = Path(__file__).resolve().parents[2] / "config" / "default_sdlc.yaml"
PACKAGED_GRAPH_PATH = Path(__file__).resolve().parents[1] / "resources" / "default_sdlc.yaml"
DEFAULT_GRAPH_PATH = SOURCE_GRAPH_PATH if SOURCE_GRAPH_PATH.is_file() else PACKAGED_GRAPH_PATH


class ConditionalInsertion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    when: Literal["blocking_ambiguity"]
    before: str
    stage: StageDefinition


class GraphDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    stages: tuple[StageDefinition, ...]
    conditional_insertions: tuple[ConditionalInsertion, ...] = ()


class UniqueKeySafeLoader(yaml.SafeLoader):
    """Reject duplicate YAML mapping keys instead of silently replacing values."""


def _construct_unique_mapping(
    loader: UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise GraphValidationError(f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _with_insertions(document: GraphDocument) -> tuple[StageDefinition, ...]:
    stages = list(document.stages)
    for insertion in document.conditional_insertions:
        predecessor_names = insertion.stage.dependencies
        if len(predecessor_names) != 1:
            raise GraphValidationError(
                f"Conditional stage {insertion.stage.name} requires one predecessor"
            )
        predecessor = predecessor_names[0]
        for index, stage in enumerate(stages):
            if stage.name == insertion.before:
                if predecessor not in stage.dependencies:
                    raise GraphValidationError(
                        f"{insertion.before} does not depend on {predecessor}"
                    )
                dependencies = tuple(
                    insertion.stage.name if name == predecessor else name
                    for name in stage.dependencies
                )
                stages[index] = stage.model_copy(update={"dependencies": dependencies})
                stages.append(insertion.stage)
                break
        else:
            raise GraphValidationError(f"Unknown insertion target {insertion.before}")
    return tuple(stages)


def parse_graph(
    source: str,
    *,
    blocking_ambiguity: bool = False,
    registry: GraphRegistry = DEFAULT_REGISTRY,
) -> WorkflowGraph:
    try:
        raw = yaml.load(source, Loader=UniqueKeySafeLoader)
        document = GraphDocument.model_validate(raw)
    except (yaml.YAMLError, ValidationError, TypeError) as error:
        raise GraphValidationError(f"Invalid graph document: {error}") from error
    if not document.version:
        raise GraphValidationError("Graph version is required")

    # Validate both variants even when the caller currently needs only one.
    base = build_graph(document.version, document.stages, registry=registry)
    conditional_stages = _with_insertions(document)
    conditional = build_graph(document.version, conditional_stages, registry=registry)
    return conditional if blocking_ambiguity else base


def load_graph(
    path: Path | str = DEFAULT_GRAPH_PATH,
    *,
    blocking_ambiguity: bool = False,
    registry: GraphRegistry = DEFAULT_REGISTRY,
) -> WorkflowGraph:
    return parse_graph(
        Path(path).read_text(encoding="utf-8"),
        blocking_ambiguity=blocking_ambiguity,
        registry=registry,
    )
