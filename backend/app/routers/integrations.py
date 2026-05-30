import uuid
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Integration, GSCDataPoint, Project, Organization
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.services.gsc import get_oauth_url, exchange_code, fetch_gsc_data, aggregate_gsc_by_day
from app.workers.phase2_tasks import sync_gsc
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/integrations", tags=["integrations"])


@router.get("", response_model=List[dict])
async def list_integrations(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(Integration.project_id == project.id)
    )
    integrations = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "provider": i.provider,
            "property_id": i.property_id,
            "is_active": i.is_active,
            "last_synced_at": i.last_synced_at.isoformat() if i.last_synced_at else None,
        }
        for i in integrations
    ]


@router.get("/gsc/oauth-url")
async def get_gsc_oauth_url(
    project: Project = Depends(verify_project_access),
):
    """Get Google OAuth URL for Search Console connection."""
    state = str(project.id)
    url = get_oauth_url(state)
    if not url:
        # Return mock connection info when Google creds not configured
        return {
            "url": None,
            "message": "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env to enable real GSC integration. Mock data will be used.",
            "mock_available": True,
        }
    return {"url": url}


@router.post("/gsc/connect-mock")
async def connect_gsc_mock(
    body: dict,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Connect GSC with mock data (for development without real OAuth)."""
    property_id = body.get("property_id", f"sc-domain:{project.domain}")

    existing = await db.execute(
        select(Integration).where(
            Integration.project_id == project.id,
            Integration.provider == "gsc",
        )
    )
    integration = existing.scalar_one_or_none()

    if not integration:
        integration = Integration(
            project_id=project.id,
            organization_id=org.id,
            provider="gsc",
            property_id=property_id,
            is_active=True,
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)

    # Trigger sync
    sync_gsc.apply_async(args=[str(project.id), str(integration.id)])

    return {
        "id": str(integration.id),
        "provider": "gsc",
        "property_id": property_id,
        "status": "syncing",
    }


@router.delete("/{integration_id}", status_code=204)
async def disconnect_integration(
    integration_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.project_id == project.id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404)
    await db.delete(integration)
    await db.commit()


@router.post("/{integration_id}/sync")
async def trigger_sync(
    integration_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
):
    """Manually trigger a GSC data sync."""
    task = sync_gsc.apply_async(args=[str(project.id), str(integration_id)])
    return {"task_id": task.id, "status": "queued"}


# ── GSC data endpoints ────────────────────────────────────────────────────────

@router.get("/gsc/performance")
async def gsc_performance(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    days: int = Query(90, le=365),
):
    """Get aggregated GSC performance over time (for charts)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(GSCDataPoint).where(
            GSCDataPoint.project_id == project.id,
            GSCDataPoint.date >= cutoff,
        ).order_by(GSCDataPoint.date.asc())
    )
    rows = result.scalars().all()

    if not rows:
        # Auto-generate mock if no data
        from app.services.gsc import _mock_gsc_data
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        mock_rows = _mock_gsc_data(
            project.domain,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
        return aggregate_gsc_by_day(mock_rows)

    row_dicts = [
        {
            "date": r.date.strftime("%Y-%m-%d"),
            "clicks": r.clicks,
            "impressions": r.impressions,
            "ctr": r.ctr or 0,
            "position": r.position or 0,
        }
        for r in rows
    ]
    return aggregate_gsc_by_day(row_dicts)


@router.get("/gsc/top-queries")
async def gsc_top_queries(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, le=90),
    limit: int = Query(20, le=100),
):
    """Top queries by clicks."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(GSCDataPoint).where(
            GSCDataPoint.project_id == project.id,
            GSCDataPoint.date >= cutoff,
            GSCDataPoint.query.isnot(None),
        )
    )
    rows = result.scalars().all()

    if not rows:
        from app.services.gsc import _mock_gsc_data
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        rows_raw = _mock_gsc_data(project.domain, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        agg: dict = {}
        for r in rows_raw:
            q = r.get("query", "")
            if q not in agg:
                agg[q] = {"query": q, "clicks": 0, "impressions": 0, "position_sum": 0, "count": 0}
            agg[q]["clicks"] += r["clicks"]
            agg[q]["impressions"] += r["impressions"]
            agg[q]["position_sum"] += r.get("position", 0)
            agg[q]["count"] += 1
        result_list = []
        for v in agg.values():
            avg_pos = round(v["position_sum"] / v["count"], 1) if v["count"] else 0
            ctr = round(v["clicks"] / v["impressions"] * 100, 2) if v["impressions"] > 0 else 0
            result_list.append({"query": v["query"], "clicks": v["clicks"], "impressions": v["impressions"], "ctr": ctr, "position": avg_pos})
        result_list.sort(key=lambda x: x["clicks"], reverse=True)
        return result_list[:limit]

    agg: dict = {}
    for r in rows:
        q = r.query or ""
        if q not in agg:
            agg[q] = {"query": q, "clicks": 0, "impressions": 0, "pos_sum": 0, "count": 0}
        agg[q]["clicks"] += r.clicks
        agg[q]["impressions"] += r.impressions
        agg[q]["pos_sum"] += r.position or 0
        agg[q]["count"] += 1

    out = []
    for v in agg.values():
        avg_pos = round(v["pos_sum"] / v["count"], 1) if v["count"] else 0
        ctr = round(v["clicks"] / v["impressions"] * 100, 2) if v["impressions"] > 0 else 0
        out.append({"query": v["query"], "clicks": v["clicks"], "impressions": v["impressions"], "ctr": ctr, "position": avg_pos})
    out.sort(key=lambda x: x["clicks"], reverse=True)
    return out[:limit]
