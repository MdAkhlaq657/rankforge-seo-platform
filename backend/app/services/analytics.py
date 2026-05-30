"""
Predictive analytics service.
- Keyword cannibalization detection using cluster + rank overlap
- ROI forecasting using GSC CTR curves + keyword volume
- Traffic forecasting (simple trend extrapolation)
"""
import math
from datetime import datetime, timezone, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger()

# ── CTR curve by position (from industry studies) ────────────────────────────
# Average organic CTR by SERP position
CTR_BY_POSITION = {
    1: 0.278, 2: 0.155, 3: 0.114, 4: 0.082, 5: 0.063,
    6: 0.050, 7: 0.040, 8: 0.032, 9: 0.026, 10: 0.021,
    11: 0.015, 12: 0.012, 13: 0.010, 14: 0.009, 15: 0.008,
    20: 0.005, 30: 0.003, 50: 0.002,
}


def get_ctr(position: int) -> float:
    """Interpolated CTR for a given position."""
    if position in CTR_BY_POSITION:
        return CTR_BY_POSITION[position]
    positions = sorted(CTR_BY_POSITION.keys())
    for i in range(len(positions) - 1):
        lo, hi = positions[i], positions[i + 1]
        if lo <= position <= hi:
            ratio = (position - lo) / (hi - lo)
            return CTR_BY_POSITION[lo] + ratio * (CTR_BY_POSITION[hi] - CTR_BY_POSITION[lo])
    return 0.001


# ── Cannibalization detection ─────────────────────────────────────────────────

def detect_cannibalization(
    keywords: list[dict],    # [{keyword, cluster_id, current_position, best_url}]
    rank_threshold: int = 20,
) -> list[dict]:
    """
    Find clusters where 2+ pages compete for the same keyword group.
    Returns list of cannibalization issue dicts.
    """
    from collections import defaultdict

    # Group tracked keywords by cluster
    cluster_keywords: dict[str, list] = defaultdict(list)
    for kw in keywords:
        if kw.get("cluster_id") and kw.get("current_position"):
            if kw["current_position"] <= rank_threshold:
                cluster_keywords[kw["cluster_id"]].append(kw)

    issues = []
    for cluster_id, kws in cluster_keywords.items():
        # Find unique ranking URLs for this cluster
        urls_in_cluster = {}
        for kw in kws:
            url = kw.get("best_url") or ""
            if url:
                if url not in urls_in_cluster:
                    urls_in_cluster[url] = []
                urls_in_cluster[url].append(kw["keyword"])

        if len(urls_in_cluster) >= 2:
            # Cannibalization: multiple URLs competing in same cluster
            competing_urls = [
                {
                    "url": url,
                    "keywords": kw_list,
                    "avg_position": sum(
                        k["current_position"] for k in kws if k.get("best_url") == url
                    ) / max(len(kw_list), 1),
                }
                for url, kw_list in urls_in_cluster.items()
            ]

            # Severity: how many keywords, how close the positions
            total_kws = sum(len(u["keywords"]) for u in competing_urls)
            severity = "high" if total_kws >= 5 else "medium" if total_kws >= 3 else "low"

            # Recommendation
            positions = [u["avg_position"] for u in competing_urls]
            if max(positions) - min(positions) < 5:
                recommendation = "consolidate"
            elif len(set(u["url"].split("/")[2] for u in competing_urls)) == 1:
                recommendation = "canonicalize"
            else:
                recommendation = "differentiate"

            representative_keyword = kws[0]["keyword"] if kws else cluster_id
            issues.append({
                "keyword": representative_keyword,
                "cluster_id": cluster_id,
                "competing_urls": competing_urls,
                "recommendation": recommendation,
                "severity": severity,
                "affected_keywords": total_kws,
            })

    return sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])


# ── ROI / Traffic forecasting ─────────────────────────────────────────────────

def forecast_keyword_opportunity(
    keyword: str,
    search_volume: int,
    current_position: Optional[int],
    avg_conversion_rate: float = 0.02,   # 2% default
    avg_order_value: float = 50.0,       # $50 default
) -> dict:
    """
    Forecast traffic and revenue potential for position improvements.
    Returns projections for positions 1, 3, 5, 10.
    """
    projections = []
    for target_pos in [1, 3, 5, 10]:
        ctr = get_ctr(target_pos)
        monthly_clicks = int(search_volume * ctr)
        monthly_conversions = int(monthly_clicks * avg_conversion_rate)
        monthly_revenue = monthly_conversions * avg_order_value

        current_clicks = 0
        if current_position:
            current_ctr = get_ctr(current_position)
            current_clicks = int(search_volume * current_ctr)

        projections.append({
            "position": target_pos,
            "ctr": round(ctr * 100, 1),
            "monthly_clicks": monthly_clicks,
            "click_uplift": monthly_clicks - current_clicks,
            "monthly_conversions": monthly_conversions,
            "monthly_revenue": round(monthly_revenue, 2),
            "is_current": current_position == target_pos,
        })

    opportunity_value = projections[0]["monthly_revenue"] - (
        int(search_volume * get_ctr(current_position) * avg_conversion_rate * avg_order_value)
        if current_position else 0
    )

    return {
        "keyword": keyword,
        "search_volume": search_volume,
        "current_position": current_position,
        "projections": projections,
        "opportunity_value": round(opportunity_value, 2),
    }


def forecast_traffic_trend(
    gsc_daily: list[dict],   # [{date, clicks, impressions}]
    forecast_days: int = 90,
) -> dict:
    """
    Simple linear regression on recent traffic to forecast future trend.
    Returns {historical, forecast, trend_direction, confidence}.
    """
    if len(gsc_daily) < 14:
        return {"error": "Need at least 14 days of data", "historical": gsc_daily}

    # Use last 90 days for regression
    recent = sorted(gsc_daily, key=lambda x: x["date"])[-90:]
    n = len(recent)
    xs = list(range(n))
    ys = [d["clicks"] for d in recent]

    # Simple linear regression
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))
    slope = numerator / denominator if denominator != 0 else 0
    intercept = mean_y - slope * mean_x

    # R² for confidence
    ss_res = sum((ys[i] - (slope * xs[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r_squared = max(0, 1 - ss_res / ss_tot) if ss_tot != 0 else 0

    # Generate forecast
    from datetime import date
    last_date = datetime.strptime(recent[-1]["date"], "%Y-%m-%d")
    forecast_points = []
    for i in range(1, forecast_days + 1):
        pred_date = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
        pred_clicks = max(0, int(slope * (n + i) + intercept))
        # Add slight weekly seasonality
        day_of_week = (last_date + timedelta(days=i)).weekday()
        seasonality = 1.1 if day_of_week < 5 else 0.7
        forecast_points.append({
            "date": pred_date,
            "clicks": int(pred_clicks * seasonality),
            "is_forecast": True,
        })

    trend = "rising" if slope > 0.5 else "falling" if slope < -0.5 else "stable"
    confidence = round(r_squared * 100, 1)

    return {
        "historical": recent,
        "forecast": forecast_points,
        "slope": round(slope, 3),
        "trend_direction": trend,
        "confidence": confidence,
        "forecast_30d_clicks": sum(p["clicks"] for p in forecast_points[:30]),
        "forecast_90d_clicks": sum(p["clicks"] for p in forecast_points[:90]),
    }


def compute_keyword_roi_table(
    keywords: list[dict],  # [{keyword, search_volume, current_position}]
    conversion_rate: float = 0.02,
    order_value: float = 50.0,
) -> list[dict]:
    """Compute opportunity value for all tracked keywords. Sorted by value."""
    results = []
    for kw in keywords:
        if not kw.get("search_volume"):
            continue
        opp = forecast_keyword_opportunity(
            kw["keyword"],
            kw["search_volume"],
            kw.get("current_position"),
            conversion_rate,
            order_value,
        )
        results.append({
            "keyword": kw["keyword"],
            "search_volume": kw["search_volume"],
            "current_position": kw.get("current_position"),
            "opportunity_value": opp["opportunity_value"],
            "top1_monthly_revenue": opp["projections"][0]["monthly_revenue"],
            "top1_monthly_clicks": opp["projections"][0]["monthly_clicks"],
        })
    return sorted(results, key=lambda x: x["opportunity_value"], reverse=True)
