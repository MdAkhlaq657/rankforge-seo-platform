import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import Backlink, BacklinkProfile, Project, Organization, BacklinkStatus
from app.middleware.auth import get_current_org, verify_project_access
from app.services.backlinks import (
    fetch_backlinks, fetch_competitor_backlinks, get_profile,
    compute_gap, get_disavow_candidates, generate_disavow_txt,
    anchor_text_distribution,
)
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/backlinks", tags=["backlinks"])


@router.post("/fetch")
async def fetch_and_store(
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(150, le=500),
):
    """Fetch fresh backlinks for this project's domain and store them."""
    # Clear existing for this project
    await db.execute(delete(Backlink).where(Backlink.project_id == project.id))

    raw = await fetch_backlinks(project.domain, limit=limit)
    for item in raw:
        bl = Backlink(
            project_id=project.id,
            organization_id=org.id,
            source_url=item["source_url"],
            source_domain=item["source_domain"],
            target_url=item["target_url"],
            anchor_text=item.get("anchor_text"),
            is_dofollow=item.get("is_dofollow", True),
            domain_rating=item.get("domain_rating"),
            spam_score=item.get("spam_score"),
            toxicity_score=item.get("toxicity_score", 0),
            status=item.get("status", "live"),
        )
        db.add(bl)

    # Upsert profile
    profile_data = get_profile(project.domain)
    existing = await db.execute(
        select(BacklinkProfile).where(BacklinkProfile.project_id == project.id)
    )
    profile = existing.scalar_one_or_none()
    if profile:
        profile.total_backlinks = len(raw)
        profile.total_referring_domains = len({b["source_domain"] for b in raw})
        profile.domain_rating = profile_data["domain_rating"]
        profile.spam_score = profile_data["spam_score"]
    else:
        db.add(BacklinkProfile(
            project_id=project.id,
            organization_id=org.id,
            domain=project.domain,
            total_backlinks=len(raw),
            total_referring_domains=len({b["source_domain"] for b in raw}),
            domain_rating=profile_data["domain_rating"],
            spam_score=profile_data["spam_score"],
        ))
    await db.commit()
    return {"fetched": len(raw), "domain": project.domain}


@router.get("")
async def list_backlinks(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    dofollow_only: bool = Query(False),
    min_dr: Optional[int] = Query(None),
    toxic_only: bool = Query(False),
    offset: int = Query(0),
    limit: int = Query(100, le=500),
):
    query = select(Backlink).where(Backlink.project_id == project.id)
    if status:
        query = query.where(Backlink.status == status)
    if dofollow_only:
        query = query.where(Backlink.is_dofollow == True)
    if min_dr is not None:
        query = query.where(Backlink.domain_rating >= min_dr)
    if toxic_only:
        query = query.where(Backlink.toxicity_score >= 60)
    query = query.order_by(Backlink.domain_rating.desc().nulls_last()).offset(offset).limit(limit)
    result = await db.execute(query)
    backlinks = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "source_domain": b.source_domain,
            "source_url": b.source_url,
            "target_url": b.target_url,
            "anchor_text": b.anchor_text,
            "is_dofollow": b.is_dofollow,
            "domain_rating": b.domain_rating,
            "spam_score": b.spam_score,
            "toxicity_score": b.toxicity_score,
            "status": b.status.value if b.status else "live",
        }
        for b in backlinks
    ]


@router.get("/profile")
async def get_backlink_profile(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BacklinkProfile).where(BacklinkProfile.project_id == project.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return get_profile(project.domain)
    return {
        "domain": profile.domain,
        "total_backlinks": profile.total_backlinks,
        "total_referring_domains": profile.total_referring_domains,
        "domain_rating": profile.domain_rating,
        "spam_score": profile.spam_score,
        "fetched_at": profile.fetched_at.isoformat(),
    }


@router.get("/anchor-distribution")
async def anchor_distribution(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Backlink).where(Backlink.project_id == project.id)
    )
    backlinks = result.scalars().all()
    bl_dicts = [{"anchor_text": b.anchor_text} for b in backlinks]
    return anchor_text_distribution(bl_dicts)


@router.get("/disavow-candidates")
async def disavow_candidates(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    threshold: int = Query(60, ge=0, le=100),
):
    result = await db.execute(
        select(Backlink).where(
            Backlink.project_id == project.id,
            Backlink.toxicity_score >= threshold,
        ).order_by(Backlink.toxicity_score.desc())
    )
    candidates = result.scalars().all()
    return [
        {
            "source_domain": b.source_domain,
            "source_url": b.source_url,
            "toxicity_score": b.toxicity_score,
            "spam_score": b.spam_score,
            "domain_rating": b.domain_rating,
        }
        for b in candidates
    ]


@router.get("/disavow.txt", response_class=PlainTextResponse)
async def download_disavow(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Backlink).where(
            Backlink.project_id == project.id,
            Backlink.toxicity_score >= 60,
        )
    )
    candidates = result.scalars().all()
    bl_dicts = [{"source_domain": b.source_domain, "source_url": b.source_url} for b in candidates]
    return generate_disavow_txt(bl_dicts)


@router.post("/gap-analysis")
async def gap_analysis(
    body: dict,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Compare backlink profiles against a competitor domain."""
    competitor_domain = body.get("competitor_domain", "")
    if not competitor_domain:
        raise HTTPException(status_code=400, detail="competitor_domain required")

    own_result = await db.execute(
        select(Backlink).where(Backlink.project_id == project.id)
    )
    own = own_result.scalars().all()
    own_dicts = [{"source_domain": b.source_domain} for b in own]

    comp_dicts = await fetch_competitor_backlinks(competitor_domain, limit=100)
    gap_domains = compute_gap(own_dicts, comp_dicts)

    return {
        "own_referring_domains": len({b["source_domain"] for b in own_dicts}),
        "competitor_referring_domains": len({b["source_domain"] for b in comp_dicts}),
        "gap_domains": gap_domains[:50],
        "gap_count": len(gap_domains),
        "competitor_domain": competitor_domain,
    }
