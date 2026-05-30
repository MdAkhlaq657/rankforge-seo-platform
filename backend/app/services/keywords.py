"""
Keyword research service.
Uses DataForSEO when credentials are configured, falls back to rich mock data.
"""
import random
import hashlib
from typing import Optional
import httpx
from app.config import settings


# ── Mock data engine ──────────────────────────────────────────────────────────

INTENT_WORDS = {
    "how": "informational", "what": "informational", "why": "informational",
    "guide": "informational", "tutorial": "informational", "learn": "informational",
    "vs": "commercial", "best": "commercial", "top": "commercial",
    "review": "commercial", "compare": "commercial", "alternative": "commercial",
    "buy": "transactional", "price": "transactional", "cheap": "transactional",
    "discount": "transactional", "order": "transactional", "shop": "transactional",
}

SERP_FEATURES = ["featured_snippet", "paa", "local_pack", "knowledge_panel",
                 "shopping", "image_pack", "video", "top_stories"]

PAA_TEMPLATES = [
    "What is {keyword}?",
    "How does {keyword} work?",
    "Why is {keyword} important?",
    "What are the benefits of {keyword}?",
    "How to get started with {keyword}?",
    "What is the best {keyword} tool?",
    "How much does {keyword} cost?",
    "Is {keyword} worth it?",
    "What are the alternatives to {keyword}?",
    "How to improve {keyword}?",
]


def _seed(keyword: str) -> int:
    return int(hashlib.md5(keyword.encode()).hexdigest()[:8], 16)


def _mock_keyword_data(keyword: str) -> dict:
    s = _seed(keyword)
    rng = random.Random(s)

    # Volume — logarithmic distribution (most keywords are low volume)
    volume_tiers = [
        (0.35, (10, 100)),
        (0.30, (100, 1000)),
        (0.20, (1000, 10000)),
        (0.10, (10000, 100000)),
        (0.05, (100000, 500000)),
    ]
    r = rng.random()
    cumulative = 0
    for prob, (lo, hi) in volume_tiers:
        cumulative += prob
        if r <= cumulative:
            volume = rng.randint(lo, hi)
            break
    else:
        volume = rng.randint(100, 5000)

    kd = rng.randint(5, 90)
    cpc = round(rng.uniform(0.10, 45.0), 2)
    competition = round(rng.uniform(0.0, 1.0), 2)

    # Intent detection from keyword words
    intent = "informational"
    for word, detected_intent in INTENT_WORDS.items():
        if word in keyword.lower():
            intent = detected_intent
            break

    # SERP features (subset, more features for high-volume)
    feature_count = min(4, 1 + int(volume / 10000))
    features = rng.sample(SERP_FEATURES, k=min(feature_count, len(SERP_FEATURES)))

    # Keyword difficulty colour hints
    trend = rng.choice(["stable", "rising", "falling", "seasonal"])

    return {
        "keyword": keyword,
        "search_volume": volume,
        "keyword_difficulty": kd,
        "cpc": cpc,
        "competition": competition,
        "intent": intent,
        "serp_features": features,
        "trend": trend,
        "source": "mock",
    }


def _mock_paa(keyword: str, count: int = 8) -> list[dict]:
    rng = random.Random(_seed(keyword))
    questions = rng.sample(PAA_TEMPLATES, k=min(count, len(PAA_TEMPLATES)))
    return [
        {
            "question": q.format(keyword=keyword),
            "answer_snippet": f"This is a mock answer snippet for '{q.format(keyword=keyword)}'.",
            "depth": 0,
        }
        for q in questions
    ]


def _mock_related_keywords(seed_keyword: str, count: int = 20) -> list[dict]:
    """Generate realistic-looking related keyword suggestions."""
    modifiers = [
        "best", "top", "free", "online", "tool", "software", "guide",
        "tutorial", "tips", "examples", "for beginners", "vs",
        "how to", "what is", "cost", "price", "review",
    ]
    rng = random.Random(_seed(seed_keyword))
    selected = rng.sample(modifiers, k=min(count, len(modifiers)))
    results = []
    for mod in selected:
        kw = f"{mod} {seed_keyword}" if rng.random() > 0.5 else f"{seed_keyword} {mod}"
        results.append(_mock_keyword_data(kw.strip()))
    return results


# ── DataForSEO client ─────────────────────────────────────────────────────────

async def _dataforseo_keywords(keywords: list[str], location_code: int = 2840) -> list[dict]:
    """Call DataForSEO Keywords Data API."""
    url = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
    payload = [{"keywords": keywords, "location_code": location_code, "language_code": "en"}]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            auth=(settings.DATAFORSEO_LOGIN, settings.DATAFORSEO_PASSWORD),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for task in data.get("tasks", []):
        for item in task.get("result", []):
            kw = item.get("keyword", "")
            results.append({
                "keyword": kw,
                "search_volume": item.get("search_volume", 0),
                "keyword_difficulty": item.get("keyword_difficulty", 0),
                "cpc": item.get("cpc", 0),
                "competition": item.get("competition", 0),
                "intent": item.get("search_intent", "unknown"),
                "serp_features": [],
                "trend": "stable",
                "source": "dataforseo",
            })
    return results


async def _dataforseo_serp(keyword: str, location_code: int = 2840) -> dict:
    """Fetch SERP including PAA via DataForSEO."""
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    payload = [{"keyword": keyword, "location_code": location_code, "language_code": "en", "depth": 10}]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            auth=(settings.DATAFORSEO_LOGIN, settings.DATAFORSEO_PASSWORD),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    paa = []
    organic = []
    for task in data.get("tasks", []):
        for result in task.get("result", []):
            for item in result.get("items", []):
                if item.get("type") == "people_also_ask":
                    for q in item.get("items", []):
                        paa.append({
                            "question": q.get("title", ""),
                            "answer_snippet": q.get("description", ""),
                            "depth": 0,
                        })
                elif item.get("type") == "organic":
                    organic.append({
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "position": item.get("rank_absolute", 0),
                    })
    return {"paa": paa, "organic_results": organic}


# ── Public API ────────────────────────────────────────────────────────────────

def has_dataforseo() -> bool:
    return bool(settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_PASSWORD)


async def get_keyword_data(keywords: list[str]) -> list[dict]:
    if has_dataforseo():
        try:
            return await _dataforseo_keywords(keywords)
        except Exception:
            pass
    return [_mock_keyword_data(kw) for kw in keywords]


async def get_related_keywords(seed_keyword: str, count: int = 20) -> list[dict]:
    if has_dataforseo():
        try:
            related_kws = [f"{m} {seed_keyword}" for m in
                           ["best", "top", "free", "guide", "tool", "how to", "vs", "cost"]]
            return await _dataforseo_keywords(related_kws)
        except Exception:
            pass
    return _mock_related_keywords(seed_keyword, count)


async def get_serp_data(keyword: str) -> dict:
    if has_dataforseo():
        try:
            return await _dataforseo_serp(keyword)
        except Exception:
            pass
    paa = _mock_paa(keyword)
    # Mock top 10 organic results
    rng = random.Random(_seed(keyword))
    organic = [
        {
            "url": f"https://example{i}.com/{keyword.replace(' ', '-')}",
            "title": f"{keyword.title()} — Complete Guide {i+1}",
            "position": i + 1,
        }
        for i in range(10)
    ]
    return {"paa": paa, "organic_results": organic}
