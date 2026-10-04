"""Bindings for specialist executor names already declared by the SDLC graph."""

from types import MappingProxyType

from app.agents.architecture import ArchitectureAgent
from app.agents.documentation import DocumentationAgent
from app.agents.implementation import ImplementationAgent
from app.agents.planning import PlanningAgent
from app.agents.release_readiness import ReleaseReadinessAgent
from app.agents.requirement import RequirementAgent
from app.agents.security import SecurityAgent
from app.agents.testing import TestAgent

SPECIALISTS = MappingProxyType(
    {
        "requirements_specialist": RequirementAgent(),
        "task_decomposition_specialist": PlanningAgent(),
        "architecture_specialist": ArchitectureAgent(),
        "implementation_specialist": ImplementationAgent(),
        "test_design_specialist": TestAgent(),
        "security_specialist": SecurityAgent(),
        "documentation_specialist": DocumentationAgent(),
        "release_specialist": ReleaseReadinessAgent(),
    }
)
