"""
UC3 — News Fetch & Summarizer Tool
=====================================
Provides:
  - fetch_latest_news(query, limit) → list of articles
  - build_news_summary_prompt(news)  → prompt for LLM

API keys loaded from environment, never hardcoded.
"""

import os
import requests
from typing import Union, List

from src.tools.schemas import (
    NewsInput,
    NewsArticle,
    NewsOutput,
    ToolError,
)
from src.telemetry.logger import logger

# ── Constants ────────────────────────────────────────────────
NEWSAPI_BASE = "https://newsapi.org/v2/everything"
REQUEST_TIMEOUT = 10


def _get_news_api_key() -> str:
    """Retrieve API key from environment; raise if missing."""
    key = os.getenv("NEWS_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "NEWS_API_KEY not found in environment. "
            "Add it to your .env file."
        )
    return key


# ── Tool 1: News Fetch ──────────────────────────────────────
def fetch_latest_news(
    query: str = "Bitcoin",
    limit: int = 5,
) -> Union[NewsOutput, ToolError]:
    """
    Kéo tin tức mới nhất về keyword từ NewsAPI.
    Agent gọi khi user hỏi: "Có tin tức gì mới về Bitcoin?"
    """
    try:
        validated = NewsInput(query=query, limit=limit)

        logger.log_event("TOOL_CALL", {
            "tool": "fetch_latest_news",
            "input": validated.model_dump(),
        })

        api_key = _get_news_api_key()

        params = {
            "q": validated.query,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": validated.limit,
            "apiKey": api_key,
        }

        response = requests.get(
            NEWSAPI_BASE,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        raw_articles = data.get("articles", [])
        articles: List[NewsArticle] = []

        for art in raw_articles:
            title = art.get("title")
            if not title or title == "[Removed]":
                continue
            articles.append(
                NewsArticle(
                    title=title,
                    description=art.get("description"),
                    url=art.get("url", ""),
                    published_at=art.get("publishedAt", ""),
                )
            )

        result = NewsOutput(
            query=validated.query,
            total_results=len(articles),
            articles=articles,
        )

        logger.log_event("TOOL_RESULT", {
            "tool": "fetch_latest_news",
            "total_results": result.total_results,
        })
        return result

    except EnvironmentError as exc:
        return ToolError(
            tool_name="fetch_latest_news",
            error_type="ConfigError",
            message=str(exc),
            recoverable=False,
        )

    except requests.exceptions.Timeout:
        return ToolError(
            tool_name="fetch_latest_news",
            error_type="TimeoutError",
            message=f"NewsAPI timeout cho '{query}'.",
        )

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response else "unknown"
        msg = f"NewsAPI trả lỗi {status}."
        if status == 401:
            msg += " API key không hợp lệ hoặc hết hạn."
        elif status == 429:
            msg += " Đã hết quota request."
        return ToolError(
            tool_name="fetch_latest_news",
            error_type="HTTPError",
            message=msg,
        )

    except Exception as exc:
        return ToolError(
            tool_name="fetch_latest_news",
            error_type=type(exc).__name__,
            message=f"Lỗi khi kéo tin {query}: {str(exc)}",
        )


# ── Tool 2: Summarizer Prompt Builder ───────────────────────
def build_news_summary_prompt(
    news: NewsOutput,
    context_keyword: str = "Bitcoin",
) -> str:
    """
    Gom các bài báo thành prompt cho LLM tóm tắt.
    Trả về chuỗi prompt chuẩn (không gọi LLM trực tiếp).
    """
    if not news.articles:
        return "Không có tin tức nào mới để phân tích."

    combined = ""
    for i, article in enumerate(news.articles, 1):
        combined += (
            f"\n[Tin {i}]\n"
            f"- Tiêu đề: {article.title}\n"
            f"- Mô tả: {article.description or 'N/A'}\n"
            f"- Thời gian: {article.published_at}\n"
        )

    return (
        f"Bạn là chuyên gia phân tích Crypto.\n"
        f"Context hiện tại: {context_keyword}.\n\n"
        f"Dưới đây là {len(news.articles)} tin tức mới nhất:\n"
        f"{combined}\n"
        f"Nhiệm vụ:\n"
        f"1. Tóm tắt các sự kiện chính (3-4 gạch đầu dòng).\n"
        f"2. Phân tích ảnh hưởng: Bullish / Bearish / Neutral đến {context_keyword}.\n"
        f"3. Đưa ra 1 câu kết luận ngắn cho nhà đầu tư.\n"
    )