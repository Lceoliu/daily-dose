import json
import os
from typing import Any


def _enabled() -> bool:
    return os.getenv("ENABLE_OPENAI_SUMMARY", "").lower() in {"1", "true", "yes"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _serialize_item(item: dict) -> dict[str, Any]:
    linked_context = item.get("linked_context") or {}
    return {
        "title": item.get("title"),
        "source": item.get("source"),
        "category": item.get("category"),
        "summary": item.get("summary"),
        "content_context": item.get("content_context"),
        "comment_highlights": item.get("comment_highlights"),
        "related_headlines": item.get("related_headlines"),
        "trend_score": item.get("trend_score"),
        "score": item.get("score"),
        "comment_count": item.get("comment_count"),
        "total_stars": item.get("total_stars"),
        "language": item.get("language"),
        "domains": item.get("domains"),
        "subreddit": item.get("subreddit"),
        "author": item.get("author"),
        "url": item.get("url"),
        "page_title": linked_context.get("page_title"),
        "page_description": linked_context.get("page_description"),
        "page_excerpt": linked_context.get("page_excerpt"),
        "resolved_url": linked_context.get("resolved_url"),
    }


def _build_summary_input(payload: dict) -> dict[str, Any]:
    top_trends = [_serialize_item(item) for item in payload.get("top_trends", [])[:12]]
    source_leaders = {}
    for source_name, items in (payload.get("items") or {}).items():
        source_leaders[source_name] = [_serialize_item(item) for item in items[:3]]

    return {
        "generated_at": payload.get("generated_at"),
        "counts": payload.get("counts", {}),
        "notes": payload.get("notes", []),
        "top_trends": top_trends,
        "source_leaders": source_leaders,
    }


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _build_default_follow_up(item: dict) -> str:
    category = item.get("category")
    if category == "github_trending":
        return "明天继续看 star 增速、是否出现更多 issue 或二次讨论，以及是否有开发者开始真实集成。"
    if category == "reddit":
        return "明天继续看讨论是否扩散到更多板块，以及是否出现原始信源或新增事实。"
    if category == "hacker_news":
        return "明天继续看评论区是否补出关键反驳、实际案例或更多技术上下文。"
    if category == "news":
        return "明天继续看是否有官方回应、后续细节或二级影响进入头条。"
    return "明天继续看热度是否延续，以及是否出现更多可验证的新信息。"


def _default_hype_check(item: dict) -> str:
    category = item.get("category")
    if category == "github_trending":
        return "目前更像真实信号，但要警惕 GitHub 日榜对新奇项目的放大效应。"
    if category in {"reddit", "news"}:
        return "当前更像情绪传播与真实信息混合，不能只看标题判断。"
    if category == "hacker_news":
        return "当前信号偏早期，技术圈兴趣存在，但未必说明更大趋势已经形成。"
    return "当前信号强弱仍需更多上下文验证。"


def _default_value_check(item: dict) -> str:
    category = item.get("category")
    if category == "github_trending":
        return "如果后续出现真实用例、生态集成或持续上榜，就有持续跟踪价值。"
    if category == "reddit":
        return "有跟踪价值，但重点应放在原始报道和评论里透露的新增事实，而不是情绪本身。"
    if category == "hacker_news":
        return "有一定价值，适合观察技术社区是否给出更深入的方法、反例或实测。"
    if category == "news":
        return "是否值得继续跟，要看这条新闻能否演化出政策、产品或产业层面的后续动作。"
    return "后续价值取决于是否出现更多可验证的信息。"


def _fallback_source_briefs(payload: dict) -> list[dict[str, str]]:
    briefs: list[dict[str, str]] = []
    items_by_source = payload.get("items") or {}
    for source_name in ("reddit", "hacker_news", "news"):
        items = items_by_source.get(source_name) or []
        if not items:
            continue
        item = items[0]
        briefs.append(
            {
                "source_group": source_name,
                "item_name": item.get("title") or "Unnamed item",
                "content_summary": item.get("content_context") or item.get("summary") or "暂无足够内容上下文。",
                "ai_comment": _default_value_check(item),
            }
        )
    return briefs


def _normalize_named_hotspots(summary: dict, payload: dict) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    items_by_name = {}
    for item in payload.get("top_trends", []):
        title = (item.get("title") or "").strip()
        if title:
            items_by_name[title.lower()] = item
            items_by_name[title.lower().split("/")[-1]] = item

    for item in summary.get("named_hotspots") or []:
        name = item.get("name") or "Unnamed hotspot"
        matched = items_by_name.get(str(name).lower()) or {}
        normalized.append(
            {
                "name": name,
                "kind": item.get("kind") or "topic",
                "source": item.get("source") or matched.get("source") or "",
                "what_happened": item.get("what_happened") or "",
                "core_details": item.get("core_details") or item.get("why_hot") or item.get("what_happened") or "",
                "ai_take": item.get("ai_take") or item.get("why_hot") or "",
                "hype_check": item.get("hype_check") or _default_hype_check(matched),
                "value_check": item.get("value_check") or _default_value_check(matched),
                "follow_up": item.get("follow_up") or _build_default_follow_up(matched),
                "evidence": item.get("evidence") or "",
            }
        )
    return normalized


def _normalize_summary(summary: dict, payload: dict) -> dict:
    return {
        "overview": summary.get("overview") or "",
        "named_hotspots": _normalize_named_hotspots(summary, payload),
        "source_briefs": summary.get("source_briefs") or _fallback_source_briefs(payload),
        "closing_note": summary.get("closing_note") or "",
    }


def _client_kwargs() -> dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    return {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": base_url,
        "timeout": _env_int("OPENAI_TIMEOUT_SECONDS", 180),
        "max_retries": _env_int("OPENAI_MAX_RETRIES", 4),
    }


def summarize_payload(payload: dict) -> dict | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    if not _enabled():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(**_client_kwargs())
    summary_input = _build_summary_input(payload)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are writing a sharp Chinese daily trends briefing for a technical reader. "
                        "Use the provided content_context, page_description, page_excerpt, comment_highlights, "
                        "and related_headlines to summarize the actual substance of each item, not just the headline. "
                        "For every hotspot, explain whether it looks like durable signal, short-lived hype, "
                        "or a mixed case; and say whether it deserves follow-up tomorrow. "
                        "All prose values must be in Simplified Chinese. "
                        "Return valid JSON only with this exact schema: "
                        "{"
                        '"overview": string, '
                        '"named_hotspots": ['
                        "{"
                        '"name": string, '
                        '"kind": string, '
                        '"source": string, '
                        '"what_happened": string, '
                        '"core_details": string, '
                        '"ai_take": string, '
                        '"hype_check": string, '
                        '"value_check": string, '
                        '"follow_up": string, '
                        '"evidence": string'
                        "}"
                        "], "
                        '"source_briefs": ['
                        "{"
                        '"source_group": string, '
                        '"item_name": string, '
                        '"content_summary": string, '
                        '"ai_comment": string'
                        "}"
                        "], "
                        '"closing_note": string'
                        "}. "
                        "Rules: "
                        "1. Mention only specific named entities from the input. "
                        "2. kind must be one of: project, company, model, product, event, person, research, topic. "
                        "3. named_hotspots should prioritize 6-10 items across GitHub Trending, Reddit, Hacker News, and News. "
                        "4. what_happened should state the event plainly. "
                        "5. core_details must summarize the underlying content or discussion, using comments/excerpts when available. "
                        "6. ai_take should be your informed interpretation of why the item matters. "
                        "7. hype_check must explicitly judge whether it is mostly attention bait, mostly real signal, or mixed. "
                        "8. value_check must judge whether following this item tomorrow is worthwhile and why. "
                        "9. source_briefs should summarize at least one concrete item each from reddit, hacker_news, and news when data exists. "
                        "10. Keep the tone direct, analytical, and specific."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(summary_input, ensure_ascii=False),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # noqa: BLE001
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or "default-openai-base-url"
        raise RuntimeError(
            f"{exc} (model={model}, base_url={base_url})"
        ) from exc

    content = response.choices[0].message.content or ""
    summary = _extract_json(content)
    if summary is None:
        return _normalize_summary(
            {
                "overview": content.strip(),
                "named_hotspots": [],
                "source_briefs": [],
                "closing_note": "",
            },
            payload,
        )
    return _normalize_summary(summary, payload)
