import uuid
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Report, ReportStatus, Project, Organization
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.workers.phase2_tasks import generate_report_task
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


class ReportCreateRequest(BaseModel):
    title: str | None = None
    period_months: int = 1  # 1 = last month, 3 = last quarter


@router.get("", response_model=List[dict])
async def list_reports(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report)
        .where(Report.project_id == project.id)
        .order_by(Report.created_at.desc())
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "period_start": r.period_start.strftime("%d %b %Y"),
            "period_end": r.period_end.strftime("%d %b %Y"),
            "status": r.status.value,
            "has_pdf": bool(r.pdf_path),
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.post("", response_model=dict, status_code=201)
async def create_report(
    data: ReportCreateRequest,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Queue a new PDF report for generation."""
    now = datetime.now(timezone.utc)
    period_end = now.replace(day=1) - timedelta(days=1)  # last day of previous month
    period_start = (period_end.replace(day=1) - timedelta(days=30 * (data.period_months - 1))).replace(day=1)

    title = data.title or f"{project.name} — SEO Report {period_end.strftime('%B %Y')}"

    report = Report(
        project_id=project.id,
        organization_id=org.id,
        title=title,
        period_start=period_start,
        period_end=period_end,
        status=ReportStatus.PENDING,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Queue generation
    generate_report_task.apply_async(args=[str(report.id)])

    return {
        "id": str(report.id),
        "title": report.title,
        "status": report.status.value,
        "message": "Report is being generated and will be ready shortly.",
    }


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Download the generated PDF."""
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.project_id == project.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != ReportStatus.GENERATED:
        raise HTTPException(status_code=425, detail="Report not ready yet")
    if not report.pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")

    import os
    if not os.path.exists(report.pdf_path):
        raise HTTPException(status_code=404, detail="PDF file missing from storage")

    return FileResponse(
        report.pdf_path,
        media_type="application/pdf",
        filename=f"{report.title.replace(' ', '_')}.pdf",
    )


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.project_id == project.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404)
    await db.delete(report)
    await db.commit()
