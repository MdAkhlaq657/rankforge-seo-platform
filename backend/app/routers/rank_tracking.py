import uuid
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Keyword, RankHistory, Project, Organization
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.workers.phase2_tasks import daily_rank_check

router = APIRouter(prefix="/projects/{project_id}/ranks", tags=["rank-tracking"])


@router.get("", response_model=List[dict])
async def get_rank_summary(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, le=90),
):
    """Get current rankings with delta for all tracked keywords."""
    kw_result = await db.execute(
        select(Keyword).where(
            Keyword.project_id == project.id,
            Keyword.is_tracked == True,
        )
    )
    keywords = kw_result.scalars().all()

    cutoff_now = datetime.now(timezone.utc)
    cutoff_prev = cutoff_now - timedelta(days=7)
    cutoff_days = cutoff_now - timedelta(days=days)

    results = []
    for kw in keywords:
        # Latest position
        latest_result = await db.execute(
            select(RankHistory)
            .where(RankHistory.keyword_id == kw.id)
            .order_by(RankHistory.checked_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()

        # Position 7 days ago for delta
        prev_result = await db.execute(
            select(RankHistory)
            .where(
                RankHistory.keyword_id == kw.id,
                RankHistory.checked_at <= cutoff_prev,
            )
            .order_by(RankHistory.checked_at.desc())
            .limit(1)
        )
        prev = prev_result.scalar_one_or_none()

        # Sparkline (last N days)
        sparkline_result = await db.execute(
            select(RankHistory)
            .where(
                RankHistory.keyword_id == kw.id,
                RankHistory.checked_at >= cutoff_days,
            )
            .order_by(RankHistory.checked_at.asc())
        )
        sparkline_records = sparkline_result.scalars().all()
        sparkline = [r.position for r in sparkline_records]

        current_pos = latest.position if latest else None
        prev_pos = prev.position if prev else None
        delta = None
        if current_pos is not None and prev_pos is not None:
            delta = prev_pos - current_pos  # positive = improved

        results.append({
            "keyword_id": str(kw.id),
            "keyword": kw.keyword,
            "search_volume": kw.search_volume,
            "intent": kw.intent.value if kw.intent else "unknown",
            "current_position": current_pos,
            "previous_position": prev_pos,
            "delta": delta,
            "best_url": latest.url if latest else None,
            "serp_features": latest.serp_features if latest else [],
            "sparkline": sparkline,
            "last_checked": latest.checked_at.isoformat() if latest else None,
        })

    # Sort: ranking keywords first (by position), then not ranking
    results.sort(key=lambda x: (x["current_position"] is None, x["current_position"] or 999))
    return results


@router.get("/history/{keyword_id}", response_model=List[dict])
async def get_rank_history(
    keyword_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    days: int = Query(90, le=365),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(RankHistory)
        .where(
            RankHistory.keyword_id == keyword_id,
            RankHistory.project_id == project.id,
            RankHistory.checked_at >= cutoff,
        )
        .order_by(RankHistory.checked_at.asc())
    )
    records = result.scalars().all()
    return [
        {
            "date": r.checked_at.strftime("%Y-%m-%d"),
            "position": r.position,
            "url": r.url,
            "serp_features": r.serp_features,
        }
        for r in records
    ]


@router.post("/check-now")
async def trigger_rank_check(
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
):
    """Manually trigger an immediate rank check for this project."""
    task = daily_rank_check.apply_async(args=[str(project.id)])
    return {"task_id": task.id, "status": "queued"}


@router.get("/stats")
async def rank_stats(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Overview stats: top 3, positions 4-10, 11-20, 21-50, 50+, not ranking."""
    kw_result = await db.execute(
        select(Keyword).where(
            Keyword.project_id == project.id,
            Keyword.is_tracked == True,
        )
    )
    keywords = kw_result.scalars().all()

    buckets = {"top_3": 0, "4_10": 0, "11_20": 0, "21_50": 0, "51_100": 0, "not_ranking": 0}

    for kw in keywords:
        rank_result = await db.execute(
            select(RankHistory)
            .where(RankHistory.keyword_id == kw.id)
            .order_by(RankHistory.checked_at.desc())
            .limit(1)
        )
        latest = rank_result.scalar_one_or_none()
        pos = latest.position if latest else None

        if pos is None: buckets["not_ranking"] += 1
        elif pos <= 3: buckets["top_3"] += 1
        elif pos <= 10: buckets["4_10"] += 1
        elif pos <= 20: buckets["11_20"] += 1
        elif pos <= 50: buckets["21_50"] += 1
        else: buckets["51_100"] += 1

    return {
        "total_tracked": len(keywords),
        "buckets": buckets,
    }
