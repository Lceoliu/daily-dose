import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fetchers.common import utc_now
from fetchers.content import build_text_block


DEFAULT_HEADERS = {
    "User-Agent": "daily-trends-bot/0.1 (+https://github.com/actions)",
}
BASE_URL = "https://github.com"
REQUEST_TIMEOUT = 20


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_count(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = text.replace(",", "").strip()
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    return int(digits) if digits else None


def fetch_github_trending(limit_per_feed: int = 10) -> list[dict]:
    languages = _env_list("GITHUB_TRENDING_LANGUAGES") or [""]
    items: list[dict] = []
    generated_at = utc_now().isoformat()

    for language in languages:
        params = {"since": "daily"}
        if language:
            params["l"] = language

        response = requests.get(
            f"{BASE_URL}/trending",
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("article.Box-row")
        for article in articles[:limit_per_feed]:
            repo_link = article.select_one("h2 a")
            if repo_link is None:
                continue

            repo_path = repo_link.get("href", "").strip()
            repo_name = repo_link.get_text(" ", strip=True).replace(" / ", "/")
            description_node = article.select_one("p")
            lang_node = article.select_one('span[itemprop="programmingLanguage"]')
            stats_links = article.select("a.Link--muted")
            built_by = [img.get("alt", "").lstrip("@") for img in article.select("img.avatar")]

            total_stars = None
            forks_count = None
            if len(stats_links) >= 1:
                total_stars = _parse_count(stats_links[0].get_text(" ", strip=True))
            if len(stats_links) >= 2:
                forks_count = _parse_count(stats_links[1].get_text(" ", strip=True))

            stars_today_text = article.get_text("\n", strip=True)
            stars_today = None
            for line in stars_today_text.splitlines():
                if "stars today" in line.lower():
                    stars_today = _parse_count(line)
                    break

            items.append(
                {
                    "source": "github-trending",
                    "category": "github_trending",
                    "title": repo_name,
                    "url": urljoin(BASE_URL, repo_path),
                    "author": repo_name.split("/", 1)[0] if "/" in repo_name else None,
                    "summary": description_node.get_text(" ", strip=True) if description_node else None,
                    "published_at": generated_at,
                    "language": (lang_node.get_text(" ", strip=True) if lang_node else language) or None,
                    "score": stars_today,
                    "comment_count": forks_count,
                    "total_stars": total_stars,
                    "built_by": built_by,
                    "content_context": build_text_block(
                        [
                            description_node.get_text(" ", strip=True) if description_node else None,
                            f"Language: {(lang_node.get_text(' ', strip=True) if lang_node else language) or 'unknown'}",
                            f"Stars today: {stars_today}" if stars_today is not None else None,
                            f"Total stars: {total_stars}" if total_stars is not None else None,
                            f"Built by: {', '.join(built_by[:5])}" if built_by else None,
                        ],
                        limit=600,
                    ),
                }
            )

    items.sort(
        key=lambda item: (
            item.get("score") or 0,
            item.get("comment_count") or 0,
            item.get("total_stars") or 0,
        ),
        reverse=True,
    )
    return items[: len(languages) * limit_per_feed]
