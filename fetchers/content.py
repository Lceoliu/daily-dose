from __future__ import annotations

import html
import re
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": "daily-trends-bot/0.1 (+https://github.com/actions)",
}
REQUEST_TIMEOUT = 20
TEXT_RE = re.compile(r"\s+")


def clean_text(value: str | None, limit: int = 1200) -> str | None:
    if not value:
        return None

    text = html.unescape(value)
    text = TEXT_RE.sub(" ", text).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_text_block(parts: Iterable[str | None], limit: int = 1600) -> str | None:
    unique_parts: list[str] = []
    seen: set[str] = set()
    total_length = 0

    for part in parts:
        cleaned = clean_text(part)
        if not cleaned or cleaned in seen:
            continue
        next_length = total_length + len(cleaned) + (2 if unique_parts else 0)
        if next_length > limit:
            remaining = limit - total_length - (2 if unique_parts else 0)
            if remaining > 40:
                unique_parts.append(cleaned[: remaining - 3].rstrip() + "...")
            break
        unique_parts.append(cleaned)
        seen.add(cleaned)
        total_length = next_length

    if not unique_parts:
        return None
    return "\n\n".join(unique_parts)


def _pick_meta(soup: BeautifulSoup, selectors: list[tuple[str, str]]) -> str | None:
    for attr, value in selectors:
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            cleaned = clean_text(tag["content"], limit=500)
            if cleaned:
                return cleaned
    return None


def _pick_paragraphs(soup: BeautifulSoup, limit: int = 3) -> list[str]:
    container = soup.find("article") or soup.find("main") or soup.body
    if container is None:
        return []

    paragraphs: list[str] = []
    for paragraph in container.find_all("p"):
        text = clean_text(paragraph.get_text(" ", strip=True), limit=400)
        if not text or len(text) < 60:
            continue
        if text in paragraphs:
            continue
        paragraphs.append(text)
        if len(paragraphs) >= limit:
            break
    return paragraphs


def fetch_page_context(url: str | None) -> dict:
    if not url:
        return {}

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {}

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        return {}

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "xml" not in content_type:
        return {
            "resolved_url": response.url,
            "content_type": content_type,
        }

    soup = BeautifulSoup(response.text, "html.parser")
    title = clean_text(
        (
            _pick_meta(soup, [("property", "og:title"), ("name", "twitter:title")])
            or (soup.title.get_text(" ", strip=True) if soup.title else None)
        ),
        limit=240,
    )
    description = _pick_meta(
        soup,
        [
            ("property", "og:description"),
            ("name", "description"),
            ("name", "twitter:description"),
        ],
    )
    paragraphs = _pick_paragraphs(soup)
    excerpt = build_text_block(paragraphs, limit=1000)
    return {
        "resolved_url": response.url,
        "page_title": title,
        "page_description": description,
        "page_excerpt": excerpt,
    }
