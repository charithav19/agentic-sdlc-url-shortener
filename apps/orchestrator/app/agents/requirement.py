"""RequirementAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import RequirementOutput


class RequirementAgent(Specialist[RequirementOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="RequirementAgent",
            instructions=COMMON
            + (
                "Normalize the user's intent into an engineering requirement and measurable "
                "acceptance criteria. Identify ambiguities and ask precise clarifying "
                "questions. Mark blocking_ambiguity when unresolved intent prevents a safe "
                "plan. Make assumptions explicit; do not silently decide requirements. "
            ),
            output_type=RequirementOutput,
            allowed_tools=("read_artifact",),
            max_turns=4,
            timeout_seconds=60,
        )
