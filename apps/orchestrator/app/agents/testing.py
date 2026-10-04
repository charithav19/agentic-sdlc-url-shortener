"""TestAgent definition; no orchestration authority."""

from app.agents.contracts import Specialist
from app.agents.instructions import COMMON
from app.agents.output_schemas import TestOutput


class TestAgent(Specialist[TestOutput]):
    def __init__(self) -> None:
        super().__init__(
            name="TestAgent",
            instructions=COMMON
            + (
                "Design unit and integration tests mapped to acceptance criteria, including "
                "failure paths and regressions. List generated tests and execution evidence "
                "only when supplied. Identify uncovered risks. A test plan is not a passing "
                "test result; report missing execution evidence. "
            ),
            output_type=TestOutput,
            allowed_tools=("read_artifact", "list_files", "read_file", "search_code"),
            max_turns=6,
            timeout_seconds=60,
        )
