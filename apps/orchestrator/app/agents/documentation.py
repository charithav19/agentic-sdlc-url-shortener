"""DocumentationAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import DocumentationOutput


class DocumentationAgent(Specialist[DocumentationOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="DocumentationAgent",
            instructions=COMMON
            + (
                "Produce documentation content for the current supplied candidate: API "
                "changes, run and test instructions, and limitations. Keep proposed commands "
                "separate from observed results. Reconcile supplied requirement, "
                "implementation and validation evidence; disclose gaps. "
            ),
            output_type=DocumentationOutput,
            allowed_tools=("read_artifact", "list_files", "read_file", "write_file", "apply_patch"),
            instruction_version="2",
            max_turns=6,
            timeout_seconds=60,
        )
