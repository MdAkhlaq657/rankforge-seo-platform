import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db
from app.models import Keyword, PAAQuestion, Project, Organization, User, RankHistory, KeywordIntent
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.services.keywords import get_keyword_data, get_related_keywords, get_serp_data
from app.services.onpage import cluster_keywords
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/keywords", tags=["keywords"])


class KeywordAddRequest(BaseModel):
    keywords: List[str]
    track: bool = False


class KeywordUpdate(BaseModel):
    is_tracked: Optional[bool] = None
    target_url: Optional[str] = None


@router.get("", response_model=List[dict])
async def list_keywords(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    tracked_only: bool = Query(False),
    intent: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
):
    query = select(Keyword).where(Keyword.project_id == project.id)
    if tracked_only:
        query = query.where(Keyword.is_tracked == True)
    if intent:
        query = query.where(Keyword.intent == intent)
    query = query.order_by(Keyword.search_volume.desc().nulls_last()).offset(offset).limit(limit)
    result = await db.execute(query)
    keywords = result.scalars().all()

    # Enrich with latest rank
    enriched = []
    for kw in keywords:
        latest_rank = None
        if kw.is_tracked:
            rank_result = await db.execute(
                select(RankHistory)
                .where(RankHistory.keyword_id == kw.id)
                .order_by(RankHistory.checked_at.desc())
                .limit(1)
            )
            rh = rank_result.scalar_one_or_none()
            latest_rank = rh.position if rh else None

        enriched.append({
            "id": str(kw.id),
            "keyword": kw.keyword,
            "search_volume": kw.search_volume,
            "keyword_difficulty": kw.keyword_difficulty,
            "cpc": kw.cpc,
            "intent": kw.intent.value if kw.intent else "unknown",
            "serp_features": kw.serp_features,
            "is_tracked": kw.is_tracked,
            "target_url": kw.target_url,
            "cluster_id": kw.cluster_id,
            "current_position": latest_rank,
            "created_at": kw.created_at.isoformat(),
        })
    return enriched


@router.post("/research", response_model=List[dict])
async def research_keywords(
    data: KeywordAddRequest,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Fetch keyword data and optionally save to project."""
    if len(data.keywords) > 50:
        raise HTTPException(status_code=400, detail="Max 50 keywords per request")

    kw_data_list = await get_keyword_data(data.keywords)

    if data.track:
        for kw_data in kw_data_list:
            existing = await db.execute(
                select(Keyword).where(
                    Keyword.project_id == project.id,
                    Keyword.keyword == kw_data["keyword"],
                )
            )
            if existing.scalar_one_or_none():
                continue
            kw = Keyword(
                project_id=project.id,
                organization_id=org.id,
                keyword=kw_data["keyword"],
                search_volume=kw_data.get("search_volume"),
                keyword_difficulty=kw_data.get("keyword_difficulty"),
                cpc=kw_data.get("cpc"),
                competition=kw_data.get("competition"),
                intent=kw_data.get("intent", "unknown"),
                serp_features=kw_data.get("serp_features", []),
                is_tracked=True,
            )
            db.add(kw)
        await db.commit()

    return kw_data_list


@router.post("/suggest", response_model=List[dict])
async def suggest_keywords(
    body: dict,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Get related keyword suggestions for a seed keyword."""
    seed = body.get("seed_keyword", "")
    if not seed:
        raise HTTPException(status_code=400, detail="seed_keyword required")
    return await get_related_keywords(seed, count=25)


@router.get("/{keyword_id}/paa", response_model=List[dict])
async def get_paa(
    keyword_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PAAQuestion).where(PAAQuestion.keyword_id == keyword_id)
    )
    questions = result.scalars().all()
    if not questions:
        # Fetch and cache
        kw_result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
        kw = kw_result.scalar_one_or_none()
        if not kw:
            raise HTTPException(status_code=404, detail="Keyword not found")
        serp = await get_serp_data(kw.keyword)
        paa_data = serp.get("paa", [])
        for q_data in paa_data:
            q = PAAQuestion(
                keyword_id=keyword_id,
                project_id=project.id,
                question=q_data["question"],
                answer_snippet=q_data.get("answer_snippet"),
                depth=q_data.get("depth", 0),
            )
            db.add(q)
        await db.commit()
        result = await db.execute(select(PAAQuestion).where(PAAQuestion.keyword_id == keyword_id))
        questions = result.scalars().all()

    return [
        {
            "id": str(q.id),
            "question": q.question,
            "answer_snippet": q.answer_snippet,
            "depth": q.depth,
        }
        for q in questions
    ]


@router.post("/cluster")
async def cluster_project_keywords(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    """Cluster all project keywords by semantic similarity."""
    result = await db.execute(
        select(Keyword).where(Keyword.project_id == project.id)
    )
    keywords = result.scalars().all()
    if len(keywords) < 3:
        raise HTTPException(status_code=400, detail="Need at least 3 keywords to cluster")

    kw_texts = [kw.keyword for kw in keywords]
    clusters = cluster_keywords(kw_texts, n_clusters=min(8, len(kw_texts) // 2))

    for kw in keywords:
        cluster_id = clusters.get(kw.keyword, "cluster_0")
        kw.cluster_id = cluster_id

    await db.commit()
    return {"clustered": len(keywords), "clusters": len(set(clusters.values()))}


@router.patch("/{keyword_id}")
async def update_keyword(
    keyword_id: uuid.UUID,
    data: KeywordUpdate,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.project_id == project.id)
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    if data.is_tracked is not None:
        kw.is_tracked = data.is_tracked
    if data.target_url is not None:
        kw.target_url = data.target_url
    await db.commit()
    return {"id": str(kw.id), "is_tracked": kw.is_tracked}


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(
    keyword_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.project_id == project.id)
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(kw)
    await db.commit()
