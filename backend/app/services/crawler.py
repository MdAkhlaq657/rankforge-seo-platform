import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
import tldextract
import structlog

from app.models import (
    CrawledPage, AuditIssue, Task, IssueType, TaskSeverity, TaskStatus
)

logger = structlog.get_logger()

# ── CWV thresholds ─────────────────────────────────────────────────────────────
CWV_THRESHOLDS = {
    "lcp": {"good": 2.5, "needs_improvement": 4.0},
    "cls": {"good": 0.1, "needs_improvement": 0.25},
    "inp": {"good": 200, "needs_improvement": 500},
}

# ── Issue definitions ──────────────────────────────────────────────────────────
ISSUE_DEFINITIONS = {
    IssueType.MISSING_TITLE: {
        "severity": TaskSeverity.P2,
        "title": "Missing title tag",
        "description": "This page has no <title> tag, which is a critical on-page SEO signal.",
        "recommendation": "Add a unique, descriptive title tag between 50–60 characters.",
        "fix_difficulty": "low",
    },
    IssueType.DUPLICATE_TITLE: {
        "severity": TaskSeverity.P2,
        "title": "Duplicate title tag",
        "description": "This page shares its title tag with one or more other pages on the site.",
        "recommendation": "Write a unique title for each page that accurately reflects its content.",
        "fix_difficulty": "low",
    },
    IssueType.MISSING_META: {
        "severity": TaskSeverity.P3,
        "title": "Missing meta description",
        "description": "No meta description found. While not a direct ranking factor, it influences click-through rate.",
        "recommendation": "Add a meta description between 150–160 characters.",
        "fix_difficulty": "low",
    },
    IssueType.MISSING_H1: {
        "severity": TaskSeverity.P2,
        "title": "Missing H1 tag",
        "description": "No H1 heading was found on this page.",
        "recommendation": "Add a single H1 tag that contains the primary keyword for this page.",
        "fix_difficulty": "low",
    },
    IssueType.MULTIPLE_H1: {
        "severity": TaskSeverity.P3,
        "title": "Multiple H1 tags",
        "description": "More than one H1 tag was detected. This dilutes the page's topical signal.",
        "recommendation": "Consolidate to a single H1 per page.",
        "fix_difficulty": "low",
    },
    IssueType.BROKEN_LINK: {
        "severity": TaskSeverity.P1,
        "title": "Broken page (4xx/5xx)",
        "description": "This URL returned a non-200 status code.",
        "recommendation": "Fix or redirect this URL. If the content has moved, implement a 301 redirect.",
        "fix_difficulty": "medium",
    },
    IssueType.NOINDEX_KEY_PAGE: {
        "severity": TaskSeverity.P1,
        "title": "Key page blocked from indexing",
        "description": "This page has a noindex directive but may be important for organic traffic.",
        "recommendation": "Verify the noindex is intentional. If not, remove it.",
        "fix_difficulty": "low",
    },
    IssueType.THIN_CONTENT: {
        "severity": TaskSeverity.P3,
        "title": "Thin content",
        "description": "Page contains fewer than 300 words, which may be considered thin by search engines.",
        "recommendation": "Expand the page content to cover the topic comprehensively.",
        "fix_difficulty": "high",
    },
    IssueType.MISSING_CANONICAL: {
        "severity": TaskSeverity.P2,
        "title": "Missing canonical tag",
        "description": "No canonical tag found. This can lead to duplicate content issues.",
        "recommendation": "Add a self-referencing canonical tag to every page.",
        "fix_difficulty": "low",
    },
    IssueType.SLOW_CWV: {
        "severity": TaskSeverity.P2,
        "title": "Poor Core Web Vitals",
        "description": "One or more Core Web Vitals metrics are in the 'Needs Improvement' or 'Poor' range.",
        "recommendation": "Optimize images, reduce render-blocking resources, and audit JavaScript execution time.",
        "fix_difficulty": "high",
    },
}


def _mock_cwv(url: str) -> dict:
    """Generate realistic mock CWV data. Roughly 60% good, 30% NI, 10% poor."""
    seed = hash(url) % 100
    if seed < 60:
        lcp = round(random.uniform(1.2, 2.4), 2)
        cls = round(random.uniform(0.01, 0.09), 3)
        inp = random.randint(80, 190)
        score = random.randint(82, 98)
    elif seed < 85:
        lcp = round(random.uniform(2.5, 3.8), 2)
        cls = round(random.uniform(0.1, 0.22), 3)
        inp = random.randint(200, 480)
        score = random.randint(55, 79)
    else:
        lcp = round(random.uniform(4.0, 8.0), 2)
        cls = round(random.uniform(0.25, 0.6), 3)
        inp = random.randint(500, 1200)
        score = random.randint(20, 54)
    return {
        "lcp_mobile": lcp,
        "cls_mobile": cls,
        "inp_mobile": inp,
        "lcp_desktop": round(lcp * 0.6, 2),
        "cls_desktop": round(cls * 0.5, 3),
        "inp_desktop": int(inp * 0.5),
        "performance_score": score,
    }


def _has_poor_cwv(cwv: dict) -> bool:
    return (
        cwv["lcp_mobile"] > CWV_THRESHOLDS["lcp"]["needs_improvement"]
        or cwv["cls_mobile"] > CWV_THRESHOLDS["cls"]["needs_improvement"]
        or cwv["inp_mobile"] > CWV_THRESHOLDS["inp"]["needs_improvement"]
    )


async def crawl_page(client: httpx.AsyncClient, url: str, base_domain: str, depth: int = 0) -> dict:
    """Crawl a single page and return extracted data."""
    try:
        response = await client.get(url, follow_redirects=True, timeout=15.0)
        redirect_chain = [str(r.url) for r in response.history]
        final_url = str(response.url)
        status_code = response.status_code

        page_data = {
            "url": url,
            "final_url": final_url,
            "status_code": status_code,
            "redirect_chain": redirect_chain,
            "redirect_url": final_url if redirect_chain else None,
            "page_depth": depth,
            "discovered_urls": [],
        }

        if status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            return page_data

        soup = BeautifulSoup(response.text, "lxml")

        # Title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        page_data["title"] = title
        page_data["title_length"] = len(title) if title else 0

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = meta_desc.get("content", "").strip() if meta_desc else None
        page_data["meta_description"] = desc
        page_data["meta_description_length"] = len(desc) if desc else 0

        # Headings
        h1_tags = soup.find_all("h1")
        h2_tags = soup.find_all("h2")
        page_data["h1"] = h1_tags[0].get_text(strip=True) if h1_tags else None
        page_data["h1_count"] = len(h1_tags)
        page_data["h2_count"] = len(h2_tags)

        # Canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        page_data["canonical_url"] = canonical.get("href") if canonical else None

        # Indexability
        robots_meta = soup.find("meta", attrs={"name": "robots"})
        robots_content = robots_meta.get("content", "").lower() if robots_meta else ""
        page_data["has_noindex"] = "noindex" in robots_content
        page_data["is_indexable"] = not page_data["has_noindex"]

        # Word count (rough)
        body = soup.find("body")
        page_data["word_count"] = len(body.get_text().split()) if body else 0

        # Schema markup
        schema_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
        page_data["has_schema"] = len(schema_tags) > 0
        page_data["schema_types"] = [str(i) for i in range(len(schema_tags))]

        # Links
        all_links = soup.find_all("a", href=True)
        internal_links = 0
        external_links = 0
        discovered_urls = []
        for link in all_links:
            href = link["href"].strip()
            abs_url = urljoin(url, href)
            parsed = urlparse(abs_url)
            if not parsed.scheme.startswith("http"):
                continue
            link_domain = tldextract.extract(abs_url).registered_domain
            if link_domain == base_domain:
                internal_links += 1
                if depth < 3 and abs_url not in discovered_urls:
                    discovered_urls.append(abs_url)
            else:
                external_links += 1
        page_data["internal_links"] = internal_links
        page_data["external_links"] = external_links
        page_data["discovered_urls"] = discovered_urls[:50]  # Cap discovery per page

        # CWV (mock)
        page_data.update(_mock_cwv(url))

        return page_data

    except httpx.TimeoutException:
        return {"url": url, "status_code": 408, "error": "timeout", "page_depth": depth, "discovered_urls": []}
    except Exception as e:
        return {"url": url, "status_code": None, "error": str(e), "page_depth": depth, "discovered_urls": []}


def detect_issues(page_data: dict, all_titles: set[str]) -> list[dict]:
    """Detect SEO issues from crawled page data. Returns list of issue dicts."""
    issues = []
    status = page_data.get("status_code")

    # Broken page
    if status and status >= 400:
        defn = ISSUE_DEFINITIONS[IssueType.BROKEN_LINK]
        issues.append({**defn, "issue_type": IssueType.BROKEN_LINK,
                       "meta": {"status_code": status}})
        return issues  # No point checking on-page for error pages

    if status != 200:
        return issues

    # Title issues
    title = page_data.get("title")
    if not title:
        defn = ISSUE_DEFINITIONS[IssueType.MISSING_TITLE]
        issues.append({**defn, "issue_type": IssueType.MISSING_TITLE, "meta": {}})
    elif title in all_titles:
        defn = ISSUE_DEFINITIONS[IssueType.DUPLICATE_TITLE]
        issues.append({**defn, "issue_type": IssueType.DUPLICATE_TITLE, "meta": {"title": title}})

    # Meta description
    if not page_data.get("meta_description"):
        defn = ISSUE_DEFINITIONS[IssueType.MISSING_META]
        issues.append({**defn, "issue_type": IssueType.MISSING_META, "meta": {}})

    # H1 issues
    h1_count = page_data.get("h1_count", 0)
    if h1_count == 0:
        defn = ISSUE_DEFINITIONS[IssueType.MISSING_H1]
        issues.append({**defn, "issue_type": IssueType.MISSING_H1, "meta": {}})
    elif h1_count > 1:
        defn = ISSUE_DEFINITIONS[IssueType.MULTIPLE_H1]
        issues.append({**defn, "issue_type": IssueType.MULTIPLE_H1, "meta": {"count": h1_count}})

    # Canonical
    if not page_data.get("canonical_url"):
        defn = ISSUE_DEFINITIONS[IssueType.MISSING_CANONICAL]
        issues.append({**defn, "issue_type": IssueType.MISSING_CANONICAL, "meta": {}})

    # Noindex
    if page_data.get("has_noindex") and page_data.get("page_depth", 0) <= 2:
        defn = ISSUE_DEFINITIONS[IssueType.NOINDEX_KEY_PAGE]
        issues.append({**defn, "issue_type": IssueType.NOINDEX_KEY_PAGE, "meta": {}})

    # Thin content
    word_count = page_data.get("word_count", 0)
    if 0 < word_count < 300:
        defn = ISSUE_DEFINITIONS[IssueType.THIN_CONTENT]
        issues.append({**defn, "issue_type": IssueType.THIN_CONTENT, "meta": {"word_count": word_count}})

    # CWV
    if _has_poor_cwv(page_data):
        defn = ISSUE_DEFINITIONS[IssueType.SLOW_CWV]
        issues.append({**defn, "issue_type": IssueType.SLOW_CWV,
                       "meta": {
                           "lcp": page_data.get("lcp_mobile"),
                           "cls": page_data.get("cls_mobile"),
                           "inp": page_data.get("inp_mobile"),
                       }})

    return issues
