import asyncio
import uuid
from datetime import datetime, timezone
from collections import Counter, deque
from typing import Optional
import httpx
import structlog

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import (
    Crawl, CrawledPage, AuditIssue, Task, Project,
    CrawlStatus, TaskStatus
)
from app.services.crawler import crawl_page, detect_issues
import tldextract

logger = structlog.get_logger()


# SQLAlchemy's async connection pool is bound to the event loop that created
# each connection. Celery's prefork worker process can execute many tasks, so
# creating and closing a loop for every task can make a pooled asyncpg
# connection get reused from a different loop on the next task.
_worker_loop = None


def run_async(coro):
    """Run async work on one persistent event loop per Celery worker process."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        # Created lazily inside the worker child process, not in the parent
        # process before Celery forks its worker pool.
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(coro)


@celery_app.task(
    bind=True,
    name="app.workers.crawl_tasks.run_crawl",
    queue="crawls",
    max_retries=2,
    soft_time_limit=3600,
)
def run_crawl(self, crawl_id: str, project_id: str, org_id: str):
    """Main crawl task. Runs BFS crawl and records failures at every stage."""
    try:
        return run_async(_run_crawl_async(crawl_id, project_id, org_id, self))
    except Exception as exc:
        # The crawl can fail before _run_crawl_async reaches its own crawl
        # loop (for example, while loading the project or marking it running).
        # Use a fresh session so a failed/aborted transaction cannot leave the
        # database row permanently pending.
        logger.exception("Crawl task crashed", crawl_id=crawl_id, error=str(exc))
        try:
            run_async(_mark_crawl_failed(crawl_id))
        except Exception as status_exc:
            logger.exception(
                "Could not persist failed crawl status",
                crawl_id=crawl_id,
                error=str(status_exc),
            )
        raise


async def _mark_crawl_failed(crawl_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Crawl).where(Crawl.id == uuid.UUID(crawl_id))
        )
        crawl = result.scalar_one_or_none()
        if crawl and crawl.status not in (CrawlStatus.COMPLETED, CrawlStatus.CANCELLED):
            crawl.status = CrawlStatus.FAILED
            crawl.completed_at = datetime.now(timezone.utc)
            await db.commit()


async def _run_crawl_async(crawl_id: str, project_id: str, org_id: str, task):
    async with AsyncSessionLocal() as db:
        # Load crawl + project
        result = await db.execute(
            select(Crawl).where(Crawl.id == uuid.UUID(crawl_id))
        )
        crawl = result.scalar_one_or_none()
        if not crawl:
            logger.error("Crawl not found", crawl_id=crawl_id)
            return

        result = await db.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        project = result.scalar_one_or_none()
        if not project:
            return

        # Mark as running
        crawl.status = CrawlStatus.RUNNING
        crawl.started_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info("Crawl started", crawl_id=crawl_id, domain=project.domain)

        base_domain = tldextract.extract(project.domain).registered_domain
        start_url = f"https://{project.domain}"
        max_pages = project.max_pages

        visited = set()
        queue = deque([(start_url, 0)])  # (url, depth)
        all_page_data = []

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": project.custom_user_agent or "SEOPlatformBot/1.0 (+https://seoplatform.io/bot)"},
                follow_redirects=True,
                verify=False,
            ) as client:
                # BFS crawl
                while queue and len(visited) < max_pages:
                    url, depth = queue.popleft()

                    # Normalize URL
                    clean_url = url.split("#")[0].rstrip("/")
                    if clean_url in visited:
                        continue
                    visited.add(clean_url)

                    # Update progress
                    task.update_state(
                        state="PROGRESS",
                        meta={"pages_crawled": len(visited), "current_url": clean_url},
                    )

                    page_data = await crawl_page(client, clean_url, base_domain, depth)
                    page_data["url"] = clean_url
                    all_page_data.append(page_data)

                    # Persist page to DB
                    page_id = await _save_page(db, page_data, crawl, project)

                    # Enqueue discovered URLs
                    if depth < 3:
                        for discovered_url in page_data.get("discovered_urls", []):
                            clean = discovered_url.split("#")[0].rstrip("/")
                            if clean not in visited:
                                queue.append((clean, depth + 1))

                    # Rate limiting
                    await asyncio.sleep(0.3)

            # Count normalized titles across all crawled pages before auditing.
            title_counts = Counter(
                page["title"].strip().casefold()
                for page in all_page_data
                if page.get("title") and page["title"].strip()
            )

            # Run audit pass with complete title counts.
            total_issues = 0
            for page_data in all_page_data:
                issues = detect_issues(page_data, title_counts)
                for issue_def in issues:
                    await _save_issue_and_task(db, issue_def, page_data, crawl, project, db)
                    total_issues += 1

            # Mark complete
            crawl.status = CrawlStatus.COMPLETED
            crawl.completed_at = datetime.now(timezone.utc)
            crawl.pages_crawled = len(visited)
            crawl.pages_total = len(visited)
            crawl.issues_found = total_issues
            await db.commit()

            logger.info("Crawl completed", crawl_id=crawl_id, pages=len(visited), issues=total_issues)
            return {"pages_crawled": len(visited), "issues_found": total_issues}

        except Exception as e:
            logger.error("Crawl failed", crawl_id=crawl_id, error=str(e))
            crawl.status = CrawlStatus.FAILED
            crawl.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise


async def _save_page(db, page_data: dict, crawl: Crawl, project: Project) -> uuid.UUID:
    page = CrawledPage(
        crawl_id=crawl.id,
        project_id=project.id,
        organization_id=project.organization_id,
        url=page_data.get("url", ""),
        status_code=page_data.get("status_code"),
        redirect_url=page_data.get("redirect_url"),
        redirect_chain=page_data.get("redirect_chain", []),
        title=page_data.get("title"),
        title_length=page_data.get("title_length", 0),
        meta_description=page_data.get("meta_description"),
        meta_description_length=page_data.get("meta_description_length", 0),
        h1=page_data.get("h1"),
        h1_count=page_data.get("h1_count", 0),
        h2_count=page_data.get("h2_count", 0),
        canonical_url=page_data.get("canonical_url"),
        is_indexable=page_data.get("is_indexable", True),
        has_noindex=page_data.get("has_noindex", False),
        word_count=page_data.get("word_count", 0),
        internal_links=page_data.get("internal_links", 0),
        external_links=page_data.get("external_links", 0),
        has_schema=page_data.get("has_schema", False),
        schema_types=page_data.get("schema_types", []),
        page_depth=page_data.get("page_depth", 0),
        lcp_mobile=page_data.get("lcp_mobile"),
        cls_mobile=page_data.get("cls_mobile"),
        inp_mobile=page_data.get("inp_mobile"),
        lcp_desktop=page_data.get("lcp_desktop"),
        cls_desktop=page_data.get("cls_desktop"),
        inp_desktop=page_data.get("inp_desktop"),
        performance_score=page_data.get("performance_score"),
    )
    db.add(page)
    await db.flush()
    return page.id


async def _save_issue_and_task(db, issue_def: dict, page_data: dict, crawl: Crawl, project: Project, _db):
    # Find the page record
    result = await db.execute(
        select(CrawledPage).where(
            CrawledPage.crawl_id == crawl.id,
            CrawledPage.url == page_data.get("url", "")
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        return

    issue = AuditIssue(
        crawl_id=crawl.id,
        page_id=page.id,
        project_id=project.id,
        organization_id=project.organization_id,
        issue_type=issue_def["issue_type"],
        severity=issue_def["severity"],
        title=issue_def["title"],
        description=issue_def.get("description"),
        recommendation=issue_def.get("recommendation"),
        affected_url=page_data.get("url", ""),
        meta=issue_def.get("meta", {}),
    )
    db.add(issue)
    await db.flush()

    task = Task(
        project_id=project.id,
        organization_id=project.organization_id,
        issue_id=issue.id,
        title=f"{issue_def['title']} — {page_data.get('url', '')[:80]}",
        description=issue_def.get("description"),
        severity=issue_def["severity"],
        status=TaskStatus.OPEN,
        fix_difficulty=issue_def.get("fix_difficulty", "medium"),
        affected_url=page_data.get("url", ""),
    )
    db.add(task)
    await db.flush()
