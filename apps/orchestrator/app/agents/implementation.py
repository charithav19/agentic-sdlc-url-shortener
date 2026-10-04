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
                "and list risks. Implement the design using authorized write_file/apply_patch "
                "tools. Report only files supported by tool receipts; run allowed validation "
                "commands when granted and report failures honestly. "
            ),
            output_type=ImplementationOutput,
            allowed_tools=(
                "read_artifact",
                "list_files",
                "read_file",
                "search_code",
                "write_file",
                "apply_patch",
                "run_build",
                "run_tests",
            ),
            instruction_version="2",
            max_turns=8,
            timeout_seconds=60,
        )
