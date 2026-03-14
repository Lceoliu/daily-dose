import os
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from fetchers.common import filter_recent_items, normalize_published_at
from fetchers.content import build_text_block, clean_text


DEFAULT_HEADERS = {
    "User-Agent": "daily-trends-bot/0.1 (+https://github.com/actions)",
}
DEFAULT_NEWS_FEED = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
REQUEST_TIMEOUT = 20


def _parse_related_headlines(description_html: str | None) -> list[str]:
    if not description_html:
        return []

    soup = BeautifulSoup(description_html, "html.parser")
    related: list[str] = []
    for link in soup.find_all("a"):
        text = clean_text(link.get_text(" ", strip=True), limit=220)
        if text and text not in related:
            related.append(text)
    return related


def _build_news_context(source: str, title: str, related_headlines: list[str]) -> tuple[str | None, str | None]:
    alternates = [headline for headline in related_headlines if headline != title]
    summary = None
    if alternates:
        summary = f"{source} 头条聚焦该事件，Google News 同时聚合到这些相关表述：{'；'.join(alternates[:3])}。"
    elif source:
        summary = f"{source} 在最近 24 小时头条中突出报道了这条新闻。"

    context = build_text_block(
        [
            title,
            summary,
            *(f"Related coverage: {headline}" for headline in alternates[:5]),
        ],
        limit=1200,
    )
    return summary, context


def fetch_news_headlines(limit: int = 10) -> list[dict]:
    feed_url = os.getenv("NEWS_RSS_FEED", DEFAULT_NEWS_FEED)
    response = requests.get(feed_url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    items: list[dict] = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title", default="").strip()
        link = item.findtext("link")
        pub_date = item.findtext("pubDate")
        source_node = item.find("source")
        description_html = item.findtext("description")
        source_name = source_node.text.strip() if source_node is not None and source_node.text else "google-news"
        related_headlines = _parse_related_headlines(description_html)
        summary, content_context = _build_news_context(source_name, title, related_headlines)
        items.append(
            {
                "source": source_name,
                "category": "news",
                "title": title,
                "url": link.strip() if link else None,
                "published_at": normalize_published_at(pub_date),
                "summary": summary,
                "related_headlines": related_headlines,
                "content_context": content_context,
            }
        )

    return filter_recent_items(items, max_age_hours=24, limit=limit)
