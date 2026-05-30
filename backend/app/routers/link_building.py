import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import LinkProspect, OutreachEmail, Project, Organization, OutreachStatus
from app.middleware.auth import get_current_org, verify_project_access
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/link-building", tags=["link-building"])

PIPELINE_STAGES = [
    OutreachStatus.PROSPECTING, OutreachStatus.QUALIFIED,
    OutreachStatus.CONTACTED, OutreachStatus.FOLLOWED_UP,
    OutreachStatus.NEGOTIATING, OutreachStatus.PLACED, OutreachStatus.DECLINED,
]


class ProspectCreate(BaseModel):
    domain: str
    url: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    domain_rating: int | None = None
    source: str = "manual"
    notes: str | None = None


class ProspectUpdate(BaseModel):
    status: OutreachStatus | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    notes: str | None = None
    domain_rating: int | None = None


class EmailCreate(BaseModel):
    subject: str
    body: str


@router.get("/pipeline")
async def get_pipeline(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Return prospects grouped by pipeline stage."""
    pipeline = []
    for stage in PIPELINE_STAGES:
        result = await db.execute(
            select(LinkProspect).where(
                LinkProspect.project_id == project.id,
                LinkProspect.status == stage,
            ).order_by(LinkProspect.domain_rating.desc().nulls_last())
        )
        prospects = result.scalars().all()
        pipeline.append({
            "stage": stage.value,
            "count": len(prospects),
            "prospects": [
                {
                    "id": str(p.id),
                    "domain": p.domain,
                    "url": p.url,
                    "contact_name": p.contact_name,
                    "contact_email": p.contact_email,
                    "domain_rating": p.domain_rating,
                    "source": p.source,
                    "notes": p.notes,
                    "last_contacted_at": p.last_contacted_at.isoformat() if p.last_contacted_at else None,
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in prospects
            ],
        })
    return pipeline


@router.get("")
async def list_prospects(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    offset: int = Query(0),
    limit: int = Query(100, le=500),
):
    query = select(LinkProspect).where(LinkProspect.project_id == project.id)
    if status:
        query = query.where(LinkProspect.status == status)
    if source:
        query = query.where(LinkProspect.source == source)
    query = query.order_by(LinkProspect.domain_rating.desc().nulls_last()).offset(offset).limit(limit)
    result = await db.execute(query)
    prospects = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "domain": p.domain,
            "url": p.url,
            "contact_name": p.contact_name,
            "contact_email": p.contact_email,
            "domain_rating": p.domain_rating,
            "status": p.status.value,
            "source": p.source,
            "last_contacted_at": p.last_contacted_at.isoformat() if p.last_contacted_at else None,
        }
        for p in prospects
    ]


@router.post("", status_code=201)
async def add_prospect(
    data: ProspectCreate,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    prospect = LinkProspect(
        project_id=project.id,
        organization_id=org.id,
        domain=data.domain.lower().strip(),
        url=data.url,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        domain_rating=data.domain_rating,
        source=data.source,
        notes=data.notes,
    )
    db.add(prospect)
    await db.commit()
    await db.refresh(prospect)
    return {"id": str(prospect.id), "domain": prospect.domain, "status": prospect.status.value}


@router.patch("/{prospect_id}")
async def update_prospect(
    prospect_id: uuid.UUID,
    data: ProspectUpdate,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LinkProspect).where(
            LinkProspect.id == prospect_id,
            LinkProspect.project_id == project.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    await db.commit()
    return {"id": str(p.id), "status": p.status.value}


@router.delete("/{prospect_id}", status_code=204)
async def delete_prospect(
    prospect_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LinkProspect).where(
            LinkProspect.id == prospect_id,
            LinkProspect.project_id == project.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404)
    await db.delete(p)
    await db.commit()


@router.post("/{prospect_id}/emails", status_code=201)
async def send_email(
    prospect_id: uuid.UUID,
    data: EmailCreate,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Log an outreach email (send via SES in production)."""
    result = await db.execute(
        select(LinkProspect).where(
            LinkProspect.id == prospect_id,
            LinkProspect.project_id == project.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404)

    email = OutreachEmail(
        prospect_id=p.id,
        project_id=project.id,
        organization_id=org.id,
        subject=data.subject,
        body=data.body,
        is_sent=True,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(email)

    # Auto-advance status
    if p.status == OutreachStatus.QUALIFIED:
        p.status = OutreachStatus.CONTACTED
    elif p.status == OutreachStatus.CONTACTED:
        p.status = OutreachStatus.FOLLOWED_UP
    p.last_contacted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"id": str(email.id), "sent": True, "prospect_status": p.status.value}


@router.get("/{prospect_id}/emails")
async def get_emails(
    prospect_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutreachEmail)
        .where(OutreachEmail.prospect_id == prospect_id)
        .order_by(OutreachEmail.created_at.desc())
    )
    emails = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "subject": e.subject,
            "body": e.body,
            "is_sent": e.is_sent,
            "is_opened": e.is_opened,
            "sent_at": e.sent_at.isoformat() if e.sent_at else None,
        }
        for e in emails
    ]


@router.post("/import-gap")
async def import_gap_prospects(
    body: dict,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Import competitor backlink gap domains as prospecting leads."""
    gap_domains = body.get("domains", [])
    if not gap_domains:
        raise HTTPException(status_code=400, detail="domains list required")

    added = 0
    for domain in gap_domains[:50]:
        existing = await db.execute(
            select(LinkProspect).where(
                LinkProspect.project_id == project.id,
                LinkProspect.domain == domain,
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(LinkProspect(
            project_id=project.id,
            organization_id=org.id,
            domain=domain,
            source="competitor_gap",
            status=OutreachStatus.PROSPECTING,
        ))
        added += 1

    await db.commit()
    return {"added": added, "total_requested": len(gap_domains)}
