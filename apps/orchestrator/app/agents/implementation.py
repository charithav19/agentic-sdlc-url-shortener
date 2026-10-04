"""ImplementationAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import ImplementationOutput


class ImplementationAgent(Specialist[ImplementationOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="ImplementationAgent",
            instructions=COMMON
            + (
                "Analyze the approved design and supplied candidate/change evidence. Describe "
                "created and changed files only when supplied evidence shows those effects. "
                "Request the needed unit and integration tests, summarize engineering work "
                "and list risks. Snapshot tools cannot edit files: with no change evidence "
                "report empty file lists and explain the limitation; never invent an "
                "implementation. "
            ),
            output_type=ImplementationOutput,
            allowed_tools=("read_artifact", "list_files", "read_file", "search_code"),
            max_turns=8,
            timeout_seconds=60,
        )
