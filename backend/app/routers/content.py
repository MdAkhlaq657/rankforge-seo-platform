import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import ContentPiece, Keyword, PAAQuestion, Project, Organization, ContentStatus
from app.middleware.auth import get_current_user, get_current_org, verify_project_access
from app.services.content_writer import (
    scrape_competitor_content, generate_brief, generate_article_stream,
    generate_article_full,
)
from app.services.keywords import get_serp_data
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/content", tags=["content"])


class ContentCreateRequest(BaseModel):
    target_keyword: str
    title: str


class ContentUpdate(BaseModel):
    title: str | None = None
    article_markdown: str | None = None
    status: ContentStatus | None = None


@router.get("", response_model=List[dict])
async def list_content(
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContentPiece)
        .where(ContentPiece.project_id == project.id)
        .order_by(ContentPiece.created_at.desc())
    )
    pieces = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "target_keyword": p.target_keyword,
            "status": p.status.value,
            "word_count": p.word_count,
            "seo_score": p.seo_score,
            "created_at": p.created_at.isoformat(),
        }
        for p in pieces
    ]


@router.post("", response_model=dict, status_code=201)
async def create_content(
    data: ContentCreateRequest,
    project: Project = Depends(verify_project_access),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Create a new content piece and immediately generate a brief."""
    # Get SERP data + competitor URLs
    serp = await get_serp_data(data.target_keyword)
    competitor_urls = [r["url"] for r in serp.get("organic_results", [])[:5]]
    paa_questions = [q["question"] for q in serp.get("paa", [])[:10]]
    serp_features = serp.get("serp_features", [])

    # Scrape competitor content
    competitor_data = await scrape_competitor_content(competitor_urls)

    # Generate brief
    brief = await generate_brief(
        keyword=data.target_keyword,
        paa_questions=paa_questions,
        competitor_data=competitor_data,
        serp_features=serp_features,
    )

    piece = ContentPiece(
        project_id=project.id,
        organization_id=org.id,
        title=data.title,
        target_keyword=data.target_keyword,
        status=ContentStatus.DRAFT,
        brief=brief,
        competitor_urls=competitor_urls,
    )
    db.add(piece)
    await db.commit()
    await db.refresh(piece)

    return {
        "id": str(piece.id),
        "title": piece.title,
        "target_keyword": piece.target_keyword,
        "status": piece.status.value,
        "brief": piece.brief,
        "competitor_urls": piece.competitor_urls,
    }


@router.get("/{content_id}", response_model=dict)
async def get_content(
    content_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContentPiece).where(
            ContentPiece.id == content_id,
            ContentPiece.project_id == project.id,
        )
    )
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")
    return {
        "id": str(piece.id),
        "title": piece.title,
        "target_keyword": piece.target_keyword,
        "status": piece.status.value,
        "brief": piece.brief,
        "article_markdown": piece.article_markdown,
        "word_count": piece.word_count,
        "seo_score": piece.seo_score,
        "competitor_urls": piece.competitor_urls,
        "created_at": piece.created_at.isoformat(),
        "updated_at": piece.updated_at.isoformat(),
    }


@router.post("/{content_id}/generate-article")
async def generate_article(
    content_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
    stream: bool = False,
):
    """Generate the full article for a content piece."""
    result = await db.execute(
        select(ContentPiece).where(
            ContentPiece.id == content_id,
            ContentPiece.project_id == project.id,
        )
    )
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")

    competitor_data = await scrape_competitor_content(piece.competitor_urls or [])

    if stream:
        async def event_stream():
            full_text = ""
            async for chunk in generate_article_stream(piece.target_keyword, piece.brief, competitor_data):
                full_text += chunk
                yield f"data: {chunk}\n\n"
            # Save after stream completes
            yield f"data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming
    article = await generate_article_full(piece.target_keyword, piece.brief, competitor_data)
    piece.article_markdown = article
    piece.word_count = len(article.split())
    piece.status = ContentStatus.GENERATED
    await db.commit()

    return {
        "article_markdown": article,
        "word_count": piece.word_count,
        "status": piece.status.value,
    }


@router.patch("/{content_id}", response_model=dict)
async def update_content(
    content_id: uuid.UUID,
    data: ContentUpdate,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContentPiece).where(
            ContentPiece.id == content_id,
            ContentPiece.project_id == project.id,
        )
    )
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")

    if data.title is not None: piece.title = data.title
    if data.article_markdown is not None:
        piece.article_markdown = data.article_markdown
        piece.word_count = len(data.article_markdown.split())
    if data.status is not None: piece.status = data.status

    await db.commit()
    return {"id": str(piece.id), "status": piece.status.value, "word_count": piece.word_count}


@router.delete("/{content_id}", status_code=204)
async def delete_content(
    content_id: uuid.UUID,
    project: Project = Depends(verify_project_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContentPiece).where(
            ContentPiece.id == content_id,
            ContentPiece.project_id == project.id,
        )
    )
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(piece)
    await db.commit()
