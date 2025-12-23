"""
RSS Feed fetcher executor for the LangGraph pipeline.

This module implements the DataFetchRSS tool that:
- Fetches RSS/Atom feeds using feedparser
- Deduplicates content using etag/modified headers
- Stores items in the EvidenceStore
- Returns ToolResult with evidence IDs
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import feedparser

from src.core.evidence_store import EvidenceStore
from src.core.schemas import ErrorClass, ToolResult


# Dynamic search URL templates
SEARCH_TEMPLATES = {
    "google_news": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
    "reddit_search": "https://www.reddit.com/search.rss?q={query}&sort=new",
}


# Cache file for etag/modified tracking
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
HEADERS_CACHE_FILE = CACHE_DIR / "feed_headers.json"


def _load_headers_cache() -> Dict[str, Dict[str, str]]:
    """Load the cached etag/modified headers."""
    if not HEADERS_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(HEADERS_CACHE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def _save_headers_cache(cache: Dict[str, Dict[str, str]]) -> None:
    """Save the etag/modified headers cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    HEADERS_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def _generate_item_id(item: Dict[str, Any], feed_url: str) -> str:
    """Generate a unique ID for a feed item."""
    # Use guid/id if available, otherwise hash title + link
    unique_key = item.get("id") or item.get("guid") or ""
    if not unique_key:
        unique_key = f"{item.get('title', '')}{item.get('link', '')}"
    
    content = f"{feed_url}:{unique_key}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    """Check if text contains any of the keywords (case-insensitive)."""
    if not keywords:
        return True  # No filter = match all
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _expand_search_url(url: str, query: str = "") -> str:
    """Expand dynamic search URL templates."""
    if "{query}" in url and query:
        return url.replace("{query}", quote_plus(query))
    return url


def fetch_rss(
    url: str,
    max_items: int = 10,
    keywords: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    evidence_store: Optional[EvidenceStore] = None,
) -> ToolResult:
    """
    Fetch and parse an RSS/Atom feed with optional keyword filtering.
    
    Args:
        url: The feed URL to fetch (can contain {query} placeholder)
        max_items: Maximum number of items to process (default: 10)
        keywords: Optional list of keywords to filter items by
        search_query: Query string for dynamic URL expansion
        evidence_store: Optional EvidenceStore instance (creates new if not provided)
        
    Returns:
        ToolResult with evidence_ids for stored items
    """
    if evidence_store is None:
        evidence_store = EvidenceStore()
    
    # Expand dynamic search URL if applicable
    if search_query:
        url = _expand_search_url(url, search_query)
    
    # Load cached headers for conditional fetch
    headers_cache = _load_headers_cache()
    cached = headers_cache.get(url, {})
    
    # Prepare conditional fetch headers
    fetch_kwargs = {}
    if cached.get("etag"):
        fetch_kwargs["etag"] = cached["etag"]
    if cached.get("modified"):
        fetch_kwargs["modified"] = cached["modified"]
    
    # Fetch the feed
    try:
        feed = feedparser.parse(url, **fetch_kwargs)
    except Exception as e:
        return ToolResult(
            status="fail",
            error_class=ErrorClass.TRANSIENT,
            summary=f"Failed to fetch feed: {e}",
            evidence_ids=[],
        )
    
    # Check for HTTP errors
    if hasattr(feed, "status"):
        if feed.status == 304:
            # Not modified - content unchanged
            return ToolResult(
                status="success",
                summary=f"Feed unchanged (304 Not Modified): {url}",
                evidence_ids=[],
            )
        elif feed.status >= 400:
            error_class = ErrorClass.TRANSIENT if feed.status >= 500 else ErrorClass.PERMANENT
            return ToolResult(
                status="fail",
                error_class=error_class,
                summary=f"HTTP {feed.status} fetching {url}",
                evidence_ids=[],
            )
    
    # Check for feed-level errors
    if feed.bozo and not feed.entries:
        return ToolResult(
            status="fail",
            error_class=ErrorClass.VALIDATION,
            summary=f"Invalid feed format: {feed.bozo_exception}",
            evidence_ids=[],
        )
    
    # Update cached headers
    new_cache = {}
    if hasattr(feed, "etag") and feed.etag:
        new_cache["etag"] = feed.etag
    if hasattr(feed, "modified") and feed.modified:
        new_cache["modified"] = feed.modified
    if new_cache:
        headers_cache[url] = new_cache
        _save_headers_cache(headers_cache)
    
    # Process entries
    evidence_ids = []
    items_processed = 0
    
    for entry in feed.entries[:max_items]:
        # Extract item data
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        summary = entry.get("summary", entry.get("description", ""))
        
        # Keyword filtering: skip items that don't match
        if keywords:
            combined_text = f"{title} {summary}"
            if not _matches_keywords(combined_text, keywords):
                continue

        item_data = {
            "title": title,
            "link": link,
            "summary": summary,
            "published": entry.get("published", entry.get("updated", "")),
            "author": entry.get("author", ""),
        }
        
        # Generate unique item ID
        item_id = _generate_item_id(entry, url)
        
        # Check if already in evidence store
        if evidence_store.exists(f"rss_{item_id}"):
            continue
            
        # Validation: Mark as failed if critical fields are missing
        # This allows upstream logic to track "failed" items in lifecycle
        if not link and title == "Untitled":
             evidence_id = evidence_store.save(
                payload={"raw": str(entry)},
                metadata={
                    "type": "failed_rss_item",
                    "source_url": url,
                    "reason": "Missing title and link",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
             evidence_ids.append(evidence_id)
             continue

        # Store valid item
        evidence_id = evidence_store.save(
            payload=item_data,
            metadata={
                "type": "rss_item",
                "source_url": url,
                "feed_title": feed.feed.get("title", "Unknown Feed"),
                "item_hash": item_id,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        
        evidence_ids.append(evidence_id)
        items_processed += 1
    
    # Build summary
    total_entries = len(feed.entries)
    feed_title = feed.feed.get("title", "Unknown Feed")
    
    return ToolResult(
        status="success",
        summary=f"Fetched {items_processed} new items from '{feed_title}' "
                f"({total_entries} total in feed, max {max_items} requested)",
        evidence_ids=evidence_ids,
        payload_ref=url,
    )


def execute_data_fetch_rss(params: Dict[str, Any]) -> ToolResult:
    """
    Execute DataFetchRSS action from ProposedAction params.
    
    This is the main entry point called by the executor node.
    
    Args:
        params: Dict containing:
            - url: Feed URL (required, can use 'google_news' or 'reddit_search' shortcuts)
            - max_items: Max items to fetch (optional, default 10)
            - keywords: List of keywords to filter by (optional)
            - search_query: Query for dynamic URL expansion (optional)
        
    Returns:
        ToolResult from fetch_rss
    """
    url = params.get("url")
    if not url:
        return ToolResult(
            status="fail",
            error_class=ErrorClass.VALIDATION,
            summary="Missing required 'url' parameter",
            evidence_ids=[],
        )
    
    # Resolve URL shortcuts
    if url in SEARCH_TEMPLATES:
        url = SEARCH_TEMPLATES[url]
    
    max_items = params.get("max_items", 10)
    keywords = params.get("keywords", [])
    search_query = params.get("search_query", "")
    
    return fetch_rss(
        url=url,
        max_items=max_items,
        keywords=keywords,
        search_query=search_query
    )
