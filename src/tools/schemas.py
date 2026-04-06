"""
Pydantic schemas for all tool inputs/outputs.
Ensures type safety and validation across the entire agent pipeline.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ============================================================
# Enums
# ============================================================

class SentimentType(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class DecisionType(str, Enum):
    BUY = "Buy"
    SELL = "Sell"
    HOLD = "Hold"


# ============================================================
# UC1 — Crypto Price Schemas
# ============================================================

class CryptoPriceInput(BaseModel):
    """Input schema for get_crypto_price tool."""
    symbol: str = Field(
        default="BTC",
        description="Crypto symbol, e.g. BTC, ETH, SOL"
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        return v.strip().upper()


class CryptoPriceOutput(BaseModel):
    """Output schema for get_crypto_price tool."""
    symbol: str
    name: str
    price_usd: float
    price_yesterday: float
    change_24h_pct: float = Field(
        default=0.0,
        description="Percentage change vs yesterday"
    )
    last_updated: Optional[str] = None


class MultiCryptoPriceInput(BaseModel):
    """Input schema for getting multiple coin prices."""
    symbols: List[str] = Field(
        default=["BTC"],
        description="List of crypto symbols"
    )

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        return [s.strip().upper() for s in v]


# ============================================================
# UC2 — Price Analysis Schemas
# ============================================================

class PriceAnalysisInput(BaseModel):
    """Input schema for price trend analysis."""
    symbol: str = Field(default="BTC", description="Crypto symbol to analyze")
    days: int = Field(default=7, ge=1, le=365, description="Number of days to look back")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        return v.strip().upper()


class PriceAnalysisOutput(BaseModel):
    """Output schema for price trend analysis."""
    symbol: str
    days: int
    start_price: float
    end_price: float
    change_pct: float
    high: float
    low: float
    trend: str = Field(description="UP / DOWN / SIDEWAYS")


# ============================================================
# UC3 — News Schemas
# ============================================================

class NewsInput(BaseModel):
    """Input schema for news fetch tool."""
    query: str = Field(default="Bitcoin", description="Search keyword")
    limit: int = Field(default=5, ge=1, le=20, description="Max articles to fetch")


class NewsArticle(BaseModel):
    """Schema for a single news article."""
    title: str
    description: Optional[str] = None
    url: str
    published_at: str


class NewsOutput(BaseModel):
    """Output schema for news fetch tool."""
    query: str
    total_results: int
    articles: List[NewsArticle]


# ============================================================
# UC4 — Summary Schemas
# ============================================================

class SummaryInput(BaseModel):
    """Input schema for the summarizer/aggregator."""
    symbol: str = Field(default="BTC")
    include_price: bool = Field(default=True)
    include_trend: bool = Field(default=True)
    include_news: bool = Field(default=True)


class SummaryOutput(BaseModel):
    """Output schema: aggregated context for LLM."""
    symbol: str
    price_data: Optional[CryptoPriceOutput] = None
    trend_data: Optional[PriceAnalysisOutput] = None
    news_data: Optional[NewsOutput] = None
    aggregated_prompt: str = Field(
        description="Ready-to-use prompt for LLM summarization"
    )


# ============================================================
# UC5 — Decision Schemas
# ============================================================

class DecisionInput(BaseModel):
    """Input schema for the decision evaluator."""
    symbol: str = Field(default="BTC")


class DecisionOutput(BaseModel):
    """Output schema: AI-powered investment suggestion."""
    symbol: str
    decision: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    reasoning: str
    disclaimer: str = Field(
        default="DISCLAIMER: This is NOT financial advice. Always do your own research (DYOR)."
    )


# ============================================================
# Generic Tool Error Schema
# ============================================================

class ToolError(BaseModel):
    """Standard error envelope for tool failures."""
    tool_name: str
    error_type: str
    message: str
    recoverable: bool = True
