"""
Backlink analysis service.
Fetches backlinks via DataForSEO or generates rich mock data.
Computes toxicity scores, identifies competitor gap, suggests disavow candidates.
"""
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

# ── Mock data constants ───────────────────────────────────────────────────────

MOCK_TLDS = [".com", ".org", ".net", ".io", ".co", ".info", ".biz", ".edu", ".gov"]
SPAM_TLDS = [".xyz", ".top", ".click", ".link", ".pw", ".tk", ".ml", ".cf"]
ANCHOR_TEMPLATES = [
    "{kw}", "{kw} tool", "best {kw}", "{kw} software", "click here",
    "visit website", "learn more", "{domain}", "this article", "{kw} guide",
    "{kw} tips", "read more", "source", "{kw} review", "official site",
]


def _seed(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def _toxicity_score(domain: str, is_dofollow: bool, anchor: str, dr: int) -> int:
    """Compute 0-100 toxicity score for a backlink."""
    score = 0
    tld = "." + domain.split(".")[-1]
    if tld in SPAM_TLDS: score += 40
    if dr < 5: score += 20
    if not is_dofollow: score -= 10
    # Over-optimized anchor
    exact_match_words = ["buy", "cheap", "discount", "free", "download", "casino", "porn"]
    if any(w in anchor.lower() for w in exact_match_words): score += 30
    if len(anchor.split()) == 1 and len(anchor) > 20: score += 10  # suspiciously long anchor
    return max(0, min(100, score + random.Random(_seed(domain)).randint(-5, 5)))


def _mock_backlinks(domain: str, count: int = 100, is_competitor: bool = False) -> list[dict]:
    rng = random.Random(_seed(domain))
    now = datetime.now(timezone.utc)
    results = []

    for i in range(count):
        # Source domain
        src_tld = rng.choices(MOCK_TLDS + SPAM_TLDS, weights=[8]*len(MOCK_TLDS) + [1]*len(SPAM_TLDS))[0]
        src_domain = f"source{rng.randint(1, 9999)}{src_tld}"
        src_url = f"https://{src_domain}/article/{rng.randint(1000, 9999)}"
        target_path = rng.choice(["/", "/blog/", "/services/", "/products/", f"/{domain}-guide/"])
        target_url = f"https://{domain}{target_path}"

        # Metrics
        dr = rng.randint(0, 90)
        is_dofollow = rng.random() > 0.25
        anchor = rng.choice(ANCHOR_TEMPLATES).format(kw=domain.split(".")[0], domain=domain)
        days_ago = rng.randint(0, 730)
        first_seen = now - timedelta(days=days_ago + rng.randint(0, 180))
        last_seen = now - timedelta(days=rng.randint(0, days_ago))
        status = "live"
        if rng.random() < 0.12: status = "lost"
        elif days_ago < 14: status = "new"

        toxicity = _toxicity_score(src_domain, is_dofollow, anchor, dr)
        spam_score = min(100, toxicity + rng.randint(-10, 10))

        results.append({
            "source_url": src_url,
            "source_domain": src_domain,
            "target_url": target_url,
            "anchor_text": anchor,
            "is_dofollow": is_dofollow,
            "domain_rating": dr,
            "spam_score": max(0, spam_score),
            "toxicity_score": toxicity,
            "is_competitor": is_competitor,
            "status": status,
            "first_seen": first_seen.isoformat(),
            "last_seen": last_seen.isoformat(),
        })

    return results


def _mock_profile(domain: str) -> dict:
    rng = random.Random(_seed(domain))
    return {
        "domain": domain,
        "total_backlinks": rng.randint(50, 15000),
        "total_referring_domains": rng.randint(20, 3000),
        "domain_rating": rng.randint(10, 85),
        "spam_score": rng.randint(0, 30),
    }


def _backlink_gap(own_domains: set, competitor_domains: set) -> list[str]:
    """Domains linking to competitor but NOT to target."""
    return list(competitor_domains - own_domains)


# ── DataForSEO client ─────────────────────────────────────────────────────────

async def _dataforseo_backlinks(domain: str, limit: int = 100) -> dict:
    url = "https://api.dataforseo.com/v3/backlinks/backlinks/live"
    payload = [{
        "target": domain,
        "limit": limit,
        "mode": "as_is",
        "filters": [["dofollow", "=", True]],
    }]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url, json=payload,
            auth=(settings.DATAFORSEO_LOGIN, settings.DATAFORSEO_PASSWORD),
            timeout=30,
        )
        resp.raise_for_status()
    data = resp.json()
    items = []
    for task in data.get("tasks", []):
        for result in task.get("result", []):
            for item in result.get("items", []):
                items.append({
                    "source_url": item.get("url_from", ""),
                    "source_domain": item.get("domain_from", ""),
                    "target_url": item.get("url_to", ""),
                    "anchor_text": item.get("anchor", ""),
                    "is_dofollow": item.get("dofollow", True),
                    "domain_rating": item.get("rank", 0),
                    "spam_score": item.get("spam_score", 0),
                    "toxicity_score": 0,
                    "status": "live",
                    "first_seen": item.get("first_seen"),
                    "last_seen": item.get("last_seen"),
                })
    return items


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_backlinks(domain: str, limit: int = 150) -> list[dict]:
    if settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_PASSWORD:
        try:
            return await _dataforseo_backlinks(domain, limit)
        except Exception as e:
            logger.warning("DataForSEO backlinks failed, using mock", error=str(e))
    return _mock_backlinks(domain, count=min(limit, 150))


async def fetch_competitor_backlinks(competitor_domain: str, limit: int = 100) -> list[dict]:
    return _mock_backlinks(competitor_domain, count=limit, is_competitor=True)


def get_profile(domain: str) -> dict:
    return _mock_profile(domain)


def compute_gap(own_backlinks: list[dict], competitor_backlinks: list[dict]) -> list[str]:
    own_domains = {b["source_domain"] for b in own_backlinks}
    comp_domains = {b["source_domain"] for b in competitor_backlinks}
    return _backlink_gap(own_domains, comp_domains)


def get_disavow_candidates(backlinks: list[dict], threshold: int = 60) -> list[dict]:
    return [b for b in backlinks if b.get("toxicity_score", 0) >= threshold]


def generate_disavow_txt(backlinks: list[dict]) -> str:
    lines = ["# Disavow file generated by RankForge", "# Remove links you do not want Google to consider", ""]
    for b in backlinks:
        lines.append(f"domain:{b['source_domain']}")
    return "\n".join(lines)


def anchor_text_distribution(backlinks: list[dict]) -> list[dict]:
    anchors: dict[str, int] = {}
    for b in backlinks:
        a = (b.get("anchor_text") or "").strip().lower() or "(empty)"
        anchors[a] = anchors.get(a, 0) + 1
    total = sum(anchors.values()) or 1
    return sorted(
        [{"anchor": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in anchors.items()],
        key=lambda x: x["count"], reverse=True
    )[:20]
