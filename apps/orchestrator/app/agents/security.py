"""SecurityAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import SecurityOutput


class SecurityAgent(Specialist[SecurityOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="SecurityAgent",
            instructions=COMMON
            + (
                "Review supplied design and code for security risks. For each finding provide "
                "severity, rule, evidence, affected files and remediation. Identify blocking "
                "concerns and coverage limitations. Model review is not a vulnerability scan "
                "or security clearance. "
            ),
            output_type=SecurityOutput,
            allowed_tools=("read_artifact", "list_files", "read_file", "search_code"),
            max_turns=6,
            timeout_seconds=60,
        )
