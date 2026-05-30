from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.database import engine, Base
from app.routers import auth, projects, crawls, tasks  # noqa

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="SEO Platform API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(crawls.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# Phase 2 routers
from app.routers import keywords, rank_tracking, onpage, content, integrations, reports  # noqa
app.include_router(keywords.router, prefix="/api/v1")
app.include_router(rank_tracking.router, prefix="/api/v1")
app.include_router(onpage.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")

# Phase 3 routers
from app.routers import backlinks, competitors, link_building, analytics, billing  # noqa
app.include_router(backlinks.router, prefix="/api/v1")
app.include_router(competitors.router, prefix="/api/v1")
app.include_router(link_building.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
