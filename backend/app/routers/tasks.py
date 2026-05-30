import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Task, AuditIssue, Project, Organization, User, TaskStatus, TaskSeverity
from app.schemas import TaskCreate, TaskUpdate, TaskOut, TaskBoardColumn
from app.middleware.auth import get_current_user, get_current_org, verify_project_access

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.get("", response_model=List[TaskOut])
async def list_tasks(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
):
    query = select(Task).where(Task.project_id == project.id)
    if status:
        query = query.where(Task.status == status)
    if severity:
        query = query.where(Task.severity == severity)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    query = query.order_by(Task.severity, Task.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    tasks = result.scalars().all()

    enriched = []
    for t in tasks:
        tout = TaskOut.model_validate(t)
        if t.issue_id:
            issue_result = await db.execute(select(AuditIssue).where(AuditIssue.id == t.issue_id))
            issue = issue_result.scalar_one_or_none()
            if issue:
                tout.issue_type = issue.issue_type
        enriched.append(tout)

    return enriched


@router.get("/board", response_model=List[TaskBoardColumn])
async def get_task_board(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Return tasks grouped by status for kanban board."""
    columns = []
    for status in [TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW, TaskStatus.DONE]:
        result = await db.execute(
            select(Task)
            .where(Task.project_id == project.id, Task.status == status)
            .order_by(Task.severity, Task.created_at.desc())
            .limit(50)
        )
        tasks = result.scalars().all()

        enriched = []
        for t in tasks:
            tout = TaskOut.model_validate(t)
            if t.issue_id:
                issue_result = await db.execute(select(AuditIssue).where(AuditIssue.id == t.issue_id))
                issue = issue_result.scalar_one_or_none()
                if issue:
                    tout.issue_type = issue.issue_type
            enriched.append(tout)

        columns.append(TaskBoardColumn(status=status, tasks=enriched, count=len(enriched)))

    return columns


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    data: TaskCreate,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    task = Task(
        project_id=project.id,
        organization_id=org.id,
        title=data.title,
        description=data.description,
        severity=data.severity,
        fix_difficulty=data.fix_difficulty,
        affected_url=data.affected_url,
        due_date=data.due_date,
        assignee_id=data.assignee_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.project_id == project.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.project_id == project.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()


@router.post("/bulk-update", response_model=List[TaskOut])
async def bulk_update_tasks(
    task_ids: List[uuid.UUID],
    data: TaskUpdate,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Bulk update multiple tasks at once (e.g. assign all P1s to a team member)."""
    result = await db.execute(
        select(Task).where(
            Task.id.in_(task_ids),
            Task.project_id == project.id,
        )
    )
    tasks = result.scalars().all()

    updated = []
    for task in tasks:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(task, field, value)
        updated.append(TaskOut.model_validate(task))

    await db.commit()
    return updated
