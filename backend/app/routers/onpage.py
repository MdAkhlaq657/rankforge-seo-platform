import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import OnPageAnalysis, CrawledPage, Project, Organization
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.services.onpage import analyze_page
from app.services.keywords import get_serp_data
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/onpage", tags=["on-page"])


class OnPageRequest(BaseModel):
    url: str
    target_keyword: str
    use_top_competitors: bool = True


@router.post("/analyze", response_model=dict)
async def run_analysis(
    data: OnPageRequest,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Run full NLP on-page analysis for a URL + keyword."""
    competitor_urls = []
    if data.use_top_competitors:
        serp = await get_serp_data(data.target_keyword)
        competitor_urls = [
            r["url"] for r in serp.get("organic_results", [])[:5]
            if data.url not in r.get("url", "")
        ]

    result = await analyze_page(
        url=data.url,
        target_keyword=data.target_keyword,
        competitor_urls=competitor_urls,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    analysis = OnPageAnalysis(
        project_id=project.id,
        organization_id=org.id,
        url=data.url,
        target_keyword=data.target_keyword,
        content_score=result.get("content_score"),
        word_count=result.get("word_count"),
        avg_competitor_words=result.get("avg_competitor_words"),
        keyword_density=result.get("keyword_density"),
        missing_entities=result.get("missing_entities", []),
        present_entities=result.get("present_entities", []),
        suggested_keywords=result.get("suggested_keywords", []),
        competitor_urls=competitor_urls,
        raw_analysis=result,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return {
        "id": str(analysis.id),
        **result,
        "competitor_urls": competitor_urls,
    }


@router.get("", response_model=List[dict])
async def list_analyses(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnPageAnalysis)
        .where(OnPageAnalysis.project_id == project.id)
        .order_by(OnPageAnalysis.created_at.desc())
        .limit(50)
    )
    analyses = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "url": a.url,
            "target_keyword": a.target_keyword,
            "content_score": a.content_score,
            "word_count": a.word_count,
            "keyword_density": a.keyword_density,
            "missing_entities_count": len(a.missing_entities or []),
            "created_at": a.created_at.isoformat(),
        }
        for a in analyses
    ]


@router.get("/{analysis_id}", response_model=dict)
async def get_analysis(
    analysis_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnPageAnalysis).where(
            OnPageAnalysis.id == analysis_id,
            OnPageAnalysis.project_id == project.id,
        )
    )
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "id": str(a.id),
        "url": a.url,
        "target_keyword": a.target_keyword,
        "content_score": a.content_score,
        "word_count": a.word_count,
        "avg_competitor_words": a.avg_competitor_words,
        "keyword_density": a.keyword_density,
        "missing_entities": a.missing_entities,
        "present_entities": a.present_entities,
        "suggested_keywords": a.suggested_keywords,
        "competitor_urls": a.competitor_urls,
        "raw_analysis": a.raw_analysis,
        "created_at": a.created_at.isoformat(),
    }
