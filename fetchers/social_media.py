from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from typing import Iterable

import requests

from fetchers.common import filter_recent_items, normalize_published_at
from fetchers.content import build_text_block, clean_text, fetch_page_context


DEFAULT_HEADERS = {
    "User-Agent": "daily-trends-bot/0.1 (+https://github.com/actions)",
    "Accept": "application/json",
}
REQUEST_TIMEOUT = 20


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def fetch_reddit_posts(
    subreddits: Iterable[str] | None = None,
    limit_per_subreddit: int = 5,
) -> list[dict]:
    subreddit_list = list(subreddits or _env_list("REDDIT_SUBREDDITS"))
    if not subreddit_list:
        subreddit_list = ["technology", "worldnews", "artificial"]

    items: list[dict] = []
    fetch_errors: list[str] = []
    successful_subreddits = 0
    for subreddit in subreddit_list:
        response = None
        last_error = None
        for endpoint in (
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            f"https://api.reddit.com/r/{subreddit}/hot",
        ):
            try:
                response = requests.get(
                    endpoint,
                    params={
                        "limit": max(limit_per_subreddit * 4, 20),
                        "raw_json": 1,
                    },
                    headers=DEFAULT_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
                response = None

        if response is None:
            error_message = str(last_error) if last_error else "unknown reddit fetch error"
            fetch_errors.append(f"r/{subreddit}: {error_message}")
            continue

        successful_subreddits += 1

        payload = response.json()
        children = payload.get("data", {}).get("children", [])
        for child in children:
            data = child.get("data", {})
            if not data:
                continue
            items.append(
                {
                    "source": f"reddit:r/{subreddit}",
                    "category": "reddit",
                    "title": (data.get("title") or "").strip(),
                    "url": f"https://www.reddit.com{data.get('permalink')}" if data.get("permalink") else data.get("url"),
                    "external_url": data.get("url"),
                    "permalink": data.get("permalink"),
                    "author": data.get("author"),
                    "summary": data.get("selftext") or None,
                    "published_at": normalize_published_at(data.get("created_utc")),
                    "subreddit": subreddit,
                    "score": data.get("score"),
                    "comment_count": data.get("num_comments"),
                }
            )

    filtered_items = filter_recent_items(
        items,
        max_age_hours=24,
        limit=len(subreddit_list) * limit_per_subreddit,
    )

    if successful_subreddits == 0:
        detail = "; ".join(fetch_errors[:3]) or "no subreddit fetch succeeded"
        raise RuntimeError(f"all subreddit fetches failed: {detail}")

    return [_enrich_reddit_item(item) for item in filtered_items]


def _fetch_reddit_comments(permalink: str | None, limit: int = 3) -> list[str]:
    if not permalink:
        return []

    try:
        response = requests.get(
            f"https://www.reddit.com{permalink}.json",
            params={"raw_json": 1, "limit": limit},
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    try:
        payload = response.json()
    except ValueError:
        return []

    comments: list[str] = []
    for child in payload[1].get("data", {}).get("children", []):
        if child.get("kind") != "t1":
            continue
        body = clean_text(child.get("data", {}).get("body"), limit=300)
        if body:
            comments.append(body)
        if len(comments) >= limit:
            break
    return comments


def _enrich_reddit_item(item: dict) -> dict:
    enriched = dict(item)
    comment_highlights = _fetch_reddit_comments(item.get("permalink"))
    external_url = item.get("external_url")
    page_context = {}
    if external_url and "reddit.com" not in str(external_url):
        page_context = fetch_page_context(str(external_url))

    context_parts = [
        item.get("summary"),
        page_context.get("page_description"),
        page_context.get("page_excerpt"),
        *(f"Top comment: {comment}" for comment in comment_highlights),
    ]
    enriched["comment_highlights"] = comment_highlights
    enriched["linked_context"] = page_context
    enriched["content_context"] = build_text_block(context_parts)
    if not enriched.get("summary"):
        enriched["summary"] = (
            page_context.get("page_description")
            or page_context.get("page_excerpt")
            or (comment_highlights[0] if comment_highlights else None)
        )
    return enriched


def _fetch_hacker_news_comment(comment_id: int) -> str | None:
    try:
        response = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json",
            headers=DEFAULT_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    body = response.json().get("text")
    return clean_text(body, limit=300)


def _fetch_hacker_news_item(story_id: int) -> dict | None:
    item_response = requests.get(
        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    item_response.raise_for_status()
    story = item_response.json()

    if not story or story.get("type") != "story" or story.get("deleted") or story.get("dead"):
        return None

    external_context = fetch_page_context(story.get("url"))
    comment_ids = story.get("kids") or []
    comment_highlights = [comment for comment in (_fetch_hacker_news_comment(comment_id) for comment_id in comment_ids[:3]) if comment]
    summary = (
        external_context.get("page_description")
        or external_context.get("page_excerpt")
        or (comment_highlights[0] if comment_highlights else None)
    )

    return {
        "source": "hacker-news",
        "category": "hacker_news",
        "title": story.get("title", "").strip(),
        "url": story.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
        "author": story.get("by"),
        "score": story.get("score"),
        "comment_count": story.get("descendants"),
        "published_at": normalize_published_at(story.get("time")),
        "summary": summary,
        "comment_highlights": comment_highlights,
        "linked_context": external_context,
        "content_context": build_text_block(
            [
                story.get("text"),
                external_context.get("page_description"),
                external_context.get("page_excerpt"),
                *(f"HN comment: {comment}" for comment in comment_highlights),
            ]
        ),
    }


def fetch_hacker_news_posts(limit: int = 10, max_scan: int = 40) -> list[dict]:
    story_ids_response = requests.get(
        "https://hacker-news.firebaseio.com/v0/newstories.json",
        headers=DEFAULT_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    story_ids_response.raise_for_status()
    story_ids = story_ids_response.json()

    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(_fetch_hacker_news_item, story_id)
            for story_id in story_ids[:max_scan]
        ]
        for future in as_completed(futures):
            try:
                item = future.result()
            except requests.RequestException:
                continue
            if item:
                items.append(item)

    return filter_recent_items(items, max_age_hours=24, limit=limit)
