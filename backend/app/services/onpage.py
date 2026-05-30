"""
On-page NLP analysis service.
Uses TF-IDF + entity extraction. spaCy model loaded lazily.
Falls back gracefully if spaCy model not downloaded.
"""
import re
import math
import asyncio
from typing import Optional
import httpx
import structlog

try:
    import spacy
    _nlp = None
    def get_nlp():
        global _nlp
        if _nlp is None:
            try:
                _nlp = spacy.load("en_core_web_sm")
            except OSError:
                _nlp = False  # Mark as unavailable
        return _nlp if _nlp else None
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    def get_nlp(): return None

logger = structlog.get_logger()

# ── Text extraction ───────────────────────────────────────────────────────────

async def fetch_page_text(url: str) -> str:
    """Extract clean text from a URL using trafilatura."""
    try:
        import trafilatura
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True,
                                    headers={"User-Agent": "SEOPlatformBot/1.0"})
            resp.raise_for_status()
        text = trafilatura.extract(resp.text, include_comments=False,
                                   include_tables=True, no_fallback=False)
        return text or ""
    except Exception as e:
        logger.warning("fetch_page_text failed", url=url, error=str(e))
        return ""


# ── TF-IDF helpers ────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with",
        "is","are","was","were","be","been","being","have","has","had","do",
        "does","did","will","would","could","should","may","might","shall",
        "that","this","these","those","it","its","they","their","we","our",
        "you","your","he","his","she","her","i","my","me","us","them",
        "from","by","as","into","through","about","between","each","more",
        "also","than","so","if","not","no","can","all","any","one","two",
    }
    return [t for t in tokens if t not in stopwords]


def _term_freq(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = len(tokens)
    return {k: v / total for k, v in tf.items()}


def _tfidf_scores(doc_tokens: list[str], corpus_tokens: list[list[str]]) -> dict[str, float]:
    """Compute TF-IDF for doc against corpus."""
    tf = _term_freq(doc_tokens)
    n_docs = len(corpus_tokens) + 1
    idf: dict[str, float] = {}
    all_terms = set(doc_tokens)
    for term in all_terms:
        doc_count = sum(1 for d in corpus_tokens if term in d) + 1
        idf[term] = math.log(n_docs / doc_count)
    return {t: tf.get(t, 0) * idf.get(t, 0) for t in all_terms}


def _keyword_density(text: str, keyword: str) -> float:
    words = text.lower().split()
    if not words:
        return 0.0
    kw_words = keyword.lower().split()
    count = sum(
        1 for i in range(len(words) - len(kw_words) + 1)
        if words[i:i+len(kw_words)] == kw_words
    )
    return round(count / max(len(words), 1) * 100, 2)


# ── Entity extraction ─────────────────────────────────────────────────────────

def _extract_entities(text: str) -> list[str]:
    nlp = get_nlp()
    if not nlp or not text:
        return []
    try:
        doc = nlp(text[:50000])  # spaCy has token limits
        return list({
            ent.text.lower() for ent in doc.ents
            if ent.label_ in ("ORG", "PRODUCT", "GPE", "PERSON", "NORP", "WORK_OF_ART", "LAW", "TECH")
        })
    except Exception:
        return []


# ── Keyword clustering (TF-IDF cosine) ───────────────────────────────────────

def cluster_keywords(keywords: list[str], n_clusters: int = 8) -> dict[str, str]:
    """Return {keyword: cluster_id} mapping using simple token overlap."""
    if not keywords:
        return {}
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        import numpy as np

        n_clusters = min(n_clusters, len(keywords))
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        X = vec.fit_transform(keywords)
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        return {kw: f"cluster_{label}" for kw, label in zip(keywords, labels)}
    except Exception:
        return {kw: "cluster_0" for kw in keywords}


# ── Internal link suggestions ─────────────────────────────────────────────────

def suggest_internal_links(
    target_url: str,
    target_tokens: list[str],
    other_pages: list[dict],  # [{url, tokens}]
    top_n: int = 5,
) -> list[dict]:
    """Find pages with high token overlap for internal link suggestions."""
    target_set = set(target_tokens)
    scores = []
    for page in other_pages:
        if page["url"] == target_url:
            continue
        page_set = set(page.get("tokens", []))
        if not page_set:
            continue
        overlap = len(target_set & page_set)
        jaccard = overlap / len(target_set | page_set) if (target_set | page_set) else 0
        if jaccard > 0.05:
            # Pick best anchor text (highest-scoring shared term)
            shared = list(target_set & page_set)
            anchor = max(shared, key=lambda t: target_tokens.count(t), default=t) if shared else ""
            scores.append({"url": page["url"], "score": round(jaccard, 3), "suggested_anchor": anchor})
    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:top_n]


# ── Main analysis function ────────────────────────────────────────────────────

async def analyze_page(
    url: str,
    target_keyword: str,
    competitor_urls: Optional[list[str]] = None,
    page_texts: Optional[dict[str, str]] = None,  # pre-fetched texts
) -> dict:
    """
    Full on-page NLP analysis.
    Returns structured analysis dict.
    """
    competitor_urls = competitor_urls or []

    # Fetch target page
    target_text = page_texts.get(url, "") if page_texts else await fetch_page_text(url)
    if not target_text:
        return {"error": "Could not fetch page content", "url": url}

    # Fetch competitor texts concurrently
    comp_texts: list[str] = []
    if competitor_urls:
        if page_texts:
            comp_texts = [page_texts.get(u, "") for u in competitor_urls]
        else:
            tasks = [fetch_page_text(u) for u in competitor_urls[:5]]
            comp_texts = await asyncio.gather(*tasks)
        comp_texts = [t for t in comp_texts if t]

    # Tokenize
    target_tokens = _tokenize(target_text)
    comp_token_lists = [_tokenize(t) for t in comp_texts]

    # TF-IDF
    tfidf = _tfidf_scores(target_tokens, comp_token_lists)
    top_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)[:30]

    # Keyword density
    density = _keyword_density(target_text, target_keyword)

    # Word counts
    target_word_count = len(target_text.split())
    avg_comp_words = (
        int(sum(len(t.split()) for t in comp_texts) / len(comp_texts))
        if comp_texts else 0
    )

    # Entity extraction
    target_entities = set(_extract_entities(target_text))
    comp_entities: set[str] = set()
    for ct in comp_texts[:3]:
        comp_entities.update(_extract_entities(ct))
    missing_entities = list(comp_entities - target_entities)[:20]
    present_entities = list(target_entities)[:20]

    # Build suggested keywords (top TF-IDF terms not already prominent)
    kw_tokens = set(_tokenize(target_keyword))
    suggested = [
        {"term": term, "score": round(score, 4)}
        for term, score in top_terms
        if term not in kw_tokens and score > 0.001
    ][:15]

    # Content score (heuristic 0-100)
    score = 50
    if density >= 0.5 and density <= 2.5: score += 15
    elif density > 0: score += 5
    if target_word_count >= (avg_comp_words * 0.8 if avg_comp_words else 600): score += 15
    if target_word_count >= 800: score += 10
    if len(missing_entities) < 5: score += 10
    score = min(100, max(0, score))

    return {
        "url": url,
        "target_keyword": target_keyword,
        "content_score": score,
        "word_count": target_word_count,
        "avg_competitor_words": avg_comp_words,
        "keyword_density": density,
        "top_tfidf_terms": suggested,
        "missing_entities": missing_entities,
        "present_entities": present_entities,
        "suggested_keywords": suggested[:10],
        "internal_link_suggestions": [],  # populated separately
        "competitor_urls": competitor_urls,
    }
