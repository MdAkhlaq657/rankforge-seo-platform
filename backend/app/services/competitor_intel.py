"""
Competitor intelligence service.
Monitors competitor domains for new content, backlink changes, and rank movements.
"""
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()

MOCK_TOPICS = [
    "Ultimate Guide", "Best Practices", "How To", "Complete Tutorial",
    "Case Study", "Comparison", "Review", "Tips and Tricks", "Strategy Guide",
]
MOCK_CATEGORIES = [
    "seo", "content-marketing", "link-building", "technical-seo",
    "keyword-research", "analytics", "social-media", "email-marketing",
]


def _seed(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def _mock_new_content(competitor_domain: str, since_days: int = 7) -> list[dict]:
    """Simulate newly published competitor content."""
    rng = random.Random(_seed(f"{competitor_domain}{since_days}"))
    count = rng.randint(0, 4)
    now = datetime.now(timezone.utc)
    results = []
    for _ in range(count):
        topic = rng.choice(MOCK_TOPICS)
        cat = rng.choice(MOCK_CATEGORIES)
        slug = f"{cat}-{rng.randint(100, 999)}"
        published = now - timedelta(days=rng.randint(0, since_days))
        results.append({
            "url": f"https://{competitor_domain}/blog/{slug}/",
            "title": f"The {topic} to {cat.replace('-', ' ').title()}",
            "published_at": published.isoformat(),
            "estimated_words": rng.randint(800, 4000),
        })
    return results


def _mock_backlink_changes(competitor_domain: str) -> dict:
    rng = random.Random(_seed(f"{competitor_domain}bl"))
    gained = rng.randint(0, 8)
    lost = rng.randint(0, 4)
    domains_gained = [f"ref{rng.randint(100,999)}.com" for _ in range(gained)]
    domains_lost = [f"old{rng.randint(100,999)}.net" for _ in range(lost)]
    return {
        "gained": gained,
        "lost": lost,
        "domains_gained": domains_gained,
        "domains_lost": domains_lost,
    }


async def check_new_content(competitor_domain: str, since_days: int = 7) -> list[dict]:
    """Check for new content published by competitor."""
    # In production: fetch sitemap, diff against stored URLs
    # For now: realistic mock
    return _mock_new_content(competitor_domain, since_days)


async def check_backlink_changes(competitor_domain: str) -> dict:
    """Detect major backlinks gained/lost by competitor."""
    return _mock_backlink_changes(competitor_domain)


async def run_competitor_check(
    competitor_domain: str,
    project_domain: str,
) -> list[dict]:
    """
    Full competitor check. Returns list of event dicts.
    Each event has: event_type, title, description, url, metadata.
    """
    events = []
    now = datetime.now(timezone.utc)

    # New content events
    new_pages = await check_new_content(competitor_domain)
    for page in new_pages:
        events.append({
            "event_type": "new_content",
            "title": f"{competitor_domain} published new content",
            "description": f"New page: {page['title']} (~{page['estimated_words']:,} words)",
            "url": page["url"],
            "metadata": page,
        })

    # Backlink events
    bl_changes = await check_backlink_changes(competitor_domain)
    if bl_changes["gained"] >= 3:
        events.append({
            "event_type": "backlink_gained",
            "title": f"{competitor_domain} gained {bl_changes['gained']} new referring domains",
            "description": f"Top new domains: {', '.join(bl_changes['domains_gained'][:3])}",
            "url": None,
            "metadata": bl_changes,
        })
    if bl_changes["lost"] >= 2:
        events.append({
            "event_type": "backlink_lost",
            "title": f"{competitor_domain} lost {bl_changes['lost']} referring domains",
            "description": f"Lost domains: {', '.join(bl_changes['domains_lost'][:3])}",
            "url": None,
            "metadata": bl_changes,
        })

    return events


def _mock_brand_mentions(brand: str, days: int = 30) -> list[dict]:
    rng = random.Random(_seed(brand))
    count = rng.randint(2, 12)
    sources = ["techcrunch.com", "searchengineland.com", "moz.com", "ahrefs.com",
               "semrush.com", "reddit.com", "twitter.com", "medium.com"]
    now = datetime.now(timezone.utc)
    results = []
    for _ in range(count):
        src = rng.choice(sources)
        is_linked = rng.random() > 0.4
        results.append({
            "source_domain": src,
            "url": f"https://{src}/article/{rng.randint(1000,9999)}",
            "title": f"Mention of {brand} in article about {rng.choice(MOCK_CATEGORIES).replace('-',' ')}",
            "is_linked": is_linked,
            "detected_at": (now - timedelta(days=rng.randint(0, days))).isoformat(),
            "snippet": f"...the platform {brand} offers comprehensive tools for...",
        })
    results.sort(key=lambda x: x["detected_at"], reverse=True)
    return results


async def get_brand_mentions(brand: str, domain: str, days: int = 30) -> list[dict]:
    """Fetch brand mentions across the web. Unlinked = outreach opportunity."""
    return _mock_brand_mentions(brand, days)
