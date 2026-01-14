"""
The Graph Client for Polymarket

Queries on-chain market data (prices, liquidity) via Polymarket's subgraph.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# Polymarket subgraph endpoints
SUBGRAPH_ENDPOINTS = {
    "matic": "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets",
    "goldsky": "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn",
}


@dataclass
class OnChainMarket:
    """Market data from The Graph."""
    condition_id: str
    question_id: str
    yes_price: float
    no_price: float
    liquidity: float
    volume: float
    trades_count: int
    last_updated: datetime


class GraphClient:
    """
    Client for querying Polymarket data via The Graph.
    """
    
    def __init__(self, endpoint: str = None, timeout: float = 15.0):
        self.endpoint = endpoint or SUBGRAPH_ENDPOINTS["matic"]
        self.timeout = timeout
    
    def _query(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """Execute a GraphQL query against the subgraph."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        try:
            req = Request(
                self.endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'WeatherTradingBot/1.0'
                }
            )
            
            with urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
                
                if "errors" in result:
                    logger.error(f"GraphQL errors: {result['errors']}")
                    return None
                
                return result.get("data")
                
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.error(f"Graph query failed: {e}")
            return None
    
    def get_market_by_condition(self, condition_id: str) -> Optional[OnChainMarket]:
        """
        Fetch market data by condition ID.
        
        Args:
            condition_id: The condition ID (hex string with 0x prefix)
            
        Returns:
            OnChainMarket with price/liquidity data
        """
        query = """
        query GetMarket($conditionId: String!) {
            fixedProductMarketMakers(where: { conditions_contains: [$conditionId] }, first: 1) {
                id
                conditions
                scaledCollateralVolume
                outcomeTokenPrices
                tradesQuantity
                outcomeTokenAmounts
            }
        }
        """
        
        data = self._query(query, {"conditionId": condition_id.lower()})
        if not data or not data.get("fixedProductMarketMakers"):
            logger.debug(f"No market found for condition: {condition_id}")
            return None
        
        market = data["fixedProductMarketMakers"][0]
        
        # Parse prices (array format: [yesPrice, noPrice])
        prices = market.get("outcomeTokenPrices", [0.5, 0.5])
        if isinstance(prices, list) and len(prices) >= 2:
            yes_price = float(prices[0])
            no_price = float(prices[1])
        else:
            yes_price, no_price = 0.5, 0.5
        
        # Parse liquidity from outcome token amounts
        amounts = market.get("outcomeTokenAmounts", [0, 0])
        liquidity = sum(float(a) for a in amounts) if amounts else 0
        
        return OnChainMarket(
            condition_id=condition_id,
            question_id=market.get("id", ""),
            yes_price=yes_price,
            no_price=no_price,
            liquidity=liquidity,
            volume=float(market.get("scaledCollateralVolume", 0)),
            trades_count=int(market.get("tradesQuantity", 0)),
            last_updated=datetime.now(timezone.utc),
        )
    
    def get_markets_by_conditions(
        self, 
        condition_ids: List[str]
    ) -> Dict[str, OnChainMarket]:
        """
        Fetch multiple markets by condition IDs.
        
        Args:
            condition_ids: List of condition IDs
            
        Returns:
            Dict mapping condition_id -> OnChainMarket
        """
        query = """
        query GetMarkets($conditionIds: [String!]!) {
            fixedProductMarketMakers(
                where: { conditions_contains: $conditionIds }
                first: 100
                orderBy: scaledCollateralVolume
                orderDirection: desc
            ) {
                id
                conditions
                scaledCollateralVolume
                outcomeTokenPrices
                tradesQuantity
                outcomeTokenAmounts
            }
        }
        """
        
        # Normalize condition IDs to lowercase
        normalized = [c.lower() for c in condition_ids]
        
        data = self._query(query, {"conditionIds": normalized})
        if not data:
            return {}
        
        results = {}
        for market in data.get("fixedProductMarketMakers", []):
            conditions = market.get("conditions", [])
            for cond in conditions:
                if cond.lower() in normalized:
                    prices = market.get("outcomeTokenPrices", [0.5, 0.5])
                    yes_price = float(prices[0]) if prices else 0.5
                    no_price = float(prices[1]) if len(prices) > 1 else 0.5
                    
                    amounts = market.get("outcomeTokenAmounts", [0, 0])
                    liquidity = sum(float(a) for a in amounts) if amounts else 0
                    
                    results[cond.lower()] = OnChainMarket(
                        condition_id=cond,
                        question_id=market.get("id", ""),
                        yes_price=yes_price,
                        no_price=no_price,
                        liquidity=liquidity,
                        volume=float(market.get("scaledCollateralVolume", 0)),
                        trades_count=int(market.get("tradesQuantity", 0)),
                        last_updated=datetime.now(timezone.utc),
                    )
        
        logger.info(f"Fetched {len(results)} markets from Graph")
        return results
    
    def get_recent_trades(
        self, 
        market_id: str, 
        limit: int = 20
    ) -> List[Dict]:
        """
        Get recent trades for a market.
        
        Args:
            market_id: The market maker ID
            limit: Number of trades to fetch
            
        Returns:
            List of trade dicts with price, amount, timestamp
        """
        query = """
        query GetTrades($marketId: String!, $limit: Int!) {
            fpmmTrades(
                where: { fpmm: $marketId }
                orderBy: timestamp
                orderDirection: desc
                first: $limit
            ) {
                id
                outcomeIndex
                collateralAmount
                timestamp
            }
        }
        """
        
        data = self._query(query, {"marketId": market_id, "limit": limit})
        if not data:
            return []
        
        return data.get("fpmmTrades", [])


# Module-level singleton
_client: Optional[GraphClient] = None

def get_graph_client() -> GraphClient:
    """Get or create the singleton Graph client."""
    global _client
    if _client is None:
        _client = GraphClient()
    return _client


def test_graph_connection() -> bool:
    """Test if The Graph endpoint is reachable."""
    client = get_graph_client()
    
    # Simple test query
    query = """
    query Test {
        fixedProductMarketMakers(first: 1) {
            id
        }
    }
    """
    
    result = client._query(query)
    if result:
        logger.info("Graph connection successful")
        return True
    else:
        logger.error("Graph connection failed")
        return False
