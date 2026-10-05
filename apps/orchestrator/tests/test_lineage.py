"""Typed multi-level artifact lineage traversal."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.lineage import ArtifactLineageService, LineageRelationship
from app.artifacts.schemas import ArtifactInput, ArtifactRef
from app.orchestration.contracts import ScenarioType
from app.persistence.models import AuditEvent
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


async def store(
    persistence: WorkflowPersistenceService,
    workflow_id,
    logical_name: str,
    artifact_type: str,
    *,
    revision: int = 1,
) -> ArtifactRef:
    return await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name=logical_name,
            artifact_type=artifact_type,
            schema_version="1",
            content={"name": logical_name, "revision": revision},
            requirement_ids=["REQ-1"],
            component_ids=["COMP-URL"],
        ),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_level_branching_parents_children_and_descendants(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="lineage-branching",
    )
    requirement = await store(persistence, workflow_id, "requirement", "requirement")
    plan = await store(persistence, workflow_id, "plan", "plan")
    architecture = await store(persistence, workflow_id, "architecture", "architecture")
    code = await store(persistence, workflow_id, "code", "implementation")
    test_plan = await store(persistence, workflow_id, "test-plan", "test_plan")
    documentation = await store(persistence, workflow_id, "documentation", "documentation")

    edge_ids = []
    for parent, child, relationship in (
        (requirement, plan, LineageRelationship.DERIVED_FROM),
        (plan, architecture, LineageRelationship.DERIVED_FROM),
        (architecture, code, LineageRelationship.IMPLEMENTS),
        (architecture, test_plan, LineageRelationship.VALIDATES),
        (architecture, documentation, LineageRelationship.DOCUMENTS),
    ):
        edge_ids.append(
            await persistence.link_artifacts(
                workflow_id,
                parent_artifact_id=parent.id,
                child_artifact_id=child.id,
                relationship=relationship.value,
                requirement_ids=["REQ-1"],
                component_ids=["COMP-URL"],
            )
        )

    async with UnitOfWork.open(phase6_factory) as unit:
        lineage = ArtifactLineageService(unit.session)
        code_parents = await lineage.parents(workflow_id, code.id)
        architecture_children = await lineage.children(workflow_id, architecture.id)
        descendants = await lineage.transitive_descendants(workflow_id, requirement.id)

        assert len(code_parents) == 1
        assert code_parents[0].relationship is LineageRelationship.IMPLEMENTS
        assert code_parents[0].parent.id == architecture.id
        assert code_parents[0].parent.version == architecture.version
        assert code_parents[0].child.sha256 == code.sha256
        assert code_parents[0].requirement_ids == ("REQ-1",)
        assert code_parents[0].component_ids == ("COMP-URL",)

        assert {
            connection.child.logical_name: connection.relationship
            for connection in architecture_children
        } == {
            "code": LineageRelationship.IMPLEMENTS,
            "documentation": LineageRelationship.DOCUMENTS,
            "test-plan": LineageRelationship.VALIDATES,
        }
        assert [(item.artifact.logical_name, item.depth) for item in descendants] == [
            ("plan", 1),
            ("architecture", 2),
            ("code", 3),
            ("documentation", 3),
            ("test-plan", 3),
        ]

        repeated = await lineage.add_relationship(
            workflow_id,
            parent_artifact_id=requirement.id,
            child_artifact_id=plan.id,
            relationship=LineageRelationship.DERIVED_FROM,
        )
        assert repeated.id == edge_ids[0]

        events = (
            await unit.session.scalars(
                select(AuditEvent).where(
                    AuditEvent.workflow_id == workflow_id,
                    AuditEvent.event_type == "ARTIFACT_LINEAGE_CREATED",
                )
            )
        ).all()
        assert len(events) == 5
        assert events[0].payload["edge_id"] == str(edge_ids[0])
        assert events[0].payload["relationship"] == "DERIVED_FROM"

        with pytest.raises(ValueError, match="cycle"):
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=code.id,
                child_artifact_id=requirement.id,
                relationship=LineageRelationship.DERIVED_FROM,
            )
        with pytest.raises(ValueError, match="must differ"):
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=requirement.id,
                child_artifact_id=requirement.id,
                relationship=LineageRelationship.DERIVED_FROM,
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_supersedes_requires_newer_exact_version_and_relationships_are_typed(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.AMBIGUOUS,
        provider_mode="fake",
        workspace_ref="lineage-versions",
    )
    version_one = await store(persistence, workflow_id, "requirement", "requirement", revision=1)
    version_two = await store(persistence, workflow_id, "requirement", "requirement", revision=2)
    assert (version_one.version, version_two.version) == (1, 2)

    await persistence.link_artifacts(
        workflow_id,
        parent_artifact_id=version_one.id,
        child_artifact_id=version_two.id,
        relationship=LineageRelationship.SUPERSEDES.value,
    )
    async with UnitOfWork.open(phase6_factory) as unit:
        lineage = ArtifactLineageService(unit.session)
        children = await lineage.children(workflow_id, version_one.id)
        parents = await lineage.parents(workflow_id, version_two.id)
        assert children[0].relationship is LineageRelationship.SUPERSEDES
        assert children[0].child.version == 2
        assert parents[0].parent.version == 1

        with pytest.raises(ValueError, match="newer version"):
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=version_two.id,
                child_artifact_id=version_one.id,
                relationship=LineageRelationship.SUPERSEDES,
            )
        with pytest.raises(ValueError, match="Unknown lineage relationship"):
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=version_one.id,
                child_artifact_id=version_two.id,
                relationship="UNKNOWN",
            )
