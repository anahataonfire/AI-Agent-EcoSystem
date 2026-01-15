"""
Neobrother Position Scraper

Scrapes the current positions from @neobrother's Polymarket profile.
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class TraderPosition:
    """A position held by a trader."""
    market_question: str
    outcome: str  # "Yes" or "No"
    shares: float
    avg_price: float
    current_price: float
    value: float
    pnl: float
    slug: str

@dataclass
class TraderStats:
    """Trader profile statistics."""
    username: str
    wallet: str
    total_profit: float
    predictions: int
    biggest_win: float
    positions_value: float


EXTRACTION_SCRIPT = """
(() => {
    const nextData = document.querySelector('#__NEXT_DATA__');
    if (!nextData) return { error: "No __NEXT_DATA__ found" };
    
    const data = JSON.parse(nextData.textContent);
    const pageProps = data.props?.pageProps || {};
    
    // Extract user profile
    const user = pageProps.user || pageProps.profile || {};
    
    // Extract positions from the page
    const positions = [];
    
    // Try to find positions in the dehydrated state
    const queries = pageProps.dehydratedState?.queries || [];
    queries.forEach(q => {
        if (q.state?.data?.positions) {
            q.state.data.positions.forEach(p => {
                positions.push({
                    question: p.market?.question || p.title,
                    outcome: p.outcome || (p.side === 'YES' ? 'Yes' : 'No'),
                    shares: p.size || p.shares || 0,
                    avgPrice: p.avgPrice || p.average_price || 0,
                    currentPrice: p.currentPrice || 0,
                    value: p.value || 0,
                    pnl: p.pnl || p.profit || 0,
                    slug: p.market?.slug || p.slug
                });
            });
        }
    });
    
    // Also try to parse from visible table
    const rows = document.querySelectorAll('[data-testid="position-row"], .position-row, table tbody tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('td, [class*="cell"]');
        if (cells.length >= 3) {
            const questionEl = row.querySelector('a[href*="/market/"]');
            const outcomeEl = row.querySelector('[class*="outcome"], [class*="side"]');
            positions.push({
                question: questionEl?.textContent?.trim() || 'Unknown',
                outcome: outcomeEl?.textContent?.trim() || 'Yes',
                shares: 0,
                avgPrice: 0,
                currentPrice: 0,
                value: 0,
                pnl: 0,
                slug: questionEl?.href?.split('/market/')[1]
            });
        }
    });
    
    return {
        username: user.username || user.name,
        wallet: user.proxyWallet || user.wallet,
        pnl: user.pnl || user.profit,
        tradesCount: user.marketsTraded || user.tradesCount,
        positionsValue: user.positionsValue,
        positions: positions
    };
})()
"""


def scrape_neobrother_positions() -> tuple[Optional[TraderStats], List[TraderPosition]]:
    """
    Scrape neobrother's positions using Playwright.
    
    Returns:
        Tuple of (TraderStats, List of positions)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return None, []
    
    positions = []
    stats = None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.set_default_timeout(30000)
            
            logger.info("Navigating to neobrother's profile...")
            page.goto("https://polymarket.com/@neobrother", wait_until="networkidle")
            
            # Wait for positions to load
            page.wait_for_timeout(3000)
            
            # Click on Positions tab if available
            try:
                positions_tab = page.locator('text="Positions"').first
                if positions_tab:
                    positions_tab.click()
                    page.wait_for_timeout(2000)
            except:
                pass
            
            # Extract data
            result = page.evaluate(EXTRACTION_SCRIPT)
            
            browser.close()
            
            if result and not result.get("error"):
                stats = TraderStats(
                    username=result.get("username", "neobrother"),
                    wallet=result.get("wallet", "0x6297b93ea37ff92a57fd636410f3b71ebf74517e"),
                    total_profit=result.get("pnl", 20306.09),
                    predictions=result.get("tradesCount", 2090),
                    biggest_win=4804.12,  # Not available via API
                    positions_value=result.get("positionsValue", 0)
                )
                
                for p in result.get("positions", []):
                    positions.append(TraderPosition(
                        market_question=p.get("question", ""),
                        outcome=p.get("outcome", "Yes"),
                        shares=float(p.get("shares", 0)),
                        avg_price=float(p.get("avgPrice", 0)),
                        current_price=float(p.get("currentPrice", 0)),
                        value=float(p.get("value", 0)),
                        pnl=float(p.get("pnl", 0)),
                        slug=p.get("slug", "")
                    ))
                
                logger.info(f"Found {len(positions)} positions for {stats.username}")
            
    except Exception as e:
        logger.error(f"Error scraping neobrother: {e}")
    
    return stats, positions


def get_neobrother_data() -> dict:
    """
    Get neobrother's data as a JSON-serializable dict.
    """
    stats, positions = scrape_neobrother_positions()
    
    if not stats:
        # Return cached fallback
        return {
            "username": "neobrother",
            "wallet": "0x6297b93ea37ff92a57fd636410f3b71ebf74517e",
            "stats": {
                "totalProfit": 20306.09,
                "predictions": 2090,
                "biggestWin": 4804.12,
                "positionsValue": 0
            },
            "positions": [],
            "error": "Scraping failed - using cached stats"
        }
    
    return {
        "username": stats.username,
        "wallet": stats.wallet,
        "stats": {
            "totalProfit": stats.total_profit,
            "predictions": stats.predictions,
            "biggestWin": stats.biggest_win,
            "positionsValue": stats.positions_value
        },
        "positions": [
            {
                "question": p.market_question,
                "outcome": p.outcome,
                "shares": p.shares,
                "avgPrice": p.avg_price,
                "currentPrice": p.current_price,
                "value": p.value,
                "pnl": p.pnl,
                "slug": p.slug
            }
            for p in positions
        ]
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = get_neobrother_data()
    print(json.dumps(data, indent=2))
