import math
import re
from collections import Counter
from urllib.parse import urlparse

from fetchers.common import parse_published_at, utc_now


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "when",
    "who",
    "with",
}
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
SOURCE_WEIGHTS = {
    "github_trending": 0.92,
    "reddit": 0.95,
    "hacker_news": 0.9,
    "news": 0.8,
}
TECH_SUBREDDITS = {
    "technology",
    "artificial",
    "programming",
    "machinelearning",
    "openai",
    "singularity",
    "gadgets",
}
FINANCE_SUBREDDITS = {
    "finance",
    "economics",
    "stocks",
    "investing",
    "securityanalysis",
    "options",
    "wallstreetbets",
}
TECH_KEYWORDS = {
    "ai",
    "artificial",
    "chip",
    "chips",
    "cloud",
    "code",
    "coding",
    "data",
    "developer",
    "gemini",
    "google",
    "llm",
    "machine",
    "model",
    "nvidia",
    "openai",
    "programming",
    "robot",
    "robots",
    "semiconductor",
    "software",
    "startup",
    "tech",
    "technology",
}
FINANCE_KEYWORDS = {
    "bank",
    "banks",
    "bond",
    "bonds",
    "crypto",
    "earnings",
    "economy",
    "economics",
    "etf",
    "fed",
    "finance",
    "financial",
    "gas",
    "housing",
    "inflation",
    "investing",
    "market",
    "markets",
    "mortgage",
    "oil",
    "price",
    "prices",
    "rate",
    "rates",
    "recession",
    "stock",
    "stocks",
    "tariff",
    "tariffs",
    "trade",
}
TECH_SOURCES = {
    "ycombinator",
    "techcrunch",
    "the verge",
    "wired",
    "ars technica",
    "github",
}
FINANCE_SOURCES = {
    "yahoo finance",
    "financial times",
    "wsj",
    "wall street journal",
    "bloomberg",
    "cnbc",
    "marketwatch",
    "reuters",
}
DOMAIN_WEIGHTS = {
    "technology": 1.18,
    "finance": 1.14,
}


def _title_tokens(title: str) -> set[str]:
    tokens = {token for token in TOKEN_RE.findall(title.lower()) if token not in STOPWORDS}
    return tokens


def _engagement_value(item: dict) -> float:
    score = max(float(item.get("score") or 0), 0.0)
    comment_count = max(float(item.get("comment_count") or 0), 0.0)
    return math.log1p(score) + 0.8 * math.log1p(comment_count)


def _detect_domains(item: dict) -> list[str]:
    domains: set[str] = set()
    subreddit = str(item.get("subreddit") or "").lower()
    source = str(item.get("source") or "").lower()
    title_tokens = _title_tokens(item.get("title", ""))
    url_host = urlparse(str(item.get("url") or "")).netloc.lower()

    if subreddit in TECH_SUBREDDITS:
        domains.add("technology")
    if subreddit in FINANCE_SUBREDDITS:
        domains.add("finance")

    if title_tokens & TECH_KEYWORDS:
        domains.add("technology")
    if title_tokens & FINANCE_KEYWORDS:
        domains.add("finance")

    if any(name in source for name in TECH_SOURCES) or any(name in url_host for name in TECH_SOURCES):
        domains.add("technology")
    if any(name in source for name in FINANCE_SOURCES) or any(name in url_host for name in FINANCE_SOURCES):
        domains.add("finance")

    return sorted(domains)


def _domain_weight(item: dict) -> tuple[float, list[str]]:
    domains = _detect_domains(item)
    if not domains:
        return 1.0, []

    weight = 1.0
    for domain in domains:
        weight = max(weight, DOMAIN_WEIGHTS[domain])
    return weight, domains


def rank_items(items_by_source: dict[str, list[dict]]) -> dict[str, list[dict]]:
    all_items = [item for items in items_by_source.values() for item in items]
    token_counter: Counter[str] = Counter()
    engagement_values: list[float] = []

    for item in all_items:
        token_counter.update(_title_tokens(item.get("title", "")))
        engagement_values.append(_engagement_value(item))

    max_engagement = max(engagement_values, default=0.0)
    reference_now = utc_now()

    ranked_by_source: dict[str, list[dict]] = {}
    for source_name, items in items_by_source.items():
        ranked_items: list[dict] = []
        for item in items:
            published_at = parse_published_at(item.get("published_at"))
            age_hours = 24.0
            if published_at:
                age_hours = max((reference_now - published_at).total_seconds() / 3600, 0.0)

            freshness_score = max(0.0, 1.0 - min(age_hours, 24.0) / 24.0)
            engagement_score = 0.0
            if max_engagement > 0:
                engagement_score = _engagement_value(item) / max_engagement

            overlap_score = 0.0
            tokens = _title_tokens(item.get("title", ""))
            if tokens:
                overlap_hits = sum(1 for token in tokens if token_counter[token] > 1)
                overlap_score = overlap_hits / len(tokens)

            source_weight = SOURCE_WEIGHTS.get(item.get("category", ""), 0.75)
            domain_weight, domains = _domain_weight(item)
            trend_score = round(
                100
                * source_weight
                * domain_weight
                * (
                    0.45 * freshness_score
                    + 0.35 * engagement_score
                    + 0.20 * overlap_score
                ),
                2,
            )

            ranked_item = dict(item)
            ranked_item["trend_score"] = trend_score
            ranked_item["trend_breakdown"] = {
                "freshness": round(freshness_score, 3),
                "engagement": round(engagement_score, 3),
                "topic_overlap": round(overlap_score, 3),
                "source_weight": source_weight,
                "domain_weight": domain_weight,
            }
            ranked_item["domains"] = domains
            ranked_items.append(ranked_item)

        ranked_items.sort(
            key=lambda item: (
                item["trend_score"],
                item.get("score") or 0,
                item.get("comment_count") or 0,
                item.get("published_at") or "",
            ),
            reverse=True,
        )
        ranked_by_source[source_name] = ranked_items

    return ranked_by_source


def top_ranked_items(items_by_source: dict[str, list[dict]], limit: int = 15) -> list[dict]:
    ranked_items = [item for items in items_by_source.values() for item in items]
    ranked_items.sort(
        key=lambda item: (
            item["trend_score"],
            item.get("score") or 0,
            item.get("comment_count") or 0,
            item.get("published_at") or "",
        ),
        reverse=True,
    )
    return ranked_items[:limit]
