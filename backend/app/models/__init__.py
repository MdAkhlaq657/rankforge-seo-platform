import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, DateTime, Text, Integer, Float,
    ForeignKey, Enum as SAEnum, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    SEO_MANAGER = "seo_manager"
    CONTENT_WRITER = "content_writer"
    CLIENT = "client"


class CrawlStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    RESOLVED = "resolved"


class TaskSeverity(str, enum.Enum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class IssueType(str, enum.Enum):
    BROKEN_LINK = "broken_link"
    REDIRECT_LOOP = "redirect_loop"
    MISSING_TITLE = "missing_title"
    DUPLICATE_TITLE = "duplicate_title"
    MISSING_META = "missing_meta"
    MISSING_H1 = "missing_h1"
    MULTIPLE_H1 = "multiple_h1"
    NOINDEX_KEY_PAGE = "noindex_key_page"
    SLOW_CWV = "slow_cwv"
    MISSING_CANONICAL = "missing_canonical"
    THIN_CONTENT = "thin_content"
    MISSING_SCHEMA = "missing_schema"
    BROKEN_CANONICAL = "broken_canonical"
    DUPLICATE_META = "duplicate_meta"


# ── Users & Orgs ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    memberships: Mapped[list["OrgMembership"]] = relationship("OrgMembership", back_populates="user")
    assigned_tasks: Mapped[list["Task"]] = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="starter")
    crawl_credits: Mapped[int] = mapped_column(Integer, default=5000)
    keyword_credits: Mapped[int] = mapped_column(Integer, default=500)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["OrgMembership"]] = relationship("OrgMembership", back_populates="organization")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="organization")


class OrgMembership(Base):
    __tablename__ = "org_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    role: Mapped[OrgRole] = mapped_column(SAEnum(OrgRole), default=OrgRole.SEO_MANAGER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")


# ── Projects ──────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    # Crawl config
    crawl_scope: Mapped[str] = mapped_column(String(20), default="domain")  # domain | path
    crawl_frequency: Mapped[str] = mapped_column(String(20), default="weekly")
    respect_robots_txt: Mapped[bool] = mapped_column(Boolean, default=True)
    max_pages: Mapped[int] = mapped_column(Integer, default=500)
    custom_user_agent: Mapped[str] = mapped_column(String(255), nullable=True)
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    crawls: Mapped[list["Crawl"]] = relationship("Crawl", back_populates="project", order_by="Crawl.created_at.desc()")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project")


# ── Crawls ────────────────────────────────────────────────────────────────────

class Crawl(Base):
    __tablename__ = "crawls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    status: Mapped[CrawlStatus] = mapped_column(SAEnum(CrawlStatus), default=CrawlStatus.PENDING)
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    # Stats
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    pages_total: Mapped[int] = mapped_column(Integer, nullable=True)
    issues_found: Mapped[int] = mapped_column(Integer, default=0)
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="crawls")
    pages: Mapped[list["CrawledPage"]] = relationship("CrawledPage", back_populates="crawl")


class CrawledPage(Base):
    __tablename__ = "crawled_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("crawls.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=True)
    redirect_url: Mapped[str] = mapped_column(Text, nullable=True)
    redirect_chain: Mapped[list] = mapped_column(JSON, default=list)

    # On-page
    title: Mapped[str] = mapped_column(Text, nullable=True)
    title_length: Mapped[int] = mapped_column(Integer, nullable=True)
    meta_description: Mapped[str] = mapped_column(Text, nullable=True)
    meta_description_length: Mapped[int] = mapped_column(Integer, nullable=True)
    h1: Mapped[str] = mapped_column(Text, nullable=True)
    h1_count: Mapped[int] = mapped_column(Integer, default=0)
    h2_count: Mapped[int] = mapped_column(Integer, default=0)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=True)
    is_indexable: Mapped[bool] = mapped_column(Boolean, default=True)
    has_noindex: Mapped[bool] = mapped_column(Boolean, default=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    internal_links: Mapped[int] = mapped_column(Integer, default=0)
    external_links: Mapped[int] = mapped_column(Integer, default=0)
    has_schema: Mapped[bool] = mapped_column(Boolean, default=False)
    schema_types: Mapped[list] = mapped_column(JSON, default=list)
    page_depth: Mapped[int] = mapped_column(Integer, default=0)

    # Core Web Vitals (from PSI API or mock)
    lcp_mobile: Mapped[float] = mapped_column(Float, nullable=True)
    cls_mobile: Mapped[float] = mapped_column(Float, nullable=True)
    inp_mobile: Mapped[float] = mapped_column(Float, nullable=True)
    lcp_desktop: Mapped[float] = mapped_column(Float, nullable=True)
    cls_desktop: Mapped[float] = mapped_column(Float, nullable=True)
    inp_desktop: Mapped[float] = mapped_column(Float, nullable=True)
    performance_score: Mapped[int] = mapped_column(Integer, nullable=True)

    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    crawl: Mapped["Crawl"] = relationship("Crawl", back_populates="pages")
    issues: Mapped[list["AuditIssue"]] = relationship("AuditIssue", back_populates="page")


# ── Audit Issues & Tasks ──────────────────────────────────────────────────────

class AuditIssue(Base):
    __tablename__ = "audit_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("crawls.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("crawled_pages.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    issue_type: Mapped[IssueType] = mapped_column(SAEnum(IssueType))
    severity: Mapped[TaskSeverity] = mapped_column(SAEnum(TaskSeverity))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=True)
    affected_url: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    page: Mapped["CrawledPage"] = relationship("CrawledPage", back_populates="issues")
    task: Mapped["Task"] = relationship("Task", back_populates="issue", uselist=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("audit_issues.id", ondelete="SET NULL"), nullable=True)
    assignee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    severity: Mapped[TaskSeverity] = mapped_column(SAEnum(TaskSeverity))
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.OPEN)
    fix_difficulty: Mapped[str] = mapped_column(String(20), default="medium")  # low | medium | high
    affected_url: Mapped[str] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    assignee: Mapped["User"] = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    issue: Mapped["AuditIssue"] = relationship("AuditIssue", back_populates="task")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class KeywordIntent(str, enum.Enum):
    INFORMATIONAL  = "informational"
    NAVIGATIONAL   = "navigational"
    TRANSACTIONAL  = "transactional"
    COMMERCIAL     = "commercial"
    UNKNOWN        = "unknown"


class RankDevice(str, enum.Enum):
    DESKTOP = "desktop"
    MOBILE  = "mobile"


class ContentStatus(str, enum.Enum):
    DRAFT     = "draft"
    GENERATED = "generated"
    PUBLISHED = "published"


class ReportStatus(str, enum.Enum):
    PENDING   = "pending"
    GENERATED = "generated"
    FAILED    = "failed"


# ── Keywords ──────────────────────────────────────────────────────────────────

class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    keyword: Mapped[str]              = mapped_column(String(500), nullable=False)
    search_volume: Mapped[int]        = mapped_column(Integer, nullable=True)
    keyword_difficulty: Mapped[int]   = mapped_column(Integer, nullable=True)   # 0-100
    cpc: Mapped[float]                = mapped_column(Float, nullable=True)
    competition: Mapped[float]        = mapped_column(Float, nullable=True)     # 0-1
    intent: Mapped[KeywordIntent]     = mapped_column(SAEnum(KeywordIntent), default=KeywordIntent.UNKNOWN)
    serp_features: Mapped[list]       = mapped_column(JSON, default=list)       # ["featured_snippet","paa",...]
    is_tracked: Mapped[bool]          = mapped_column(Boolean, default=False)
    target_url: Mapped[str]           = mapped_column(Text, nullable=True)
    cluster_id: Mapped[str]           = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ranks: Mapped[list["RankHistory"]]  = relationship("RankHistory", back_populates="keyword")
    paa_questions: Mapped[list["PAAQuestion"]] = relationship("PAAQuestion", back_populates="keyword")


class PAAQuestion(Base):
    __tablename__ = "paa_questions"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    question: Mapped[str]             = mapped_column(Text, nullable=False)
    answer_snippet: Mapped[str]       = mapped_column(Text, nullable=True)
    depth: Mapped[int]                = mapped_column(Integer, default=0)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())

    keyword: Mapped["Keyword"] = relationship("Keyword", back_populates="paa_questions")


# ── Rank tracking ─────────────────────────────────────────────────────────────

class RankHistory(Base):
    __tablename__ = "rank_history"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    position: Mapped[int]             = mapped_column(Integer, nullable=True)   # null = not in top 100
    url: Mapped[str]                  = mapped_column(Text, nullable=True)      # ranking URL
    device: Mapped[RankDevice]        = mapped_column(SAEnum(RankDevice), default=RankDevice.DESKTOP)
    locale: Mapped[str]               = mapped_column(String(20), default="en-US")
    serp_features: Mapped[list]       = mapped_column(JSON, default=list)
    checked_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    keyword: Mapped["Keyword"] = relationship("Keyword", back_populates="ranks")


# ── On-page analysis ──────────────────────────────────────────────────────────

class OnPageAnalysis(Base):
    __tablename__ = "onpage_analyses"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    url: Mapped[str]                  = mapped_column(Text, nullable=False)
    target_keyword: Mapped[str]       = mapped_column(String(500), nullable=False)
    content_score: Mapped[int]        = mapped_column(Integer, nullable=True)   # 0-100
    word_count: Mapped[int]           = mapped_column(Integer, nullable=True)
    avg_competitor_words: Mapped[int] = mapped_column(Integer, nullable=True)
    keyword_density: Mapped[float]    = mapped_column(Float, nullable=True)
    missing_entities: Mapped[list]    = mapped_column(JSON, default=list)
    present_entities: Mapped[list]    = mapped_column(JSON, default=list)
    suggested_keywords: Mapped[list]  = mapped_column(JSON, default=list)
    internal_link_suggestions: Mapped[list] = mapped_column(JSON, default=list)
    competitor_urls: Mapped[list]     = mapped_column(JSON, default=list)
    raw_analysis: Mapped[dict]        = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Content ───────────────────────────────────────────────────────────────────

class ContentPiece(Base):
    __tablename__ = "content_pieces"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    title: Mapped[str]                = mapped_column(String(500), nullable=False)
    target_keyword: Mapped[str]       = mapped_column(String(500), nullable=False)
    status: Mapped[ContentStatus]     = mapped_column(SAEnum(ContentStatus), default=ContentStatus.DRAFT)
    brief: Mapped[dict]               = mapped_column(JSON, default=dict)       # structured brief data
    article_markdown: Mapped[str]     = mapped_column(Text, nullable=True)
    word_count: Mapped[int]           = mapped_column(Integer, nullable=True)
    competitor_urls: Mapped[list]     = mapped_column(JSON, default=list)
    seo_score: Mapped[int]            = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── GSC / GA4 integrations ────────────────────────────────────────────────────

class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    provider: Mapped[str]             = mapped_column(String(50), nullable=False)   # "gsc" | "ga4"
    property_id: Mapped[str]          = mapped_column(String(255), nullable=True)   # e.g. sc-domain:example.com
    access_token: Mapped[str]         = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str]        = mapped_column(Text, nullable=True)
    token_expiry: Mapped[datetime]    = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool]           = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())


class GSCDataPoint(Base):
    __tablename__ = "gsc_data"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    date: Mapped[datetime]            = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    query: Mapped[str]                = mapped_column(Text, nullable=True)
    page: Mapped[str]                 = mapped_column(Text, nullable=True)
    clicks: Mapped[int]               = mapped_column(Integer, default=0)
    impressions: Mapped[int]          = mapped_column(Integer, default=0)
    ctr: Mapped[float]                = mapped_column(Float, nullable=True)
    position: Mapped[float]           = mapped_column(Float, nullable=True)
    device: Mapped[str]               = mapped_column(String(20), nullable=True)
    country: Mapped[str]              = mapped_column(String(10), nullable=True)


# ── Reports ───────────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    title: Mapped[str]                = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime]    = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ReportStatus]      = mapped_column(SAEnum(ReportStatus), default=ReportStatus.PENDING)
    pdf_path: Mapped[str]             = mapped_column(Text, nullable=True)       # S3 key or local path
    summary_html: Mapped[str]         = mapped_column(Text, nullable=True)
    data_snapshot: Mapped[dict]       = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BacklinkStatus(str, enum.Enum):
    LIVE    = "live"
    LOST    = "lost"
    NEW     = "new"


class OutreachStatus(str, enum.Enum):
    PROSPECTING  = "prospecting"
    QUALIFIED    = "qualified"
    CONTACTED    = "contacted"
    FOLLOWED_UP  = "followed_up"
    NEGOTIATING  = "negotiating"
    PLACED       = "placed"
    DECLINED     = "declined"


class CreditLedgerType(str, enum.Enum):
    GRANT   = "grant"
    DEBIT   = "debit"
    REFUND  = "refund"


# ── Backlinks ─────────────────────────────────────────────────────────────────

class BacklinkProfile(Base):
    __tablename__ = "backlink_profiles"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    domain: Mapped[str]                = mapped_column(String(255), nullable=False)
    total_backlinks: Mapped[int]       = mapped_column(Integer, default=0)
    total_referring_domains: Mapped[int] = mapped_column(Integer, default=0)
    domain_rating: Mapped[int]         = mapped_column(Integer, nullable=True)
    spam_score: Mapped[int]            = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())


class Backlink(Base):
    __tablename__ = "backlinks"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    source_url: Mapped[str]            = mapped_column(Text, nullable=False)
    source_domain: Mapped[str]         = mapped_column(String(255), nullable=False, index=True)
    target_url: Mapped[str]            = mapped_column(Text, nullable=False)
    anchor_text: Mapped[str]           = mapped_column(Text, nullable=True)
    is_dofollow: Mapped[bool]          = mapped_column(Boolean, default=True)
    domain_rating: Mapped[int]         = mapped_column(Integer, nullable=True)
    spam_score: Mapped[int]            = mapped_column(Integer, nullable=True)
    toxicity_score: Mapped[int]        = mapped_column(Integer, default=0)   # 0-100
    is_competitor: Mapped[bool]        = mapped_column(Boolean, default=False)
    status: Mapped[BacklinkStatus]     = mapped_column(SAEnum(BacklinkStatus), default=BacklinkStatus.LIVE)
    first_seen: Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime]        = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Competitors ───────────────────────────────────────────────────────────────

class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    domain: Mapped[str]                = mapped_column(String(255), nullable=False)
    name: Mapped[str]                  = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool]            = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    events: Mapped[list["CompetitorEvent"]] = relationship("CompetitorEvent", back_populates="competitor")


class CompetitorEvent(Base):
    __tablename__ = "competitor_events"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    competitor_id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    event_type: Mapped[str]            = mapped_column(String(50), nullable=False)  # new_content | backlink_gained | backlink_lost | rank_change
    title: Mapped[str]                 = mapped_column(String(500), nullable=False)
    description: Mapped[str]           = mapped_column(Text, nullable=True)
    url: Mapped[str]                   = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict]             = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_read: Mapped[bool]              = mapped_column(Boolean, default=False)

    competitor: Mapped["Competitor"]   = relationship("Competitor", back_populates="events")


# ── Link Building CRM ─────────────────────────────────────────────────────────

class LinkProspect(Base):
    __tablename__ = "link_prospects"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    domain: Mapped[str]                = mapped_column(String(255), nullable=False)
    url: Mapped[str]                   = mapped_column(Text, nullable=True)
    contact_name: Mapped[str]          = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str]         = mapped_column(String(255), nullable=True)
    domain_rating: Mapped[int]         = mapped_column(Integer, nullable=True)
    traffic_estimate: Mapped[int]      = mapped_column(Integer, nullable=True)
    status: Mapped[OutreachStatus]     = mapped_column(SAEnum(OutreachStatus), default=OutreachStatus.PROSPECTING)
    source: Mapped[str]                = mapped_column(String(50), default="manual")  # competitor_gap | brand_mention | manual
    notes: Mapped[str]                 = mapped_column(Text, nullable=True)
    last_contacted_at: Mapped[datetime]= mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    emails: Mapped[list["OutreachEmail"]] = relationship("OutreachEmail", back_populates="prospect")


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prospect_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("link_prospects.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    subject: Mapped[str]               = mapped_column(String(500), nullable=False)
    body: Mapped[str]                  = mapped_column(Text, nullable=False)
    is_sent: Mapped[bool]              = mapped_column(Boolean, default=False)
    is_opened: Mapped[bool]            = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime]          = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    prospect: Mapped["LinkProspect"]   = relationship("LinkProspect", back_populates="emails")


# ── Predictive Analytics ──────────────────────────────────────────────────────

class CannibalizationIssue(Base):
    __tablename__ = "cannibalization_issues"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    keyword: Mapped[str]               = mapped_column(String(500), nullable=False)
    competing_urls: Mapped[list]       = mapped_column(JSON, default=list)
    recommendation: Mapped[str]        = mapped_column(String(50), nullable=True)  # consolidate | canonicalize | differentiate
    severity: Mapped[str]              = mapped_column(String(10), default="medium")
    is_resolved: Mapped[bool]          = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Billing / Credits ─────────────────────────────────────────────────────────

class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    ledger_type: Mapped[CreditLedgerType] = mapped_column(SAEnum(CreditLedgerType))
    credit_type: Mapped[str]           = mapped_column(String(50), nullable=False)  # crawl | keyword | ai
    amount: Mapped[int]                = mapped_column(Integer, nullable=False)     # positive=grant, negative=debit
    description: Mapped[str]           = mapped_column(String(255), nullable=True)
    reference_id: Mapped[str]          = mapped_column(String(255), nullable=True)  # Stripe session ID etc.
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)
    stripe_customer_id: Mapped[str]    = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str]= mapped_column(String(255), nullable=True)
    plan: Mapped[str]                  = mapped_column(String(50), default="starter")
    status: Mapped[str]                = mapped_column(String(50), default="active")
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
