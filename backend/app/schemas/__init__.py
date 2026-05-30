import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator
from app.models import OrgRole, CrawlStatus, TaskStatus, TaskSeverity, IssueType


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    org_name: str  # Create org on registration

    # @field_validator("password")
    # @classmethod
    # def password_min_length(cls, v):
        # if len(v) < 8:
        #     raise ValueError("Password must be at least 8 characters")
        # return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    crawl_credits: int
    keyword_credits: int

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserOut
    organizations: List[OrgOut]
    current_org: OrgOut


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    domain: str
    crawl_scope: str = "domain"
    crawl_frequency: str = "weekly"
    respect_robots_txt: bool = True
    max_pages: int = 500

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v):
        v = v.strip().lower()
        v = v.replace("https://", "").replace("http://", "").rstrip("/")
        return v


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    crawl_frequency: Optional[str] = None
    respect_robots_txt: Optional[bool] = None
    max_pages: Optional[int] = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    domain: str
    crawl_scope: str
    crawl_frequency: str
    max_pages: int
    is_active: bool
    created_at: datetime
    last_crawl_at: Optional[datetime] = None
    last_crawl_status: Optional[str] = None
    total_pages: Optional[int] = None
    open_issues: Optional[int] = None

    model_config = {"from_attributes": True}


# ── Crawls ────────────────────────────────────────────────────────────────────

class CrawlOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: CrawlStatus
    pages_crawled: int
    pages_total: Optional[int]
    issues_found: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class CrawlSummary(BaseModel):
    crawl: CrawlOut
    status_code_breakdown: dict
    issue_breakdown: dict
    cwv_summary: dict
    score: int  # 0-100 overall health score


class PageOut(BaseModel):
    id: uuid.UUID
    url: str
    status_code: Optional[int]
    title: Optional[str]
    title_length: Optional[int]
    meta_description: Optional[str]
    h1: Optional[str]
    h1_count: int
    is_indexable: bool
    has_noindex: bool
    word_count: int
    lcp_mobile: Optional[float]
    cls_mobile: Optional[float]
    inp_mobile: Optional[float]
    performance_score: Optional[int]
    issues_count: int = 0

    model_config = {"from_attributes": True}


# ── Issues & Tasks ────────────────────────────────────────────────────────────

class IssueOut(BaseModel):
    id: uuid.UUID
    issue_type: IssueType
    severity: TaskSeverity
    title: str
    description: Optional[str]
    recommendation: Optional[str]
    affected_url: str
    meta: dict

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: TaskSeverity
    fix_difficulty: str = "medium"
    affected_url: Optional[str] = None
    due_date: Optional[datetime] = None
    assignee_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    severity: Optional[TaskSeverity] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[datetime] = None
    fix_difficulty: Optional[str] = None


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: Optional[str]
    severity: TaskSeverity
    status: TaskStatus
    fix_difficulty: str
    affected_url: Optional[str]
    assignee_id: Optional[uuid.UUID]
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    issue_type: Optional[IssueType] = None

    model_config = {"from_attributes": True}


class TaskBoardColumn(BaseModel):
    status: TaskStatus
    tasks: List[TaskOut]
    count: int
