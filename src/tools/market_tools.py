"""
Market Data Tools

These tools replace the deprecated ResearcherAgent by providing direct access
to market data, news, and sentiment analysis. Currently uses mock data,
implementing the interface defined in the legacy researcher.skill.md.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from src.core.evidence_store import EvidenceStore
from src.core.schemas import ToolResult

# ============================================================================
# MOCK DATASETS
# ============================================================================

SOURCE_URLS = {
    'price': 'https://api.alpaca.markets/v2/stocks/{ticker}/trades',
    'news': 'https://api.polygon.io/v2/reference/news?ticker={ticker}',
    'sentiment': 'https://api.socialsentiment.io/v1/{ticker}',
    'catalyst': 'https://api.earningswhispers.com/v1/{ticker}',
    'technical': 'https://api.tradingview.com/indicators/{ticker}',
}

TRUST_TIERS = {
    'price': 1,  # Official API
    'news': 2,   # Major sources
    'sentiment': 3,
    'catalyst': 3,
    'technical': 2,
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _generate_evidence_id(ticker: str, query_type: str, seed_suffix: str = "") -> str:
    """Generate a deterministic evidence ID."""
    raw = f"{ticker}:{query_type}:{datetime.now().strftime('%H%M')}:{seed_suffix}"
    hash_part = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
    return f"EV-{hash_part}"

def _save_evidence(evidence_data: Dict[str, Any]) -> str:
    """Save raw evidence to store and return ID."""
    store = EvidenceStore()
    
    # Extract metadata fields
    eid = evidence_data["evidence_id"]
    
    metadata = {
        "source_url": evidence_data["source_url"],
        "source_trust_tier": evidence_data["source_trust_tier"],
        "fetched_at": evidence_data["fetched_at"],
        "type": evidence_data["type"],
        "query_hash": None, # Tools don't know the query hash context directly
        "lifecycle": "active"
    }
    
    store.save(
        payload=evidence_data,
        metadata=metadata,
        custom_id=eid
    )
    return eid

# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

def fetch_market_data(params: Dict[str, Any]) -> ToolResult:
    """
    Fetch price and volume data for a ticker.
    
    Args:
        params: {"ticker": "str"}
    """
    ticker = params.get("ticker", "UNKNOWN").upper()
    
    # Mock Response
    evidence_id = _generate_evidence_id(ticker, "price")
    
    data = {
        "evidence_id": evidence_id,
        "type": "market_data",
        "ticker": ticker,
        "price": 150.25,
        "change_percent": 1.2,
        "volume": 1500000,
        "source_url": SOURCE_URLS['price'].format(ticker=ticker),
        "source_trust_tier": TRUST_TIERS['price'],
        "fetched_at": datetime.now().isoformat(),
        "title": f"Market Data for {ticker}",
        "summary": f"{ticker} trading at $150.25 (+1.2%) with volume 1.5M."
    }
    
    _save_evidence(data)
    
    return ToolResult(
        tool_name="fetch_market_data",
        is_success=True,
        summary=f"Fetched price data for {ticker}",
        evidence_ids=[evidence_id]
    )


def fetch_news(params: Dict[str, Any]) -> ToolResult:
    """
    Fetch recent news for a ticker.
    
    Args:
        params: {"ticker": "str", "limit": int}
    """
    ticker = params.get("ticker", "UNKNOWN").upper()
    limit = params.get("limit", 3)
    
    evidence_ids = []
    
    for i in range(min(limit, 3)):
        evidence_id = _generate_evidence_id(ticker, "news", str(i))
        
        data = {
            "evidence_id": evidence_id,
            "type": "news_article",
            "ticker": ticker,
            "headline": f"Breaking news {i+1} about {ticker}",
            "source": "Financial Times" if i == 0 else "Bloomberg",
            "url": f"https://example.com/news/{ticker}/{i}",
            "source_url": SOURCE_URLS['news'].format(ticker=ticker),
            "source_trust_tier": TRUST_TIERS['news'],
            "fetched_at": datetime.now().isoformat(),
            "title": f"News: {ticker} expansion plans revealed",
            "summary": f"Reports suggest {ticker} is planning a major expansion in Q3. Analysts are optimistic."
        }
        
        _save_evidence(data)
        evidence_ids.append(evidence_id)
        
    return ToolResult(
        tool_name="fetch_news",
        is_success=True,
        summary=f"Fetched {len(evidence_ids)} news items for {ticker}",
        evidence_ids=evidence_ids
    )


def fetch_sentiment(params: Dict[str, Any]) -> ToolResult:
    """
    Fetch social sentiment analysis for a ticker.
    
    Args:
        params: {"ticker": "str"}
    """
    ticker = params.get("ticker", "UNKNOWN").upper()
    
    evidence_id = _generate_evidence_id(ticker, "sentiment")
    
    data = {
        "evidence_id": evidence_id,
        "type": "sentiment_analysis",
        "ticker": ticker,
        "sentiment_score": 0.75, # -1 to 1
        "mention_volume": "High",
        "trending_topics": ["earnings", "products", "ceo"],
        "source_url": SOURCE_URLS['sentiment'].format(ticker=ticker),
        "source_trust_tier": TRUST_TIERS['sentiment'],
        "fetched_at": datetime.now().isoformat(),
        "title": f"Sentiment Analysis for {ticker}",
        "summary": f"Social sentiment for {ticker} is bullish (0.75) with high mention volume."
    }
    
    _save_evidence(data)
    
    return ToolResult(
        tool_name="fetch_sentiment",
        is_success=True,
        summary=f"Fetched sentiment analysis for {ticker}",
        evidence_ids=[evidence_id]
    )
