"""
UC4 — Aggregator & Summary Tool (Context-aware)
=================================================
Combines data from UC1 (price), UC2 (trend), UC3 (news)
into one unified context for the LLM to summarize.
"""

from typing import Union

from src.tools.schemas import (
    SummaryInput,
    SummaryOutput,
    ToolError,
    CryptoPriceOutput,
    PriceAnalysisOutput,
    NewsOutput,
)
from src.tools.u1 import get_crypto_price
from src.tools.u2 import get_price_trend
from src.tools.u3 import fetch_latest_news
from src.telemetry.logger import logger


def aggregate_crypto_summary(
    symbol: str = "BTC",
) -> Union[SummaryOutput, ToolError]:
    """
    Gom dữ liệu từ UC1 + UC2 + UC3 thành một summary prompt.
    Agent gọi khi user hỏi: "Tóm tắt tình hình Bitcoin hiện tại"
    """
    try:
        validated = SummaryInput(symbol=symbol)
        sym = validated.symbol

        logger.log_event("TOOL_CALL", {
            "tool": "aggregate_crypto_summary",
            "input": {"symbol": sym},
        })

        # ── Gather data from sub-tools (graceful degradation) ──
        price_data = None
        trend_data = None
        news_data = None

        # UC1: Price
        price_result = get_crypto_price(sym)
        if isinstance(price_result, CryptoPriceOutput):
            price_data = price_result

        # UC2: Trend (7 days)
        trend_result = get_price_trend(sym, days=7)
        if isinstance(trend_result, PriceAnalysisOutput):
            trend_data = trend_result

        # UC3: News
        news_result = fetch_latest_news(query=sym, limit=3)
        if isinstance(news_result, NewsOutput):
            news_data = news_result

        # ── Build aggregated prompt ──
        sections = []

        if price_data:
            sections.append(
                f"[GIA HIEN TAI]\n"
                f"- {price_data.name} ({price_data.symbol}): ${price_data.price_usd:,.2f}\n"
                f"- Thay đổi 24h: {price_data.change_24h_pct:+.2f}%\n"
            )
        else:
            sections.append("[GIA HIEN TAI] Khong lay duoc du lieu gia.\n")

        if trend_data:
            sections.append(
                f"[XU HUONG {trend_data.days} NGAY]\n"
                f"- Giá đầu kỳ: ${trend_data.start_price:,.2f}\n"
                f"- Giá cuối kỳ: ${trend_data.end_price:,.2f}\n"
                f"- Thay đổi: {trend_data.change_pct:+.2f}%\n"
                f"- Cao nhất: ${trend_data.high:,.2f} | Thấp nhất: ${trend_data.low:,.2f}\n"
                f"- Xu hướng: {trend_data.trend}\n"
            )
        else:
            sections.append("[XU HUONG] Khong lay duoc du lieu trend.\n")

        if news_data and news_data.articles:
            news_section = f"[TIN TUC GAN DAY] ({news_data.total_results} bai):\n"
            for i, art in enumerate(news_data.articles, 1):
                news_section += f"  {i}. {art.title}\n"
            sections.append(news_section)
        else:
            sections.append("[TIN TUC] Khong co tin tuc moi.\n")

        aggregated_prompt = (
            f"Bạn là chuyên gia phân tích Crypto. Hãy tóm tắt tình hình {sym} dựa trên dữ liệu sau:\n\n"
            + "\n".join(sections)
            + "\nHãy đưa ra đánh giá tổng quan ngắn gọn cho nhà đầu tư."
        )

        result = SummaryOutput(
            symbol=sym,
            price_data=price_data,
            trend_data=trend_data,
            news_data=news_data,
            aggregated_prompt=aggregated_prompt,
        )

        logger.log_event("TOOL_RESULT", {
            "tool": "aggregate_crypto_summary",
            "has_price": price_data is not None,
            "has_trend": trend_data is not None,
            "has_news": news_data is not None,
        })
        return result

    except Exception as exc:
        return ToolError(
            tool_name="aggregate_crypto_summary",
            error_type=type(exc).__name__,
            message=f"Lỗi khi tổng hợp dữ liệu {symbol}: {str(exc)}",
        )
