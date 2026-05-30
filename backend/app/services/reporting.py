"""
PDF report generation service.
Jinja2 HTML template → WeasyPrint → PDF bytes.
"""
import os
from datetime import datetime, timezone
from typing import Optional
import structlog

logger = structlog.get_logger()

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False

try:
    from jinja2 import Environment, BaseLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


# ── HTML Report template ──────────────────────────────────────────────────────

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 13px; color: #111827; line-height: 1.6; }
  .page { padding: 48px 56px; }
  .header { border-bottom: 2px solid #4f46e5; padding-bottom: 24px; margin-bottom: 32px; }
  .logo { font-size: 22px; font-weight: 700; color: #4f46e5; }
  .report-title { font-size: 28px; font-weight: 700; color: #111827; margin-top: 12px; }
  .report-meta { color: #6b7280; font-size: 12px; margin-top: 4px; }
  .section { margin-bottom: 36px; page-break-inside: avoid; }
  .section-title { font-size: 18px; font-weight: 600; color: #111827; border-left: 4px solid #4f46e5; padding-left: 12px; margin-bottom: 16px; }
  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: #f8f9fb; border-radius: 8px; padding: 16px; border: 1px solid #e5e7eb; }
  .stat-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; font-weight: 500; }
  .stat-value { font-size: 28px; font-weight: 700; color: #111827; margin-top: 4px; }
  .stat-sub { font-size: 11px; color: #9ca3af; margin-top: 2px; }
  .score-circle { width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 26px; font-weight: 700; margin: 0 auto; }
  .score-good { background: #dcfce7; color: #16a34a; }
  .score-ok   { background: #fef3c7; color: #d97706; }
  .score-poor { background: #fee2e2; color: #dc2626; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th { background: #f3f4f6; text-align: left; padding: 8px 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #6b7280; }
  td { padding: 8px 12px; border-bottom: 1px solid #f3f4f6; font-size: 12px; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 500; }
  .badge-red    { background: #fee2e2; color: #dc2626; }
  .badge-amber  { background: #fef3c7; color: #d97706; }
  .badge-blue   { background: #dbeafe; color: #2563eb; }
  .badge-green  { background: #dcfce7; color: #16a34a; }
  .footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 11px; display: flex; justify-content: space-between; }
  .summary-box { background: #eef2ff; border-left: 4px solid #4f46e5; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-bottom: 24px; }
  .cwv-row { display: flex; gap: 16px; margin-bottom: 16px; }
  .cwv-pill { flex: 1; padding: 10px 14px; border-radius: 8px; font-size: 12px; }
  .cwv-good   { background: #dcfce7; color: #16a34a; }
  .cwv-warn   { background: #fef3c7; color: #d97706; }
  .cwv-poor   { background: #fee2e2; color: #dc2626; }
  @page { margin: 0; size: A4; }
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="header">
    <div class="logo">RankForge</div>
    <div class="report-title">{{ project_name }} — SEO Report</div>
    <div class="report-meta">
      Period: {{ period_start }} to {{ period_end }} &nbsp;·&nbsp;
      Generated: {{ generated_at }} &nbsp;·&nbsp;
      Domain: {{ domain }}
    </div>
  </div>

  <!-- Executive Summary -->
  <div class="section">
    <div class="section-title">Executive Summary</div>
    <div class="summary-box">{{ executive_summary }}</div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Health Score</div>
        <div class="stat-value" style="color: {% if health_score >= 80 %}#16a34a{% elif health_score >= 50 %}#d97706{% else %}#dc2626{% endif %}">{{ health_score }}</div>
        <div class="stat-sub">out of 100</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Pages Crawled</div>
        <div class="stat-value">{{ pages_crawled }}</div>
        <div class="stat-sub">{{ open_issues }} open issues</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Organic Clicks</div>
        <div class="stat-value">{{ total_clicks }}</div>
        <div class="stat-sub">from Search Console</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg. Position</div>
        <div class="stat-value">{{ avg_position }}</div>
        <div class="stat-sub">across tracked keywords</div>
      </div>
    </div>
  </div>

  <!-- Core Web Vitals -->
  <div class="section">
    <div class="section-title">Core Web Vitals</div>
    <div class="cwv-row">
      <div class="cwv-pill {{ lcp_class }}">
        <strong>LCP</strong> {{ avg_lcp }}s &nbsp;
        <span style="opacity:0.7">Largest Contentful Paint (good: &lt;2.5s)</span>
      </div>
      <div class="cwv-pill {{ cls_class }}">
        <strong>CLS</strong> {{ avg_cls }} &nbsp;
        <span style="opacity:0.7">Cumulative Layout Shift (good: &lt;0.1)</span>
      </div>
      <div class="cwv-pill {{ inp_class }}">
        <strong>INP</strong> {{ avg_inp }}ms &nbsp;
        <span style="opacity:0.7">Interaction to Next Paint (good: &lt;200ms)</span>
      </div>
    </div>
  </div>

  <!-- Top Issues -->
  <div class="section">
    <div class="section-title">Top Issues to Fix</div>
    <table>
      <thead><tr><th>Severity</th><th>Issue</th><th>Affected URL</th><th>Effort</th></tr></thead>
      <tbody>
      {% for issue in top_issues %}
        <tr>
          <td><span class="badge {% if issue.severity == 'p1' %}badge-red{% elif issue.severity == 'p2' %}badge-amber{% else %}badge-blue{% endif %}">{{ issue.severity.upper() }}</span></td>
          <td>{{ issue.title }}</td>
          <td style="font-family: monospace; font-size: 11px; color: #6b7280;">{{ issue.affected_url[:60] }}{% if issue.affected_url|length > 60 %}…{% endif %}</td>
          <td>{{ issue.fix_difficulty }}</td>
        </tr>
      {% else %}
        <tr><td colspan="4" style="text-align:center; color:#9ca3af;">No issues found</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <!-- Keyword Rankings -->
  {% if keyword_rankings %}
  <div class="section">
    <div class="section-title">Keyword Rankings</div>
    <table>
      <thead><tr><th>Keyword</th><th>Position</th><th>Volume</th><th>Intent</th></tr></thead>
      <tbody>
      {% for kw in keyword_rankings[:15] %}
        <tr>
          <td>{{ kw.keyword }}</td>
          <td>{% if kw.position %}<strong>{{ kw.position }}</strong>{% else %}<span style="color:#9ca3af">Not ranking</span>{% endif %}</td>
          <td>{{ "{:,}".format(kw.search_volume or 0) }}</td>
          <td><span class="badge badge-blue">{{ kw.intent }}</span></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- GSC Performance -->
  {% if gsc_summary %}
  <div class="section">
    <div class="section-title">Search Console Performance</div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Clicks</div>
        <div class="stat-value">{{ gsc_summary.total_clicks }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Impressions</div>
        <div class="stat-value">{{ gsc_summary.total_impressions }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg. CTR</div>
        <div class="stat-value">{{ gsc_summary.avg_ctr }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg. Position</div>
        <div class="stat-value">{{ gsc_summary.avg_position }}</div>
      </div>
    </div>
  </div>
  {% endif %}

  <!-- Footer -->
  <div class="footer">
    <span>Generated by RankForge &nbsp;·&nbsp; rankforge.io</span>
    <span>{{ project_name }} &nbsp;·&nbsp; {{ generated_at }}</span>
  </div>

</div>
</body>
</html>"""


# ── Report data helpers ───────────────────────────────────────────────────────

def _cwv_class(metric: str, value: float) -> str:
    thresholds = {
        "lcp": (2.5, 4.0),
        "cls": (0.1, 0.25),
        "inp": (200, 500),
    }
    good, poor = thresholds.get(metric, (0, 0))
    if value <= good: return "cwv-good"
    if value <= poor: return "cwv-warn"
    return "cwv-poor"


def _executive_summary(data: dict) -> str:
    score = data.get("health_score", 0)
    issues = data.get("open_issues", 0)
    pages = data.get("pages_crawled", 0)
    clicks = data.get("total_clicks", 0)
    period = f"{data.get('period_start', '')} to {data.get('period_end', '')}"

    quality = "strong" if score >= 80 else "moderate" if score >= 50 else "weak"
    return (
        f"During {period}, {data.get('project_name', 'this site')} achieved a site health score of "
        f"{score}/100, indicating {quality} technical SEO health. "
        f"The crawl analyzed {pages:,} pages and identified {issues:,} open issues requiring attention. "
        f"The site received {clicks:,} organic clicks from Google Search during the period. "
        f"{'Priority attention is needed for critical P1 issues.' if issues > 20 else 'The team has made good progress on resolving technical issues.'}"
    )


# ── Main generate function ────────────────────────────────────────────────────

async def generate_report_pdf(report_data: dict) -> bytes:
    """
    Generate a PDF report from structured data.
    Returns PDF bytes. Falls back to HTML bytes if WeasyPrint not available.
    """
    if not JINJA2_AVAILABLE:
        raise RuntimeError("Jinja2 not installed")

    env = Environment(loader=BaseLoader())
    template = env.from_string(REPORT_TEMPLATE)

    # Build template context
    avg_lcp = report_data.get("cwv_summary", {}).get("avg_lcp", 0)
    avg_cls = report_data.get("cwv_summary", {}).get("avg_cls", 0)
    avg_inp = report_data.get("cwv_summary", {}).get("avg_inp", 0)

    ctx = {
        "project_name": report_data.get("project_name", "Project"),
        "domain": report_data.get("domain", ""),
        "period_start": report_data.get("period_start", ""),
        "period_end": report_data.get("period_end", ""),
        "generated_at": datetime.now(timezone.utc).strftime("%d %b %Y"),
        "health_score": report_data.get("health_score", 0),
        "pages_crawled": f"{report_data.get('pages_crawled', 0):,}",
        "open_issues": f"{report_data.get('open_issues', 0):,}",
        "total_clicks": f"{report_data.get('total_clicks', 0):,}",
        "avg_position": report_data.get("avg_position", "—"),
        "avg_lcp": avg_lcp,
        "avg_cls": avg_cls,
        "avg_inp": avg_inp,
        "lcp_class": _cwv_class("lcp", avg_lcp),
        "cls_class": _cwv_class("cls", avg_cls),
        "inp_class": _cwv_class("inp", avg_inp),
        "top_issues": report_data.get("top_issues", [])[:10],
        "keyword_rankings": report_data.get("keyword_rankings", []),
        "gsc_summary": report_data.get("gsc_summary"),
        "executive_summary": report_data.get("executive_summary") or _executive_summary(report_data),
    }

    html_content = template.render(**ctx)

    if WEASYPRINT_AVAILABLE:
        try:
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        except Exception as e:
            logger.error("WeasyPrint failed, returning HTML", error=str(e))

    return html_content.encode("utf-8")
