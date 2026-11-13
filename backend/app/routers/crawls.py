import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Crawl, CrawledPage, AuditIssue, Project, Organization, User, CrawlStatus
from app.schemas import CrawlOut, CrawlSummary, PageOut, IssueOut
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.workers.crawl_tasks import run_crawl

router = APIRouter(prefix="/projects/{project_id}/crawls", tags=["crawls"])


@router.post("", response_model=CrawlOut, status_code=201)
async def start_crawl(
    project: Project = Depends(verify_project_access),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    # Check no crawl is already running
    result = await db.execute(
        select(Crawl).where(
            Crawl.project_id == project.id,
            Crawl.status == CrawlStatus.RUNNING
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A crawl is already running for this project")

    crawl = Crawl(
        project_id=project.id,
        organization_id=org.id,
        status=CrawlStatus.PENDING,
    )
    db.add(crawl)
    await db.commit()
    await db.refresh(crawl)

    # Dispatch Celery task
    try:
        task = run_crawl.apply_async(
            args=[str(crawl.id), str(project.id), str(org.id)],
            queue="crawls",
        )
    except Exception as exc:
        # Do not leave an orphaned PENDING row when Redis/broker dispatch fails.
        crawl.status = CrawlStatus.FAILED
        crawl.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="The crawl could not be queued. Please check that the worker and Redis services are running, then retry.",
        ) from exc

    crawl.celery_task_id = task.id
    await db.commit()

    return CrawlOut.model_validate(crawl)


@router.get("", response_model=List[CrawlOut])
async def list_crawls(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, le=50),
):
    result = await db.execute(
        select(Crawl)
        .where(Crawl.project_id == project.id)
        .order_by(Crawl.created_at.desc())
        .limit(limit)
    )
    return [CrawlOut.model_validate(c) for c in result.scalars().all()]


@router.get("/{crawl_id}", response_model=CrawlSummary)
async def get_crawl_summary(
    crawl_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Crawl).where(Crawl.id == crawl_id, Crawl.project_id == project.id)
    )
    crawl = result.scalar_one_or_none()
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")

    # Status code breakdown
    sc_result = await db.execute(
        select(CrawledPage.status_code, func.count(CrawledPage.id))
        .where(CrawledPage.crawl_id == crawl.id)
        .group_by(CrawledPage.status_code)
    )
    status_breakdown = {}
    for row in sc_result:
        code = str(row[0]) if row[0] else "unknown"
        bucket = f"{code[0]}xx" if len(code) == 3 else code
        status_breakdown[bucket] = status_breakdown.get(bucket, 0) + row[1]

    # Issue breakdown by type
    issue_result = await db.execute(
        select(AuditIssue.issue_type, func.count(AuditIssue.id))
        .where(AuditIssue.crawl_id == crawl.id)
        .group_by(AuditIssue.issue_type)
    )
    issue_breakdown = {str(r[0].value): r[1] for r in issue_result}

    # CWV summary
    cwv_result = await db.execute(
        select(
            func.avg(CrawledPage.lcp_mobile),
            func.avg(CrawledPage.cls_mobile),
            func.avg(CrawledPage.inp_mobile),
            func.avg(CrawledPage.performance_score),
        ).where(CrawledPage.crawl_id == crawl.id)
    )
    cwv_row = cwv_result.one()
    cwv_summary = {
        "avg_lcp": round(float(cwv_row[0] or 0), 2),
        "avg_cls": round(float(cwv_row[1] or 0), 3),
        "avg_inp": int(cwv_row[2] or 0),
        "avg_score": int(cwv_row[3] or 0),
    }

    # Health score (0-100)
    total_pages = crawl.pages_crawled or 1
    issues_ratio = min(crawl.issues_found / (total_pages * 3), 1)
    health_score = max(0, int((1 - issues_ratio) * 100))

    return CrawlSummary(
        crawl=CrawlOut.model_validate(crawl),
        status_code_breakdown=status_breakdown,
        issue_breakdown=issue_breakdown,
        cwv_summary=cwv_summary,
        score=health_score,
    )


@router.get("/{crawl_id}/pages", response_model=List[PageOut])
async def list_pages(
    crawl_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    status_code: Optional[int] = Query(None),
    has_issues: Optional[bool] = Query(None),
):
    query = select(CrawledPage).where(
        CrawledPage.crawl_id == crawl_id,
        CrawledPage.project_id == project.id,
    )
    if status_code:
        query = query.where(CrawledPage.status_code == status_code)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    pages = result.scalars().all()

    enriched = []
    for page in pages:
        issue_count = await db.execute(
            select(func.count(AuditIssue.id)).where(AuditIssue.page_id == page.id)
        )
        pout = PageOut.model_validate(page)
        pout.issues_count = issue_count.scalar_one()
        enriched.append(pout)

    if has_issues is True:
        enriched = [p for p in enriched if p.issues_count > 0]

    return enriched


@router.get("/{crawl_id}/issues", response_model=List[IssueOut])
async def list_issues(
    crawl_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    severity: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
):
    query = select(AuditIssue).where(
        AuditIssue.crawl_id == crawl_id,
        AuditIssue.project_id == project.id,
    )
    if severity:
        query = query.where(AuditIssue.severity == severity)
    query = query.order_by(AuditIssue.severity).offset(offset).limit(limit)

    result = await db.execute(query)
    return [IssueOut.model_validate(i) for i in result.scalars().all()]
