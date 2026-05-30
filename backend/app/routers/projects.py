import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Project, Crawl, Task, Organization, User, CrawlStatus, TaskStatus
from app.schemas import ProjectCreate, ProjectUpdate, ProjectOut
from app.middleware.auth import get_current_user, get_current_org, verify_project_access

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.organization_id == org.id, Project.is_active == True)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    # Enrich with latest crawl info
    enriched = []
    for p in projects:
        crawl_result = await db.execute(
            select(Crawl)
            .where(Crawl.project_id == p.id)
            .order_by(Crawl.created_at.desc())
            .limit(1)
        )
        latest_crawl = crawl_result.scalar_one_or_none()

        issue_count_result = await db.execute(
            select(func.count(Task.id))
            .where(Task.project_id == p.id, Task.status == TaskStatus.OPEN)
        )
        open_issues = issue_count_result.scalar_one()

        pout = ProjectOut.model_validate(p)
        if latest_crawl:
            pout.last_crawl_at = latest_crawl.created_at
            pout.last_crawl_status = latest_crawl.status.value
            pout.total_pages = latest_crawl.pages_crawled
        pout.open_issues = open_issues
        enriched.append(pout)

    return enriched


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    data: ProjectCreate,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        organization_id=org.id,
        name=data.name,
        domain=data.domain,
        crawl_scope=data.crawl_scope,
        crawl_frequency=data.crawl_frequency,
        respect_robots_txt=data.respect_robots_txt,
        max_pages=data.max_pages,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    crawl_result = await db.execute(
        select(Crawl)
        .where(Crawl.project_id == project.id)
        .order_by(Crawl.created_at.desc())
        .limit(1)
    )
    latest_crawl = crawl_result.scalar_one_or_none()
    issue_result = await db.execute(
        select(func.count(Task.id))
        .where(Task.project_id == project.id, Task.status == TaskStatus.OPEN)
    )
    pout = ProjectOut.model_validate(project)
    if latest_crawl:
        pout.last_crawl_at = latest_crawl.created_at
        pout.last_crawl_status = latest_crawl.status.value
        pout.total_pages = latest_crawl.pages_crawled
    pout.open_issues = issue_result.scalar_one()
    return pout


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    data: ProjectUpdate,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    project.is_active = False
    await db.commit()
