"""HTTP adapter for persisted workflow creation, status, and graph views."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agents.errors import AgentConfigurationError
from app.orchestration.workflow_runtime import WorkflowRuntime
from app.orchestration.workflows import CreateWorkflow, GraphView, WorkflowView

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def get_workflow_runtime(request: Request) -> WorkflowRuntime:
    return request.app.state.workflow_runtime


def schedule_workflow(request: Request, workflow_id: uuid.UUID) -> None:
    runtime = getattr(request.app.state, "workflow_runtime", None)
    if runtime is not None:
        runtime.schedule(workflow_id)


@router.post("", response_model=WorkflowView, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: CreateWorkflow,
    request: Request,
    runtime: Annotated[WorkflowRuntime, Depends(get_workflow_runtime)],
) -> WorkflowView:
    try:
        runtime.validate_provider(body.provider_mode)
        workflow_id = await runtime.service.create(body, trace_id=uuid.UUID(request.state.trace_id))
    except AgentConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    result = await runtime.service.status(workflow_id)
    runtime.schedule(workflow_id)
    return result


@router.get("/{workflow_id}", response_model=WorkflowView)
async def workflow_status(
    workflow_id: uuid.UUID,
    runtime: Annotated[WorkflowRuntime, Depends(get_workflow_runtime)],
) -> WorkflowView:
    try:
        return await runtime.service.status(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow was not found") from None
    except ValueError:
        raise HTTPException(status_code=409, detail="Persisted workflow graph is invalid") from None


@router.get("/{workflow_id}/graph", response_model=GraphView)
async def workflow_graph(
    workflow_id: uuid.UUID,
    runtime: Annotated[WorkflowRuntime, Depends(get_workflow_runtime)],
) -> GraphView:
    try:
        return await runtime.service.graph(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow was not found") from None
    except ValueError:
        raise HTTPException(status_code=409, detail="Persisted workflow graph is invalid") from None
