"""ArchitectureAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import ArchitectureOutput


class ArchitectureAgent(Specialist[ArchitectureOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="ArchitectureAgent",
            instructions=COMMON
            + (
                "Design components and interfaces for the supplied requirement and plan. "
                "Explain API and data changes, security considerations, failure modes, "
                "tradeoffs and testing implications. In brownfield work ground decisions in "
                "supplied code. Flag missing architectural context. "
            ),
            output_type=ArchitectureOutput,
            allowed_tools=("read_artifact", "list_files", "read_file", "search_code"),
            max_turns=6,
            timeout_seconds=60,
        )
