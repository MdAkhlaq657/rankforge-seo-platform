"""
Rank tracking service.
Checks SERP positions for tracked keywords. Uses DataForSEO or mock.
"""
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


# ── Mock rank engine ──────────────────────────────────────────────────────────

def _mock_position(keyword: str, domain: str, date: datetime) -> Optional[int]:
    """Simulate a realistic rank that slowly moves over time."""
    seed = int(hashlib.md5(f"{keyword}{domain}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Base position (some keywords rank, some don't)
    in_top_100 = rng.random() > 0.25
    if not in_top_100:
        return None

    base_pos = rng.randint(1, 80)

    # Add time-based drift (±3 positions per week, simulates movement)
    days_since_epoch = (date - datetime(2024, 1, 1, tzinfo=timezone.utc)).days
    drift_seed = int(hashlib.md5(f"{keyword}{domain}{days_since_epoch // 7}".encode()).hexdigest()[:4], 16)
    drift = random.Random(drift_seed).randint(-3, 3)

    position = max(1, min(100, base_pos + drift))
    return position


def _mock_ranking_url(keyword: str, domain: str, position: Optional[int]) -> Optional[str]:
    if position is None:
        return None
    rng = random.Random(int(hashlib.md5(f"{keyword}{domain}".encode()).hexdigest()[:6], 16))
    paths = ["/", "/blog/", "/services/", "/products/", f"/{keyword.replace(' ', '-')}/"]
    return f"https://{domain}{rng.choice(paths)}"


def _mock_serp_features(keyword: str) -> list[str]:
    rng = random.Random(int(hashlib.md5(keyword.encode()).hexdigest()[:6], 16))
    possible = ["featured_snippet", "paa", "local_pack", "shopping", "image_pack"]
    count = rng.randint(0, 3)
    return rng.sample(possible, k=min(count, len(possible)))


# ── DataForSEO SERP rank check ────────────────────────────────────────────────

async def _dataforseo_rank_check(
    keyword: str,
    domain: str,
    location_code: int = 2840,
    device: str = "desktop",
) -> dict:
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    payload = [{
        "keyword": keyword,
        "location_code": location_code,
        "language_code": "en",
        "device": device,
        "depth": 100,
        "domain": domain,
    }]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            auth=(settings.DATAFORSEO_LOGIN, settings.DATAFORSEO_PASSWORD),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    position = None
    ranking_url = None
    serp_features = []

    for task in data.get("tasks", []):
        for result in task.get("result", []):
            for item in result.get("items", []):
                itype = item.get("type")
                if itype in ("featured_snippet", "paa", "local_pack", "shopping", "image_pack"):
                    serp_features.append(itype)
                if itype == "organic" and domain in item.get("domain", ""):
                    if position is None:
                        position = item.get("rank_absolute")
                        ranking_url = item.get("url")

    return {
        "position": position,
        "url": ranking_url,
        "serp_features": list(set(serp_features)),
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def check_rank(
    keyword: str,
    domain: str,
    device: str = "desktop",
    locale: str = "en-US",
    date: Optional[datetime] = None,
) -> dict:
    """Check ranking for a single keyword. Returns position data."""
    if date is None:
        date = datetime.now(timezone.utc)

    if settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_PASSWORD:
        try:
            return await _dataforseo_rank_check(keyword, domain, device=device)
        except Exception as e:
            logger.warning("DataForSEO rank check failed, using mock", error=str(e))

    # Mock
    position = _mock_position(keyword, domain, date)
    return {
        "position": position,
        "url": _mock_ranking_url(keyword, domain, position),
        "serp_features": _mock_serp_features(keyword),
    }


async def check_ranks_bulk(
    keywords: list[dict],  # [{keyword_id, keyword, domain}]
    device: str = "desktop",
) -> list[dict]:
    """Check ranks for multiple keywords. Returns list of rank data."""
    import asyncio
    results = []
    now = datetime.now(timezone.utc)

    async def check_one(kw_data: dict) -> dict:
        result = await check_rank(kw_data["keyword"], kw_data["domain"], device=device, date=now)
        return {**kw_data, **result, "checked_at": now}

    # Run in batches of 5 to avoid hammering API
    batch_size = 5
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]
        batch_results = await asyncio.gather(*[check_one(k) for k in batch])
        results.extend(batch_results)

    return results


def build_sparkline(rank_history: list[dict], days: int = 30) -> list[Optional[int]]:
    """Convert rank history records to a sparkline array (oldest → newest)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    filtered = [r for r in rank_history if r["checked_at"] >= cutoff]
    filtered.sort(key=lambda x: x["checked_at"])
    return [r["position"] for r in filtered]
