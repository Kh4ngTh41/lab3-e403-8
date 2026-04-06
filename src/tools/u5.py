"""
UC5 — Decision Evaluator Tool (AI Agent)
==========================================
Combines all data from UC1-UC4 and applies rule-based scoring
to produce a Buy/Hold/Sell suggestion.

NOTE: This is NOT financial advice. For educational purposes only.
"""

from typing import Union

from src.tools.schemas import (
    DecisionInput,
    DecisionOutput,
    DecisionType,
    RiskLevel,
    SentimentType,
    ToolError,
    CryptoPriceOutput,
    PriceAnalysisOutput,
    NewsOutput,
)
from src.tools.u4 import aggregate_crypto_summary
from src.tools.schemas import SummaryOutput
from src.telemetry.logger import logger


# ── Rule-based Scoring Engine ────────────────────────────────

def _score_price_momentum(price_data: CryptoPriceOutput) -> float:
    """Score based on 24h price change. Range: [-1, +1]"""
    pct = price_data.change_24h_pct
    if pct > 5:
        return 1.0
    elif pct > 2:
        return 0.6
    elif pct > 0:
        return 0.3
    elif pct > -2:
        return -0.2
    elif pct > -5:
        return -0.6
    else:
        return -1.0


def _score_trend(trend_data: PriceAnalysisOutput) -> float:
    """Score based on 7-day trend. Range: [-1, +1]"""
    if trend_data.trend == "UP":
        magnitude = min(trend_data.change_pct / 20, 1.0)
        return max(0.3, magnitude)
    elif trend_data.trend == "DOWN":
        magnitude = max(trend_data.change_pct / 20, -1.0)
        return min(-0.3, magnitude)
    return 0.0


def _score_news_sentiment(news_data: NewsOutput) -> float:
    """
    Heuristic news sentiment via keyword matching.
    In production, replace with NLP / LLM sentiment analysis.
    """
    if not news_data.articles:
        return 0.0

    positive_keywords = [
        "rally", "surge", "bullish", "adoption", "approval",
        "etf", "institutional", "growth", "partnership", "record",
        "breakout", "support",
    ]
    negative_keywords = [
        "crash", "bearish", "hack", "ban", "regulation", "fraud",
        "investigation", "decline", "selloff", "sell-off", "loss",
        "lawsuit", "warning",
    ]

    score = 0.0
    for article in news_data.articles:
        text = (
            (article.title or "") + " " + (article.description or "")
        ).lower()
        for kw in positive_keywords:
            if kw in text:
                score += 0.15
        for kw in negative_keywords:
            if kw in text:
                score -= 0.15

    # Clamp to [-1, 1]
    return max(-1.0, min(1.0, score))


def _derive_decision(total_score: float) -> DecisionType:
    if total_score > 0.3:
        return DecisionType.BUY
    elif total_score < -0.3:
        return DecisionType.SELL
    return DecisionType.HOLD


def _derive_risk(total_score: float) -> RiskLevel:
    abs_score = abs(total_score)
    if abs_score > 0.7:
        return RiskLevel.LOW   # Strong signal = lower risk of wrong call
    elif abs_score > 0.3:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH  # Weak signal = high uncertainty


def _build_reasoning(
    price_score: float,
    trend_score: float,
    news_score: float,
    decision: DecisionType,
) -> str:
    parts = []

    # Price momentum
    if price_score > 0:
        parts.append(f"Giá 24h có momentum tích cực (score: {price_score:+.1f}).")
    elif price_score < 0:
        parts.append(f"Giá 24h giảm (score: {price_score:+.1f}).")
    else:
        parts.append("Giá 24h ổn định.")

    # Trend
    if trend_score > 0:
        parts.append(f"Xu hướng 7 ngày tăng (score: {trend_score:+.1f}).")
    elif trend_score < 0:
        parts.append(f"Xu hướng 7 ngày giảm (score: {trend_score:+.1f}).")
    else:
        parts.append("Xu hướng 7 ngày đi ngang.")

    # News
    if news_score > 0:
        parts.append(f"Tin tức nghiêng về Bullish (score: {news_score:+.1f}).")
    elif news_score < 0:
        parts.append(f"Tin tức nghiêng về Bearish (score: {news_score:+.1f}).")
    else:
        parts.append("Tin tức trung lập.")

    parts.append(f"→ Kết luận: {decision.value}.")
    return " ".join(parts)


# ── Main Tool ────────────────────────────────────────────────

def evaluate_investment(
    symbol: str = "BTC",
) -> Union[DecisionOutput, ToolError]:
    """
    Đánh giá tổng hợp và đưa ra gợi ý Buy/Hold/Sell.
    Agent gọi khi user hỏi: "Tôi có nên mua BTC lúc này không?"
    """
    try:
        validated = DecisionInput(symbol=symbol)
        sym = validated.symbol

        logger.log_event("TOOL_CALL", {
            "tool": "evaluate_investment",
            "input": {"symbol": sym},
        })

        # ── Gather aggregated data from UC4 ──
        summary = aggregate_crypto_summary(sym)

        if isinstance(summary, ToolError):
            return summary  # Propagate error

        # ── Score each dimension ──
        price_score = 0.0
        trend_score = 0.0
        news_score = 0.0

        if summary.price_data:
            price_score = _score_price_momentum(summary.price_data)
        if summary.trend_data:
            trend_score = _score_trend(summary.trend_data)
        if summary.news_data:
            news_score = _score_news_sentiment(summary.news_data)

        # Weighted average — price & trend matter more than news heuristic
        total_score = (
            price_score * 0.35
            + trend_score * 0.40
            + news_score * 0.25
        )

        decision = _derive_decision(total_score)
        risk = _derive_risk(total_score)
        confidence = round(min(abs(total_score) + 0.3, 1.0), 2)
        reasoning = _build_reasoning(price_score, trend_score, news_score, decision)

        result = DecisionOutput(
            symbol=sym,
            decision=decision,
            confidence=confidence,
            risk_level=risk,
            reasoning=reasoning,
        )

        logger.log_event("TOOL_RESULT", {
            "tool": "evaluate_investment",
            "output": result.model_dump(),
        })
        return result

    except Exception as exc:
        return ToolError(
            tool_name="evaluate_investment",
            error_type=type(exc).__name__,
            message=f"Lỗi khi đánh giá {symbol}: {str(exc)}",
        )
