"""
AI Content Writer service.
Pipeline: Keyword → SERP scrape → Competitor analysis → Brief → Article.
Uses Anthropic Claude API.
"""
import asyncio
import json
from typing import Optional, AsyncGenerator
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=getattr(settings, "ANTHROPIC_API_KEY", ""))
    ANTHROPIC_AVAILABLE = bool(getattr(settings, "ANTHROPIC_API_KEY", ""))
except Exception:
    _client = None
    ANTHROPIC_AVAILABLE = False


# ── Competitor content scraping ───────────────────────────────────────────────

async def scrape_competitor_content(urls: list[str]) -> list[dict]:
    """Extract text + structure from top-ranking URLs."""
    try:
        import trafilatura
    except ImportError:
        return []

    async def scrape_one(url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "SEOBot/1.0"})
                resp.raise_for_status()
            text = trafilatura.extract(
                resp.text, include_comments=False,
                include_tables=True, no_fallback=False
            ) or ""
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            headings = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3"])[:15]]
            word_count = len(text.split())
            return {
                "url": url,
                "text": text[:8000],
                "headings": headings,
                "word_count": word_count,
            }
        except Exception as e:
            logger.debug("scrape_one failed", url=url, error=str(e))
            return {"url": url, "text": "", "headings": [], "word_count": 0}

    results = await asyncio.gather(*[scrape_one(u) for u in urls[:5]])
    return [r for r in results if r["word_count"] > 100]


# ── Content brief generation ──────────────────────────────────────────────────

def _build_brief_prompt(
    keyword: str,
    paa_questions: list[str],
    competitor_data: list[dict],
    serp_features: list[str],
) -> str:
    comp_summary = ""
    for i, c in enumerate(competitor_data[:3], 1):
        comp_summary += f"\nCompetitor {i} ({c['url']}, {c['word_count']} words):\n"
        if c.get("headings"):
            comp_summary += "Headings: " + " | ".join(c["headings"][:8]) + "\n"

    paa_str = "\n".join(f"- {q}" for q in paa_questions[:10]) if paa_questions else "None found"
    features_str = ", ".join(serp_features) if serp_features else "standard results"

    return f"""You are an expert SEO content strategist. Analyze the data below and generate a comprehensive content brief.

TARGET KEYWORD: {keyword}
SERP FEATURES PRESENT: {features_str}

PEOPLE ALSO ASK QUESTIONS:
{paa_str}

COMPETITOR ANALYSIS:
{comp_summary}

Generate a JSON content brief with this exact structure:
{{
  "recommended_title": "...",
  "meta_description": "...",
  "recommended_word_count": 1500,
  "content_angle": "...",
  "outline": [
    {{"heading": "H2 heading", "subheadings": ["H3 sub 1", "H3 sub 2"], "key_points": ["..."]}}
  ],
  "entities_to_include": ["..."],
  "questions_to_answer": ["..."],
  "internal_links_to_include": [],
  "writing_notes": "..."
}}

Return ONLY the JSON object, no markdown, no explanation."""


def _build_article_prompt(keyword: str, brief: dict, competitor_data: list[dict]) -> str:
    outline_str = ""
    for section in brief.get("outline", []):
        outline_str += f"\n## {section['heading']}\n"
        for sub in section.get("subheadings", []):
            outline_str += f"### {sub}\n"

    entities = ", ".join(brief.get("entities_to_include", [])[:10])
    questions = "\n".join(f"- {q}" for q in brief.get("questions_to_answer", [])[:8])
    avg_words = int(
        sum(c["word_count"] for c in competitor_data) / len(competitor_data)
    ) if competitor_data else 1200
    target_words = max(brief.get("recommended_word_count", 1200), avg_words)

    return f"""You are an expert SEO content writer. Write a comprehensive, well-structured article.

TARGET KEYWORD: {keyword}
TARGET LENGTH: ~{target_words} words
TITLE: {brief.get('recommended_title', keyword)}

OUTLINE TO FOLLOW:
{outline_str}

KEY ENTITIES TO MENTION: {entities}

QUESTIONS TO ANSWER:
{questions}

WRITING INSTRUCTIONS:
- Write in clear, authoritative prose. No fluff.
- Include the target keyword naturally in the first 100 words.
- Use the keyword 2-3 times per 500 words (avoid stuffing).
- Every H2 section should answer a specific user intent.
- Include a strong introduction and conclusion.
- Format in Markdown with proper heading hierarchy.
- Write for humans first, search engines second.

Begin writing the full article now:"""


# ── Streaming generation ──────────────────────────────────────────────────────

async def generate_brief(
    keyword: str,
    paa_questions: list[str],
    competitor_data: list[dict],
    serp_features: list[str],
) -> dict:
    """Generate a structured content brief. Returns dict."""
    if not ANTHROPIC_AVAILABLE:
        return _mock_brief(keyword, paa_questions)

    prompt = _build_brief_prompt(keyword, paa_questions, competitor_data, serp_features)
    try:
        message = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # Strip any markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.error("Brief generation failed", error=str(e))
        return _mock_brief(keyword, paa_questions)


async def generate_article_stream(
    keyword: str,
    brief: dict,
    competitor_data: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream article generation. Yields text chunks."""
    if not ANTHROPIC_AVAILABLE:
        yield _mock_article(keyword, brief)
        return

    prompt = _build_article_prompt(keyword, brief, competitor_data)
    try:
        with _client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        logger.error("Article stream failed", error=str(e))
        yield _mock_article(keyword, brief)


async def generate_article_full(
    keyword: str,
    brief: dict,
    competitor_data: list[dict],
) -> str:
    """Generate complete article as a single string."""
    if not ANTHROPIC_AVAILABLE:
        return _mock_article(keyword, brief)

    prompt = _build_article_prompt(keyword, brief, competitor_data)
    try:
        message = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.error("Article generation failed", error=str(e))
        return _mock_article(keyword, brief)


# ── Mock fallbacks ────────────────────────────────────────────────────────────

def _mock_brief(keyword: str, paa_questions: list[str]) -> dict:
    return {
        "recommended_title": f"The Complete Guide to {keyword.title()} in 2025",
        "meta_description": f"Learn everything about {keyword} — from basics to advanced strategies. Updated guide with expert tips and real examples.",
        "recommended_word_count": 2000,
        "content_angle": f"Comprehensive beginner-to-advanced guide covering all aspects of {keyword}",
        "outline": [
            {
                "heading": f"What Is {keyword.title()}?",
                "subheadings": ["Definition and overview", "Why it matters"],
                "key_points": [f"Define {keyword}", "Explain core concepts"],
            },
            {
                "heading": f"How {keyword.title()} Works",
                "subheadings": ["Step-by-step process", "Key components"],
                "key_points": ["Detailed explanation", "Use real examples"],
            },
            {
                "heading": f"Best Practices for {keyword.title()}",
                "subheadings": ["Common mistakes to avoid", "Pro tips"],
                "key_points": ["Actionable advice", "Expert recommendations"],
            },
            {
                "heading": "FAQ",
                "subheadings": [q for q in paa_questions[:4]],
                "key_points": ["Answer each question concisely"],
            },
        ],
        "entities_to_include": [keyword, "SEO", "Google", "best practices", "strategy"],
        "questions_to_answer": paa_questions[:8],
        "internal_links_to_include": [],
        "writing_notes": "Write in a friendly, authoritative tone. Use short paragraphs and bullet lists for scannability.",
    }


def _mock_article(keyword: str, brief: dict) -> str:
    title = brief.get("recommended_title", f"Complete Guide to {keyword.title()}")
    sections = ""
    for section in brief.get("outline", [])[:4]:
        sections += f"\n\n## {section['heading']}\n\n"
        sections += f"This section covers everything you need to know about {section['heading'].lower()}. "
        sections += f"Understanding this aspect of {keyword} is crucial for achieving your goals.\n\n"
        for sub in section.get("subheadings", [])[:2]:
            sections += f"\n### {sub}\n\nDetailed content about {sub.lower()} goes here. "
            sections += f"This is where you would explain the concept in depth, backed by examples and data.\n"

    return f"""# {title}

{keyword.title()} is one of the most important topics in digital marketing today. In this comprehensive guide, we'll cover everything you need to know to succeed with {keyword}.

**Note:** This is mock content. Connect your Anthropic API key in `.env` to generate real AI-written articles.
{sections}

## Conclusion

Mastering {keyword} takes time and practice. Use this guide as your foundation, apply the strategies consistently, and measure your results.

*Word count: ~{brief.get('recommended_word_count', 1500)} words (mock)*
"""
