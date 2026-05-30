import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Competitor, CompetitorEvent, Project, Organization
from app.middleware.auth import get_current_org, verify_project_access
from app.services.competitor_intel import run_competitor_check, get_brand_mentions
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/competitors", tags=["competitors"])


class CompetitorCreate(BaseModel):
    domain: str
    name: str | None = None


@router.get("")
async def list_competitors(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competitor).where(
            Competitor.project_id == project.id,
            Competitor.is_active == True,
        ).order_by(Competitor.created_at)
    )
    competitors = result.scalars().all()
    enriched = []
    for c in competitors:
        event_result = await db.execute(
            select(CompetitorEvent)
            .where(CompetitorEvent.competitor_id == c.id, CompetitorEvent.is_read == False)
        )
        unread = len(event_result.scalars().all())
        enriched.append({
            "id": str(c.id),
            "domain": c.domain,
            "name": c.name or c.domain,
            "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
            "unread_events": unread,
        })
    return enriched


@router.post("", status_code=201)
async def add_competitor(
    data: CompetitorCreate,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Competitor).where(
            Competitor.project_id == project.id,
            Competitor.domain == data.domain.lower().strip(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Competitor already tracked")

    competitor = Competitor(
        project_id=project.id,
        organization_id=org.id,
        domain=data.domain.lower().strip(),
        name=data.name,
    )
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return {"id": str(competitor.id), "domain": competitor.domain}


@router.delete("/{competitor_id}", status_code=204)
async def remove_competitor(
    competitor_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id,
            Competitor.project_id == project.id,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404)
    c.is_active = False
    await db.commit()


@router.post("/{competitor_id}/check")
async def check_competitor(
    competitor_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a competitor intelligence check."""
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id,
            Competitor.project_id == project.id,
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404)

    events = await run_competitor_check(competitor.domain, project.domain)

    for ev in events:
        db.add(CompetitorEvent(
            competitor_id=competitor.id,
            project_id=project.id,
            organization_id=org.id,
            event_type=ev["event_type"],
            title=ev["title"],
            description=ev.get("description"),
            url=ev.get("url"),
            metadata=ev.get("metadata", {}),
        ))

    from datetime import datetime, timezone
    competitor.last_checked_at = datetime.now(timezone.utc)
    await db.commit()

    return {"events_found": len(events), "events": events}


@router.get("/{competitor_id}/events")
async def get_events(
    competitor_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CompetitorEvent)
        .where(CompetitorEvent.competitor_id == competitor_id)
        .order_by(CompetitorEvent.detected_at.desc())
        .limit(50)
    )
    events = result.scalars().all()

    # Mark as read
    for e in events:
        e.is_read = True
    await db.commit()

    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description,
            "url": e.url,
            "detected_at": e.detected_at.isoformat(),
        }
        for e in events
    ]


@router.get("/brand-mentions")
async def brand_mentions(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    brand = project.domain.split(".")[0]
    mentions = await get_brand_mentions(brand, project.domain)
    unlinked = [m for m in mentions if not m["is_linked"]]
    return {
        "total": len(mentions),
        "linked": len(mentions) - len(unlinked),
        "unlinked": len(unlinked),
        "outreach_opportunities": len(unlinked),
        "mentions": mentions,
    }
