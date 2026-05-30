// ── Auth ──────────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: string;
  crawl_credits: number;
  keyword_credits: number;
}

export interface MeResponse {
  user: User;
  organizations: Organization[];
  current_org: Organization;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ── Projects ──────────────────────────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  domain: string;
  crawl_scope: string;
  crawl_frequency: string;
  max_pages: number;
  is_active: boolean;
  created_at: string;
  last_crawl_at?: string;
  last_crawl_status?: string;
  total_pages?: number;
  open_issues?: number;
}

export interface ProjectCreate {
  name: string;
  domain: string;
  crawl_scope?: string;
  crawl_frequency?: string;
  respect_robots_txt?: boolean;
  max_pages?: number;
}

// ── Crawls ────────────────────────────────────────────────────────────────────
export type CrawlStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Crawl {
  id: string;
  project_id: string;
  status: CrawlStatus;
  pages_crawled: number;
  pages_total: number | null;
  issues_found: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface CrawlSummary {
  crawl: Crawl;
  status_code_breakdown: Record<string, number>;
  issue_breakdown: Record<string, number>;
  cwv_summary: {
    avg_lcp: number;
    avg_cls: number;
    avg_inp: number;
    avg_score: number;
  };
  score: number;
}

export interface CrawledPage {
  id: string;
  url: string;
  status_code: number | null;
  title: string | null;
  title_length: number | null;
  meta_description: string | null;
  h1: string | null;
  h1_count: number;
  is_indexable: boolean;
  has_noindex: boolean;
  word_count: number;
  lcp_mobile: number | null;
  cls_mobile: number | null;
  inp_mobile: number | null;
  performance_score: number | null;
  issues_count: number;
}

// ── Issues & Tasks ────────────────────────────────────────────────────────────
export type Severity = "p1" | "p2" | "p3";
export type TaskStatus = "open" | "in_progress" | "in_review" | "done" | "resolved";

export interface AuditIssue {
  id: string;
  issue_type: string;
  severity: Severity;
  title: string;
  description: string | null;
  recommendation: string | null;
  affected_url: string;
  meta: Record<string, unknown>;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  severity: Severity;
  status: TaskStatus;
  fix_difficulty: string;
  affected_url: string | null;
  assignee_id: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  issue_type?: string;
}

export interface TaskBoardColumn {
  status: TaskStatus;
  tasks: Task[];
  count: number;
}
