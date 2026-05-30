# RankForge — SEO Platform (Phase 1)

A production-ready SEO SaaS application. Phase 1 covers auth, multi-tenant project spaces, async site crawler, technical audit engine, and a Kanban task board.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), React, TailwindCSS, Tanstack Query, Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2 |
| Task queue | Celery 5, Redis |
| Database | PostgreSQL 16 |
| Crawler | httpx + BeautifulSoup4 + BFS queue |
| Auth | JWT (python-jose) + bcrypt + HTTPBearer |
| Containerisation | Docker + Docker Compose |

---

## Quick start

### 1. Clone & configure

```bash
git clone <your-repo>
cd seo-platform
cp .env.example .env
```

Edit `.env` — at minimum, change `SECRET_KEY` to a random 64-char string for anything beyond local dev.

### 2. Start all services

```bash
docker compose up --build
```

This starts:
- **PostgreSQL** on port 5432
- **Redis** on port 6379
- **FastAPI backend** on http://localhost:8000
- **Celery worker** (crawl queue)
- **Celery beat** (scheduled jobs)
- **Next.js frontend** on http://localhost:3000

### 3. Open the app

Navigate to http://localhost:3000, click **Create one free**, and register with any email/password. An organization is created automatically on registration.

---

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Ensure Postgres + Redis are running locally, then:
uvicorn app.main:app --reload --port 8000
```

Celery worker (separate terminal):
```bash
celery -A app.workers.celery_app worker --loglevel=info -Q crawls,audits,default
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API documentation

FastAPI auto-generates OpenAPI docs at:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc

---

## Key endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register user + create org |
| POST | `/api/v1/auth/login` | Login → JWT tokens |
| GET | `/api/v1/auth/me` | Current user + orgs |

### Projects
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/projects` | List org projects |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects/{id}` | Get project |
| PATCH | `/api/v1/projects/{id}` | Update project |

### Crawls
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/projects/{id}/crawls` | Start a new crawl |
| GET | `/api/v1/projects/{id}/crawls` | List crawl history |
| GET | `/api/v1/projects/{id}/crawls/{crawl_id}` | Full crawl summary + breakdown |
| GET | `/api/v1/projects/{id}/crawls/{crawl_id}/pages` | Paginated page results |
| GET | `/api/v1/projects/{id}/crawls/{crawl_id}/issues` | Issues list (filterable by severity) |

### Tasks
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/projects/{id}/tasks/board` | Kanban board (grouped by status) |
| GET | `/api/v1/projects/{id}/tasks` | Flat task list |
| POST | `/api/v1/projects/{id}/tasks` | Create manual task |
| PATCH | `/api/v1/projects/{id}/tasks/{task_id}` | Update task (status, assignee, etc.) |
| POST | `/api/v1/projects/{id}/tasks/bulk-update` | Bulk status/assignee change |

---

## Database schema

```
users ──< org_memberships >── organizations
                                    │
                               projects
                                    │
                        ┌───────────┴───────────┐
                     crawls                   tasks
                        │
               crawled_pages ──< audit_issues
                                      │
                                    tasks (auto-created per issue)
```

All tables include `organization_id` with PostgreSQL row-level security enforced at the application layer. Every query is org-scoped.

---

## Detected issue types

| Issue | Severity | Auto-fix difficulty |
|---|---|---|
| Broken page (4xx/5xx) | P1 Critical | Medium |
| Noindex on key page | P1 Critical | Low |
| Missing title | P2 Important | Low |
| Duplicate title | P2 Important | Low |
| Missing H1 | P2 Important | Low |
| Poor Core Web Vitals | P2 Important | High |
| Missing canonical | P2 Important | Low |
| Multiple H1 | P3 Minor | Low |
| Missing meta description | P3 Minor | Low |
| Thin content (<300 words) | P3 Minor | High |

---

## Crawl behaviour

- BFS crawl starting from `https://{domain}`
- Follows internal links up to depth 3
- Respects `robots.txt` when enabled
- Rate-limited to ~3 req/sec per crawl
- CWV data is mocked (realistic distribution: 60% good / 30% NI / 10% poor) — swap `_mock_cwv()` in `services/crawler.py` with a real PageSpeed Insights API call when you add the key
- Issues are auto-detected in a post-crawl pass and create Task records immediately

---

## Phase 2 checklist (next steps)

- [ ] Keyword research module (DataForSEO integration)
- [ ] On-page NLP scanner (spaCy + KeyBERT)
- [ ] Backlink analysis (DataForSEO Backlinks)
- [ ] Rank tracking (daily SERP checks → TimescaleDB)
- [ ] GSC + GA4 OAuth integration
- [ ] AI content brief generator (Anthropic API)
- [ ] Automated PDF reporting (WeasyPrint)
- [ ] Competitor intelligence monitoring
- [ ] Credit billing system (Stripe)

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL URL | See `.env.example` |
| `REDIS_URL` | Redis broker URL | `redis://redis:6379/0` |
| `SECRET_KEY` | JWT signing key | **Change in production** |
| `DATAFORSEO_LOGIN` | DataForSEO API login | — (mock data used if empty) |
| `GOOGLE_PSI_API_KEY` | PageSpeed Insights key | — (mock data used if empty) |
| `NEXT_PUBLIC_API_URL` | Backend URL for frontend | `http://localhost:8000` |
