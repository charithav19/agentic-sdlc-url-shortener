"""ReleaseReadinessAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import ReleaseReadinessOutput


class ReleaseReadinessAgent(Specialist[ReleaseReadinessOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="ReleaseReadinessAgent",
            instructions=COMMON
            + (
                "Assess the exact supplied candidate and evidence references. Report "
                "unresolved risks and recommend READY_FOR_REVIEW only when evidence supports "
                "review; otherwise NOT_READY. Missing tests or candidate evidence must "
                "prevent a positive recommendation. This is advisory: never grant release "
                "approval, claim deployment, or mark a workflow complete. "
            ),
            output_type=ReleaseReadinessOutput,
            allowed_tools=("read_artifact",),
            max_turns=4,
            timeout_seconds=60,
        )
