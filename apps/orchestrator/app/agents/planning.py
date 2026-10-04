"""PlanningAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import PlanningOutput


class PlanningAgent(Specialist[PlanningOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="PlanningAgent",
            instructions=COMMON
            + (
                "Decompose the analyzed requirement into actionable tasks with stable IDs. "
                "List dependency edges, independent parallelizable groups, affected "
                "components and risks. Do not treat unresolved blocking ambiguity as "
                "resolved. Avoid cycles and unsupported scope. "
            ),
            output_type=PlanningOutput,
            allowed_tools=("read_artifact", "list_files", "read_file", "search_code"),
            max_turns=6,
            timeout_seconds=60,
        )
