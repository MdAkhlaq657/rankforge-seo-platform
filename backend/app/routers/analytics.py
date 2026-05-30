import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import (
    Keyword, RankHistory, GSCDataPoint, CannibalizationIssue,
    Project, Organization,
)
from app.middleware.auth import get_current_org, verify_project_access
from app.services.analytics import (
    detect_cannibalization, forecast_keyword_opportunity,
    forecast_traffic_trend, compute_keyword_roi_table,
)
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/analytics", tags=["analytics"])


@router.get("/cannibalization")
async def get_cannibalization(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    refresh: bool = Query(False),
):
    """Detect keyword cannibalization across all tracked keywords."""
    # Load tracked keywords with latest rank
    kw_result = await db.execute(
        select(Keyword).where(
            Keyword.project_id == project.id,
            Keyword.is_tracked == True,
        )
    )
    keywords = kw_result.scalars().all()

    kw_dicts = []
    for kw in keywords:
        rank_result = await db.execute(
            select(RankHistory)
            .where(RankHistory.keyword_id == kw.id)
            .order_by(RankHistory.checked_at.desc())
            .limit(1)
        )
        latest = rank_result.scalar_one_or_none()
        kw_dicts.append({
            "keyword": kw.keyword,
            "cluster_id": kw.cluster_id,
            "current_position": latest.position if latest else None,
            "best_url": latest.url if latest else None,
        })

    issues = detect_cannibalization(kw_dicts)

    if refresh:
        # Persist to DB
        await db.execute(
            __import__("sqlalchemy", fromlist=["delete"]).delete(CannibalizationIssue)
            .where(CannibalizationIssue.project_id == project.id)
        )
        for issue in issues:
            db.add(CannibalizationIssue(
                project_id=project.id,
                organization_id=project.organization_id,
                keyword=issue["keyword"],
                competing_urls=[u["url"] for u in issue["competing_urls"]],
                recommendation=issue["recommendation"],
                severity=issue["severity"],
            ))
        await db.commit()

    return {
        "total_issues": len(issues),
        "high_severity": sum(1 for i in issues if i["severity"] == "high"),
        "issues": issues,
    }


@router.get("/roi-forecast")
async def roi_forecast(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    conversion_rate: float = Query(0.02, ge=0.001, le=1.0),
    order_value: float = Query(50.0, ge=1.0),
):
    """ROI forecast for all tracked keywords based on position improvements."""
    kw_result = await db.execute(
        select(Keyword).where(
            Keyword.project_id == project.id,
            Keyword.is_tracked == True,
            Keyword.search_volume.isnot(None),
        )
    )
    keywords = kw_result.scalars().all()

    kw_dicts = []
    for kw in keywords:
        rank_result = await db.execute(
            select(RankHistory)
            .where(RankHistory.keyword_id == kw.id)
            .order_by(RankHistory.checked_at.desc())
            .limit(1)
        )
        latest = rank_result.scalar_one_or_none()
        kw_dicts.append({
            "keyword": kw.keyword,
            "search_volume": kw.search_volume,
            "current_position": latest.position if latest else None,
        })

    roi_table = compute_keyword_roi_table(kw_dicts, conversion_rate, order_value)
    total_opp = sum(r["opportunity_value"] for r in roi_table if r["opportunity_value"] > 0)

    return {
        "conversion_rate": conversion_rate,
        "order_value": order_value,
        "total_opportunity_value": round(total_opp, 2),
        "keywords": roi_table[:30],
    }


@router.get("/keyword/{keyword_id}/forecast")
async def keyword_forecast(
    keyword_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    conversion_rate: float = Query(0.02),
    order_value: float = Query(50.0),
):
    kw_result = await db.execute(
        select(Keyword).where(
            Keyword.id == keyword_id,
            Keyword.project_id == project.id,
        )
    )
    kw = kw_result.scalar_one_or_none()
    if not kw:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Keyword not found")

    rank_result = await db.execute(
        select(RankHistory)
        .where(RankHistory.keyword_id == keyword_id)
        .order_by(RankHistory.checked_at.desc())
        .limit(1)
    )
    latest = rank_result.scalar_one_or_none()

    return forecast_keyword_opportunity(
        kw.keyword,
        kw.search_volume or 0,
        latest.position if latest else None,
        conversion_rate,
        order_value,
    )


@router.get("/traffic-forecast")
async def traffic_forecast(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    forecast_days: int = Query(90, le=180),
):
    """Forecast organic traffic based on GSC historical data."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    result = await db.execute(
        select(GSCDataPoint).where(
            GSCDataPoint.project_id == project.id,
            GSCDataPoint.date >= cutoff,
        ).order_by(GSCDataPoint.date.asc())
    )
    rows = result.scalars().all()

    if not rows:
        # Use mock GSC data for demo
        from app.services.gsc import _mock_gsc_data
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=90)
        raw = _mock_gsc_data(project.domain, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        from app.services.gsc import aggregate_gsc_by_day
        daily = aggregate_gsc_by_day(raw)
    else:
        # Aggregate by day
        by_date: dict = {}
        for r in rows:
            d = r.date.strftime("%Y-%m-%d")
            if d not in by_date:
                by_date[d] = {"date": d, "clicks": 0, "impressions": 0}
            by_date[d]["clicks"] += r.clicks
            by_date[d]["impressions"] += r.impressions
        daily = sorted(by_date.values(), key=lambda x: x["date"])

    return forecast_traffic_trend(daily, forecast_days=forecast_days)
