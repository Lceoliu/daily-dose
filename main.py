import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fetchers.github_trending import fetch_github_trending
from fetchers.google_trends import fetch_news_headlines
from fetchers.social_media import (
    fetch_hacker_news_posts,
    fetch_reddit_posts,
)
from outputs.email import send_markdown_email
from outputs.telegram import render_markdown_report
from ranking import rank_items, top_ranked_items
from summarizer import summarize_payload


OUTPUT_PATH = Path("outputs/latest_trends.json")
MARKDOWN_OUTPUT_PATH = Path("outputs/latest_trends.md")
REPORTS_DIR = Path("reports")
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _print_payload(payload: dict) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except ValueError:
            pass
    try:
        print(rendered)
    except UnicodeEncodeError:
        print(rendered.encode("utf-8", errors="replace").decode("utf-8"))


def _run_fetcher(name: str, fetcher, **kwargs) -> tuple[list[dict], str | None]:
    try:
        return fetcher(**kwargs), None
    except Exception as exc:  # noqa: BLE001
        return [], f"{name} fetch failed: {exc}"


def _run_summary(payload: dict) -> tuple[dict | None, str | None]:
    try:
        return summarize_payload(payload), None
    except Exception as exc:  # noqa: BLE001
        return None, f"AI summary failed: {exc}"


def _run_email(markdown_path: Path) -> str | None:
    try:
        return send_markdown_email(markdown_path)
    except Exception as exc:  # noqa: BLE001
        return f"Email failed: {exc}"


def _report_date_label(payload: dict) -> str:
    generated_at = payload.get("generated_at")
    if generated_at:
        try:
            dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            return dt.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")


def _persist_outputs(payload: dict) -> None:
    markdown = render_markdown_report(payload)
    report_date = _report_date_label(payload)
    archive_dir = REPORTS_DIR / "archive"
    report_targets = {
        OUTPUT_PATH: json.dumps(payload, ensure_ascii=False, indent=2),
        MARKDOWN_OUTPUT_PATH: markdown,
        REPORTS_DIR / "latest_trends.json": json.dumps(payload, ensure_ascii=False, indent=2),
        REPORTS_DIR / "latest_trends.md": markdown,
        archive_dir / f"{report_date}.json": json.dumps(payload, ensure_ascii=False, indent=2),
        archive_dir / f"{report_date}.md": markdown,
    }

    for path, content in report_targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main() -> None:
    github_trending_items, github_trending_error = _run_fetcher(
        "GitHub Trending",
        fetch_github_trending,
        limit_per_feed=10,
    )
    reddit_items, reddit_error = _run_fetcher(
        "Reddit",
        fetch_reddit_posts,
        limit_per_subreddit=5,
    )
    hacker_news_items, hacker_news_error = _run_fetcher(
        "Hacker News",
        fetch_hacker_news_posts,
        limit=10,
    )
    news_items, news_error = _run_fetcher("News", fetch_news_headlines, limit=10)

    notes: list[str] = []
    if github_trending_error:
        notes.append(github_trending_error)
    if reddit_error:
        notes.append(reddit_error)
    if hacker_news_error:
        notes.append(hacker_news_error)
    if news_error:
        notes.append(news_error)

    ranked_items = rank_items(
        {
            "github_trending": github_trending_items,
            "reddit": reddit_items,
            "hacker_news": hacker_news_items,
            "news": news_items,
        }
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "github_trending": len(ranked_items["github_trending"]),
            "reddit": len(ranked_items["reddit"]),
            "hacker_news": len(ranked_items["hacker_news"]),
            "news": len(ranked_items["news"]),
        },
        "items": ranked_items,
        "top_trends": top_ranked_items(ranked_items, limit=15),
        "notes": notes,
    }
    summary, summary_error = _run_summary(payload)
    if summary_error:
        payload["notes"].append(summary_error)
    payload["summary"] = summary
    if summary and summary.get("_errors"):
        payload["notes"].extend([f"AI summary partial failure: {message}" for message in summary["_errors"]])

    _persist_outputs(payload)
    email_result = _run_email(MARKDOWN_OUTPUT_PATH)
    if email_result:
        payload["notes"].append(email_result)
        _persist_outputs(payload)

    _print_payload(payload)


if __name__ == "__main__":
    main()
