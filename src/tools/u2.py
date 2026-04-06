"""
UC2 — Price Trend Analysis Tool (Calculation + API)
=====================================================
Provides:
  - get_price_trend(symbol, days)  → % change over N days

Uses CoinGecko market_chart endpoint for historical data,
then applies a Calculator tool to derive metrics.
"""

import requests
from typing import Union

from src.tools.schemas import (
    PriceAnalysisInput,
    PriceAnalysisOutput,
    ToolError,
)
from src.telemetry.logger import logger

# ── Constants ────────────────────────────────────────────────
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT = 15  # CoinGecko can be slower

# Map common symbols → CoinGecko IDs
SYMBOL_TO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
}


def _resolve_coingecko_id(symbol: str) -> str:
    """Resolve a ticker symbol to a CoinGecko API id."""
    return SYMBOL_TO_ID.get(symbol, symbol.lower())


# ── Calculator helpers ───────────────────────────────────────
def _calculate_change_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return round(((end - start) / start) * 100, 2)


def _classify_trend(change_pct: float) -> str:
    if change_pct > 1.0:
        return "UP"
    elif change_pct < -1.0:
        return "DOWN"
    return "SIDEWAYS"


# ── Main Tool ────────────────────────────────────────────────
def get_price_trend(
    symbol: str = "BTC",
    days: int = 7,
) -> Union[PriceAnalysisOutput, ToolError]:
    """
    Phân tích xu hướng giá N ngày gần nhất.
    Agent gọi khi user hỏi: "BTC tăng bao nhiêu % trong 7 ngày?"
    """
    try:
        validated = PriceAnalysisInput(symbol=symbol, days=days)
        sym = validated.symbol
        coin_id = _resolve_coingecko_id(sym)

        logger.log_event("TOOL_CALL", {
            "tool": "get_price_trend",
            "input": {"symbol": sym, "days": validated.days},
        })

        # ── Call CoinGecko market_chart ──
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": validated.days}

        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        prices = data.get("prices", [])
        if len(prices) < 2:
            return ToolError(
                tool_name="get_price_trend",
                error_type="InsufficientData",
                message=f"Không đủ dữ liệu giá cho {sym} trong {validated.days} ngày.",
            )

        # ── Calculator: derive metrics ──
        price_values = [p[1] for p in prices]
        start_price = price_values[0]
        end_price = price_values[-1]
        change_pct = _calculate_change_pct(start_price, end_price)

        result = PriceAnalysisOutput(
            symbol=sym,
            days=validated.days,
            start_price=round(start_price, 2),
            end_price=round(end_price, 2),
            change_pct=change_pct,
            high=round(max(price_values), 2),
            low=round(min(price_values), 2),
            trend=_classify_trend(change_pct),
        )

        logger.log_event("TOOL_RESULT", {
            "tool": "get_price_trend",
            "output": result.model_dump(),
        })
        return result

    except requests.exceptions.Timeout:
        return ToolError(
            tool_name="get_price_trend",
            error_type="TimeoutError",
            message=f"CoinGecko timeout cho {symbol} (>{REQUEST_TIMEOUT}s).",
        )

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response else "unknown"
        return ToolError(
            tool_name="get_price_trend",
            error_type="HTTPError",
            message=f"CoinGecko trả lỗi {status} cho {symbol}. Có thể bị rate-limit.",
        )

    except requests.exceptions.ConnectionError:
        return ToolError(
            tool_name="get_price_trend",
            error_type="ConnectionError",
            message="Không kết nối được CoinGecko. Kiểm tra internet.",
            recoverable=False,
        )

    except Exception as exc:
        return ToolError(
            tool_name="get_price_trend",
            error_type=type(exc).__name__,
            message=f"Lỗi khi phân tích trend {symbol}: {str(exc)}",
        )
