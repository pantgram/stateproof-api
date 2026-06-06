import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Workflow
from src.schemas.workflow import WorkflowCreate, WorkflowUpdate


async def create_workflow(
    db: AsyncSession, organization_id: uuid.UUID, data: WorkflowCreate
) -> Workflow:
    wf = Workflow(
        organization_id=organization_id,
        name=data.name,
        description=data.description,
        url=data.url,
        meta=data.meta,
    )
    db.add(wf)
    await db.flush()
    await db.refresh(wf)
    return wf


async def get_workflow(
    db: AsyncSession, organization_id: uuid.UUID, workflow_id: uuid.UUID
) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.organization_id == organization_id
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_by_id(
    db: AsyncSession, workflow_id: uuid.UUID
) -> Workflow | None:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    return result.scalar_one_or_none()


async def get_workflow_by_id_for_update(
    db: AsyncSession, workflow_id: uuid.UUID
) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def list_workflows(
    db: AsyncSession, organization_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> tuple[list[Workflow], int]:
    cond = Workflow.organization_id == organization_id
    total = (
        await db.execute(select(func.count()).select_from(Workflow).where(cond))
    ).scalar_one()

    result = await db.execute(
        select(Workflow)
        .where(cond)
        .order_by(Workflow.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def update_workflow(
    db: AsyncSession,
    organization_id: uuid.UUID,
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
) -> Workflow | None:
    wf = await get_workflow(db, organization_id, workflow_id)
    if wf is None:
        return None
    if data.name is not None:
        wf.name = data.name
    if data.description is not None:
        wf.description = data.description
    if data.url is not None:
        wf.url = data.url
    if data.meta is not None:
        wf.meta = data.meta
    await db.flush()
    await db.refresh(wf)
    return wf
