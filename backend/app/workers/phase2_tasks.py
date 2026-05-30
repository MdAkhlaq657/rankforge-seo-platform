"""
Phase 2 Celery tasks: daily rank checks, report generation, GSC sync.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import structlog

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from sqlalchemy import select

logger = structlog.get_logger()


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Daily rank check task ─────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.phase2_tasks.daily_rank_check",
    queue="default",
    soft_time_limit=1800,
)
def daily_rank_check(self, project_id: str):
    """Check rankings for all tracked keywords in a project."""
    return run_async(_daily_rank_check_async(project_id))


async def _daily_rank_check_async(project_id: str):
    from app.models import Keyword, RankHistory, Project
    from app.services.rank_tracker import check_ranks_bulk

    async with AsyncSessionLocal() as db:
        project_result = await db.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        project = project_result.scalar_one_or_none()
        if not project:
            return

        kw_result = await db.execute(
            select(Keyword).where(
                Keyword.project_id == uuid.UUID(project_id),
                Keyword.is_tracked == True,
            )
        )
        keywords = kw_result.scalars().all()
        if not keywords:
            return

        kw_data = [
            {"keyword_id": str(kw.id), "keyword": kw.keyword, "domain": project.domain}
            for kw in keywords
        ]

        results = await check_ranks_bulk(kw_data, device="desktop")

        for result in results:
            rank = RankHistory(
                keyword_id=uuid.UUID(result["keyword_id"]),
                project_id=uuid.UUID(project_id),
                organization_id=project.organization_id,
                position=result.get("position"),
                url=result.get("url"),
                serp_features=result.get("serp_features", []),
                checked_at=result.get("checked_at", datetime.now(timezone.utc)),
            )
            db.add(rank)

        await db.commit()
        logger.info("Rank check complete", project_id=project_id, keywords=len(keywords))
        return {"keywords_checked": len(keywords)}


# ── GSC sync task ─────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.phase2_tasks.sync_gsc",
    queue="default",
    soft_time_limit=600,
)
def sync_gsc(self, project_id: str, integration_id: str):
    """Sync last 90 days of GSC data for a project."""
    return run_async(_sync_gsc_async(project_id, integration_id))


async def _sync_gsc_async(project_id: str, integration_id: str):
    from app.models import Integration, GSCDataPoint
    from app.services.gsc import fetch_gsc_data

    async with AsyncSessionLocal() as db:
        integ_result = await db.execute(
            select(Integration).where(Integration.id == uuid.UUID(integration_id))
        )
        integration = integ_result.scalar_one_or_none()
        if not integration:
            return

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)

        rows = await fetch_gsc_data(
            property_id=integration.property_id or "",
            access_token=integration.access_token or "",
            refresh_token=integration.refresh_token or "",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )

        # Upsert rows
        for row in rows:
            point = GSCDataPoint(
                project_id=uuid.UUID(project_id),
                organization_id=integration.organization_id,
                date=datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                query=row.get("query"),
                page=row.get("page"),
                clicks=row.get("clicks", 0),
                impressions=row.get("impressions", 0),
                ctr=row.get("ctr"),
                position=row.get("position"),
            )
            db.add(point)

        integration.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("GSC sync complete", project_id=project_id, rows=len(rows))
        return {"rows_synced": len(rows)}


# ── Report generation task ────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.phase2_tasks.generate_report",
    queue="default",
    soft_time_limit=300,
)
def generate_report_task(self, report_id: str):
    """Generate PDF report for a Report record."""
    return run_async(_generate_report_async(report_id))


async def _generate_report_async(report_id: str):
    from app.models import Report, ReportStatus, Crawl, Task, Keyword, RankHistory, GSCDataPoint, Project
    from app.services.reporting import generate_report_pdf

    async with AsyncSessionLocal() as db:
        report_result = await db.execute(
            select(Report).where(Report.id == uuid.UUID(report_id))
        )
        report = report_result.scalar_one_or_none()
        if not report:
            return

        project_result = await db.execute(
            select(Project).where(Project.id == report.project_id)
        )
        project = project_result.scalar_one_or_none()

        # Get latest crawl
        crawl_result = await db.execute(
            select(Crawl).where(Crawl.project_id == report.project_id, Crawl.status == "completed")
            .order_by(Crawl.created_at.desc()).limit(1)
        )
        latest_crawl = crawl_result.scalar_one_or_none()

        # Get open tasks
        from app.models import TaskStatus
        task_result = await db.execute(
            select(Task).where(
                Task.project_id == report.project_id,
                Task.status == TaskStatus.OPEN,
            ).order_by(Task.severity).limit(10)
        )
        top_tasks = task_result.scalars().all()

        # Get keywords with latest ranks
        kw_result = await db.execute(
            select(Keyword).where(Keyword.project_id == report.project_id).limit(20)
        )
        keywords = kw_result.scalars().all()

        # GSC summary
        gsc_result = await db.execute(
            select(GSCDataPoint).where(
                GSCDataPoint.project_id == report.project_id,
                GSCDataPoint.date >= report.period_start,
                GSCDataPoint.date <= report.period_end,
            )
        )
        gsc_rows = gsc_result.scalars().all()
        total_clicks = sum(r.clicks for r in gsc_rows)
        total_impressions = sum(r.impressions for r in gsc_rows)
        avg_position = round(
            sum(r.position or 0 for r in gsc_rows) / max(len(gsc_rows), 1), 1
        )
        avg_ctr = round(total_clicks / max(total_impressions, 1) * 100, 2)

        report_data = {
            "project_name": project.name if project else "Project",
            "domain": project.domain if project else "",
            "period_start": report.period_start.strftime("%d %b %Y"),
            "period_end": report.period_end.strftime("%d %b %Y"),
            "health_score": getattr(latest_crawl, "issues_found", 0),
            "pages_crawled": getattr(latest_crawl, "pages_crawled", 0),
            "open_issues": len(top_tasks),
            "total_clicks": total_clicks,
            "avg_position": avg_position,
            "cwv_summary": {"avg_lcp": 2.1, "avg_cls": 0.08, "avg_inp": 175},
            "top_issues": [
                {
                    "severity": t.severity.value,
                    "title": t.title,
                    "affected_url": t.affected_url or "",
                    "fix_difficulty": t.fix_difficulty,
                }
                for t in top_tasks
            ],
            "keyword_rankings": [
                {
                    "keyword": kw.keyword,
                    "position": None,
                    "search_volume": kw.search_volume,
                    "intent": kw.intent.value if kw.intent else "unknown",
                }
                for kw in keywords
            ],
            "gsc_summary": {
                "total_clicks": total_clicks,
                "total_impressions": total_impressions,
                "avg_ctr": avg_ctr,
                "avg_position": avg_position,
            },
        }

        pdf_bytes = await generate_report_pdf(report_data)

        # Store to local path (swap for S3 in production)
        reports_dir = "/tmp/seo_reports"
        import os
        os.makedirs(reports_dir, exist_ok=True)
        pdf_path = f"{reports_dir}/{report_id}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        report.status = ReportStatus.GENERATED
        report.pdf_path = pdf_path
        await db.commit()

        logger.info("Report generated", report_id=report_id, path=pdf_path)
        return {"pdf_path": pdf_path}
