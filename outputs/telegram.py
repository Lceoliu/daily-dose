from datetime import datetime
from zoneinfo import ZoneInfo


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _parse_generated_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_time(value: str | None) -> str:
    dt = _parse_generated_at(value)
    if dt is None:
        return ""
    return dt.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")


def _looks_garbled(text: str | None) -> bool:
    if not text:
        return False
    markers = ["\ufffd", "\u951b", "\u95c2", "\u6d60", "\u9422", "\u6a0f", "\u95c6"]
    return any(marker in text for marker in markers)


def _render_named_hotspots(summary: dict) -> list[str]:
    items = summary.get("named_hotspots") or []
    if not items:
        return []

    lines = ["## \u4eca\u65e5\u70ed\u70b9"]
    for index, item in enumerate(items, start=1):
        name = item.get("name") or "\u672a\u547d\u540d\u70ed\u70b9"
        kind = item.get("kind") or "\u70ed\u70b9"
        source = item.get("source") or ""
        what_happened = item.get("what_happened") or ""
        core_details = item.get("core_details") or ""
        ai_take = item.get("ai_take") or ""
        hype_check = item.get("hype_check") or ""
        value_check = item.get("value_check") or ""
        follow_up = item.get("follow_up") or ""
        why_hot = item.get("why_hot") or ""
        evidence = item.get("evidence") or ""
        if source:
            lines.append(f"### {index}. {name} | {kind} | {source}")
        else:
            lines.append(f"### {index}. {name} | {kind}")
        if what_happened:
            lines.append(f"- \u53d1\u751f\u4e86\u4ec0\u4e48\uff1a{what_happened}")
        if core_details:
            lines.append(f"- \u5177\u4f53\u5185\u5bb9\uff1a{core_details}")
        if ai_take:
            lines.append(f"- AI \u89e3\u8bfb\uff1a{ai_take}")
        if hype_check:
            lines.append(f"- \u566a\u97f3\u5224\u65ad\uff1a{hype_check}")
        if value_check:
            lines.append(f"- \u540e\u7eed\u4ef7\u503c\uff1a{value_check}")
        if follow_up:
            lines.append(f"- \u660e\u65e5\u8ddf\u8e2a\uff1a{follow_up}")
        if why_hot:
            lines.append(f"- \u4e3a\u4ec0\u4e48\u706b\uff1a{why_hot}")
        if evidence:
            lines.append(f"- \u70ed\u5ea6\u8ff9\u8c61\uff1a{evidence}")
    return lines


def _render_source_briefs(summary: dict) -> list[str]:
    items = summary.get("source_briefs") or []
    if not items:
        return []

    lines = ["## \u6765\u6e90\u5185\u5bb9\u901f\u89c8"]
    for item in items:
        source_group = item.get("source_group") or "\u672a\u77e5\u6765\u6e90"
        item_name = item.get("item_name") or "\u672a\u547d\u540d\u6761\u76ee"
        content_summary = item.get("content_summary") or ""
        ai_comment = item.get("ai_comment") or ""
        lines.append(f"### {source_group} | {item_name}")
        if content_summary:
            lines.append(f"- \u5185\u5bb9\u6458\u8981\uff1a{content_summary}")
        if ai_comment:
            lines.append(f"- \u89e3\u8bfb\uff1a{ai_comment}")
    return lines


def _render_project_watchlist(summary: dict) -> list[str]:
    items = summary.get("project_watchlist") or []
    if not items:
        return []

    lines = ["## \u503c\u5f97\u7ee7\u7eed\u76ef\u7684\u9879\u76ee"]
    for item in items:
        project = item.get("project") or "\u672a\u547d\u540d\u9879\u76ee"
        description = item.get("summary") or ""
        signal = item.get("signal") or ""
        lines.append(f"### {project}")
        if description:
            lines.append(f"- \u7b80\u8ff0\uff1a{description}")
        if signal:
            lines.append(f"- \u89c2\u5bdf\u4fe1\u53f7\uff1a{signal}")
    return lines


def _render_top_trends(payload: dict) -> list[str]:
    top_trends = payload.get("top_trends") or []
    if not top_trends:
        return []

    lines = ["## \u70ed\u699c Top 10"]
    for index, item in enumerate(top_trends[:10], start=1):
        title = item.get("title") or "\u672a\u547d\u540d\u6761\u76ee"
        source = item.get("source") or "unknown"
        score = item.get("trend_score")
        url = item.get("url") or ""
        if url:
            lines.append(f"{index}. [{title}]({url}) | {source} | trend_score={score}")
        else:
            lines.append(f"{index}. {title} | {source} | trend_score={score}")
    return lines


def _format_item_meta(item: dict) -> str:
    parts: list[str] = []
    trend_score = item.get("trend_score")
    if trend_score is not None:
        parts.append(f"trend_score={trend_score}")

    category = item.get("category")
    if category == "github_trending":
        if item.get("language"):
            parts.append(f"\u8bed\u8a00={item['language']}")
        if item.get("score") is not None:
            parts.append(f"\u4eca\u65e5\u661f\u6807={item['score']}")
        if item.get("total_stars") is not None:
            parts.append(f"\u603b\u661f\u6807={item['total_stars']}")
        if item.get("comment_count") is not None:
            parts.append(f"forks={item['comment_count']}")
    else:
        if item.get("subreddit"):
            parts.append(f"\u677f\u5757=r/{item['subreddit']}")
        if item.get("score") is not None:
            parts.append(f"\u70ed\u5ea6\u5206={item['score']}")
        if item.get("comment_count") is not None:
            parts.append(f"\u8bc4\u8bba={item['comment_count']}")
        if item.get("source"):
            parts.append(f"\u6765\u6e90={item['source']}")
    return " | ".join(parts)


def _build_item_brief(item: dict) -> str:
    summary = item.get("summary")
    if summary:
        return str(summary).strip()

    category = item.get("category")
    if category == "github_trending":
        language = item.get("language") or "\u672a\u77e5"
        built_by = item.get("built_by") or []
        if built_by:
            joined = ", ".join(built_by[:3])
            return f"\u8fd9\u4e2a GitHub Trending \u9879\u76ee\u4eca\u65e5\u6301\u7eed\u722c\u5347\uff0c\u4e3b\u8981\u8d21\u732e\u8005\u5305\u62ec {joined}\u3002"
        return f"\u8fd9\u662f GitHub Trending \u4e0a\u7684\u70ed\u95e8 {language} \u9879\u76ee\u3002"
    if category == "reddit":
        subreddit = item.get("subreddit") or "unknown"
        return f"\u8fd9\u6761 Reddit \u8bdd\u9898\u6765\u81ea r/{subreddit}\uff0c\u5728\u8fd124\u5c0f\u65f6\u5185\u4ea7\u751f\u4e86\u8f83\u9ad8\u8ba8\u8bba\u5ea6\u3002"
    if category == "hacker_news":
        return "\u8fd9\u6761 Hacker News \u94fe\u63a5\u5728\u5f00\u53d1\u8005\u5708\u5185\u83b7\u5f97\u4e86\u8f83\u9ad8\u70b9\u8d5e\u548c\u8bc4\u8bba\u3002"
    if category == "news":
        return "\u8fd9\u6761\u65b0\u95fb\u5728\u8fc724\u5c0f\u65f6\u5185\u51fa\u73b0\u5728\u5934\u6761\u6e90\u4e2d\uff0c\u503c\u5f97\u7ee7\u7eed\u8ddf\u8e2a\u3002"
    return "\u8fd9\u662f\u4eca\u65e5\u70ed\u5ea6\u6392\u540d\u9760\u524d\u7684\u6761\u76ee\u3002"


def _render_source_spotlight(title: str, items: list[dict], limit: int = 3) -> list[str]:
    if not items:
        return []

    lines = [title]
    for index, item in enumerate(items[:limit], start=1):
        name = item.get("title") or "\u672a\u547d\u540d\u6761\u76ee"
        url = item.get("url") or ""
        meta = _format_item_meta(item)
        brief = _build_item_brief(item)
        if url:
            lines.append(f"### {index}. [{name}]({url})")
        else:
            lines.append(f"### {index}. {name}")
        if meta:
            lines.append(f"- \u70ed\u5ea6\uff1a{meta}")
        if brief:
            lines.append(f"- \u770b\u70b9\uff1a{brief}")
    return lines


def _render_source_sections(payload: dict) -> list[list[str]]:
    items = payload.get("items") or {}
    return [
        _render_source_spotlight("## GitHub Trending \u89c2\u5bdf", items.get("github_trending") or []),
        _render_source_spotlight("## Reddit \u89c2\u5bdf", items.get("reddit") or []),
        _render_source_spotlight("## Hacker News \u89c2\u5bdf", items.get("hacker_news") or []),
        _render_source_spotlight("## \u65b0\u95fb\u5934\u6761\u89c2\u5bdf", items.get("news") or []),
    ]


def _fallback_overview(payload: dict) -> str:
    top_trends = payload.get("top_trends") or []
    if not top_trends:
        return "\u4eca\u65e5 AI \u70ed\u70b9\u5df2\u751f\u6210\uff0c\u4f46\u6682\u65f6\u6ca1\u6709\u62bd\u53d6\u5230\u7ed3\u6784\u5316\u6458\u8981\u3002"

    top_names = [item.get("title") for item in top_trends[:3] if item.get("title")]
    joined = "\u3001".join(top_names)
    return f"\u4eca\u65e5 AI \u70ed\u70b9\u4e3b\u8981\u96c6\u4e2d\u5728 {joined}\uff0cGitHub Trending \u4e0e Reddit \u4ecd\u662f\u4e3b\u8981\u70ed\u5ea6\u6765\u6e90\u3002"


def _render_summary_status(summary: dict) -> list[str]:
    if summary:
        return []
    return [
        "## \u6458\u8981\u72b6\u6001",
        "- AI \u6458\u8981\u672c\u6b21\u672a\u542f\u7528\u6216\u8c03\u7528\u5931\u8d25\uff0c\u4e0b\u65b9\u5185\u5bb9\u4e3a\u57fa\u4e8e\u89c4\u5219\u6574\u7406\u7684\u70ed\u70b9\u65e5\u62a5\u3002",
    ]


def render_markdown_report(payload: dict) -> str:
    summary = payload.get("summary") or {}
    generated_at = payload.get("generated_at")
    display_time = _fmt_time(generated_at)
    overview = summary.get("overview") or _fallback_overview(payload)
    closing_note = summary.get("closing_note") or ""

    if _looks_garbled(overview):
        overview = _fallback_overview(payload)
        summary = {}
        closing_note = ""

    lines = [
        "# AI \u70ed\u70b9\u65e5\u62a5",
        "",
        f"> \u66f4\u65b0\u65f6\u95f4\uff1a{display_time}\uff08\u5317\u4eac\u65f6\u95f4\uff09" if display_time else "> AI \u70ed\u70b9\u65e5\u62a5",
        "",
        "## \u4eca\u65e5\u4e00\u53e5\u8bdd",
        overview,
    ]

    if payload.get("counts"):
        counts = payload["counts"]
        lines.extend(
            [
                "",
                "## \u6570\u636e\u6982\u89c8",
                f"- GitHub Trending\uff1a{counts.get('github_trending', 0)}",
                f"- Reddit\uff1a{counts.get('reddit', 0)}",
                f"- Hacker News\uff1a{counts.get('hacker_news', 0)}",
                f"- \u65b0\u95fb\u5934\u6761\uff1a{counts.get('news', 0)}",
            ]
        )

    for section in (
        _render_summary_status(summary),
        _render_named_hotspots(summary),
        _render_source_briefs(summary),
        _render_project_watchlist(summary),
        *_render_source_sections(payload),
        _render_top_trends(payload),
    ):
        if section:
            lines.extend(["", *section])

    notes = payload.get("notes") or []
    if notes:
        lines.extend(["", "## \u5907\u6ce8"])
        lines.extend([f"- {note}" for note in notes])

    if closing_note and not _looks_garbled(closing_note):
        lines.extend(["", "## \u6536\u5c3e\u5224\u65ad", closing_note])

    return "\n".join(lines).strip() + "\n"
