"""
Google Search Console and GA4 integration service.
OAuth2 flow + data fetching. Falls back to mock data if not connected.
"""
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger()

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from app.config import settings


SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def get_oauth_url(state: str) -> str:
    """Generate Google OAuth URL."""
    if not GOOGLE_AVAILABLE:
        return ""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": getattr(settings, "GOOGLE_CLIENT_ID", ""),
                "client_secret": getattr(settings, "GOOGLE_CLIENT_SECRET", ""),
                "redirect_uris": [getattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/oauth/callback")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = getattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/oauth/callback")
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    return auth_url


def exchange_code(code: str) -> dict:
    """Exchange OAuth code for tokens."""
    if not GOOGLE_AVAILABLE:
        return {}
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": getattr(settings, "GOOGLE_CLIENT_ID", ""),
                "client_secret": getattr(settings, "GOOGLE_CLIENT_SECRET", ""),
                "redirect_uris": [getattr(settings, "GOOGLE_REDIRECT_URI", "")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = getattr(settings, "GOOGLE_REDIRECT_URI", "")
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


# ── GSC data fetching ─────────────────────────────────────────────────────────

def _get_gsc_service(access_token: str, refresh_token: str):
    if not GOOGLE_AVAILABLE:
        return None
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=getattr(settings, "GOOGLE_CLIENT_ID", ""),
        client_secret=getattr(settings, "GOOGLE_CLIENT_SECRET", ""),
        token_uri="https://oauth2.googleapis.com/token",
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("searchconsole", "v1", credentials=creds)


async def fetch_gsc_data(
    property_id: str,
    access_token: str,
    refresh_token: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] = None,
    row_limit: int = 500,
) -> list[dict]:
    """Fetch Search Console performance data."""
    dimensions = dimensions or ["query", "page", "date"]
    service = _get_gsc_service(access_token, refresh_token)
    if not service:
        return _mock_gsc_data(property_id, start_date, end_date)

    try:
        request = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": row_limit,
        }
        response = service.searchanalytics().query(
            siteUrl=property_id, body=request
        ).execute()
        rows = response.get("rows", [])
        results = []
        for row in rows:
            keys = row.get("keys", [])
            result = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }
            for i, dim in enumerate(dimensions):
                if i < len(keys):
                    result[dim] = keys[i]
            results.append(result)
        return results
    except Exception as e:
        logger.error("GSC fetch failed", error=str(e))
        return _mock_gsc_data(property_id, start_date, end_date)


# ── Mock GSC data ─────────────────────────────────────────────────────────────

def _mock_gsc_data(property_id: str, start_date: str, end_date: str) -> list[dict]:
    seed = int(hashlib.md5(property_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1

    keywords = [
        "seo tools", "keyword research", "technical seo", "backlink checker",
        "rank tracker", "site audit", "on page seo", "link building",
        "content optimization", "serp analysis", "competitor analysis",
    ]

    results = []
    for day_offset in range(days):
        date = (start + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        # Daily totals (with realistic growth trend)
        growth_factor = 1 + (day_offset / max(days, 1)) * 0.15
        base_clicks = int(rng.randint(80, 400) * growth_factor)

        for kw in rng.sample(keywords, k=rng.randint(3, 7)):
            clicks = max(0, int(rng.gauss(base_clicks / 7, base_clicks / 14)))
            impressions = max(clicks, clicks * rng.randint(5, 40))
            position = round(rng.uniform(1.5, 45.0), 1)
            ctr = round((clicks / impressions * 100) if impressions > 0 else 0, 2)
            results.append({
                "query": kw,
                "page": f"https://{property_id.replace('sc-domain:', '')}/blog/{kw.replace(' ', '-')}/",
                "date": date,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": ctr,
                "position": position,
            })

    return results


def aggregate_gsc_by_day(rows: list[dict]) -> list[dict]:
    """Aggregate GSC rows by date for time-series charts."""
    by_date: dict[str, dict] = {}
    for row in rows:
        date = row.get("date", "")
        if date not in by_date:
            by_date[date] = {"date": date, "clicks": 0, "impressions": 0, "position_sum": 0, "count": 0}
        by_date[date]["clicks"] += row.get("clicks", 0)
        by_date[date]["impressions"] += row.get("impressions", 0)
        by_date[date]["position_sum"] += row.get("position", 0)
        by_date[date]["count"] += 1

    result = []
    for date, data in sorted(by_date.items()):
        avg_pos = round(data["position_sum"] / data["count"], 1) if data["count"] else 0
        ctr = round(data["clicks"] / data["impressions"] * 100, 2) if data["impressions"] > 0 else 0
        result.append({
            "date": date,
            "clicks": data["clicks"],
            "impressions": data["impressions"],
            "avg_position": avg_pos,
            "ctr": ctr,
        })
    return result
