"""
Polymarket Trade Executor
Dry-run mode by default. Set --live flag and POLY_PRIVATE_KEY for real trades.
"""
import os
import logging
from dataclasses import dataclass
from typing import Optional, Literal

logger = logging.getLogger(__name__)

@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    filled_amount: float = 0.0
    avg_price: float = 0.0
    error: Optional[str] = None

class PolymarketExecutor:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.client = None
        
        if not dry_run:
            self._init_client()
    
    def _init_client(self):
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            from dotenv import load_dotenv
            from pathlib import Path
            
            # Load environment variables from .env (check both current and parent dir)
            env_path = Path(__file__).parent / ".env"
            if not env_path.exists():
                env_path = Path(__file__).parent.parent / ".env"
            load_dotenv(env_path)
            
            private_key = os.environ.get("POLY_PRIVATE_KEY")
            if not private_key:
                logger.warning("POLY_PRIVATE_KEY not found. Live trading will fail until provided.")
                return

            # Proxy wallet address (where funds are held on Polymarket)
            funder = os.environ.get("POLY_FUNDER_ADDRESS", "0xB90588CE64AD8792019cc494ea815E59b5071640")
            
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=137,
                signature_type=2,  # Browser wallet proxy (Phantom)
                funder=funder,
            )
            
            # Always derive fresh API credentials (stored creds go stale)
            self.client.set_api_creds(self.client.derive_api_key())
            logger.info("CLOB client initialized with derived API keys")
            
        except ImportError:
            raise ImportError("Run: pip install py-clob-client python-dotenv")
    
    def get_balance(self) -> float:
        """
        Check connection and return mock/real balance.
        Note: Real balance fetching via CLOB SDK requires specific parameters.
        Verified connection via get_ok().
        """
        if self.dry_run:
            return 1000.0
        try:
            # Verify connectivity
            if self.client.get_ok() == "OK":
                # For now, return a placeholder or try to implement real balance check
                # Real USDC balance check usually involves calling the ERC20 contract
                return 0.0 # Placeholder for now, connection is verified
            return 0.0
        except Exception as e:
            logger.error(f"Balance check/Connection error: {e}")
            return 0.0
    
    def place_order(self, token_id: str, side: Literal["BUY", "SELL"], 
                    size: float, price: float) -> OrderResult:
        if self.dry_run:
            logger.info(f"[DRY RUN] {side} {size:.2f} @ {price:.2f}")
            return OrderResult(True, "dry_run", size, price)
        
        # Check VPN/connectivity before attempting trade
        try:
            if not self.client:
                return OrderResult(False, error="CLOB client not initialized - check credentials")
            health_check = self.client.get_ok()
            if health_check != "OK":
                return OrderResult(False, error=f"Cannot reach Polymarket - check VPN (status: {health_check})")
        except Exception as e:
            return OrderResult(False, error=f"VPN/connectivity check failed: {str(e)}")
        
        try:
            from py_clob_client.clob_types import OrderArgs
            
            # CLOB API always uses BUY/SELL - we're always buying tokens (YES or NO tokens)
            # The token_id determines which outcome we're betting on
            clob_side = "BUY" if side in ["YES", "NO", "BUY"] else "SELL"
            
            order = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=clob_side,
            )
            signed = self.client.create_order(order)
            result = self.client.post_order(signed)
            
            return OrderResult(True, result.get("orderID"), size, price)
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return OrderResult(False, error=str(e))
    
    def buy(self, token_id: str, dollar_amount: float, max_price: float) -> OrderResult:
        shares = dollar_amount / max_price
        return self.place_order(token_id, "BUY", shares, max_price)

def execute_opportunity(executor, opp, position_size: float) -> OrderResult:
    """Execute a weather trading opportunity."""
    if opp.recommended_side == "YES":
        token_id = opp.clob_token_ids[0] if hasattr(opp, 'clob_token_ids') else getattr(opp, 'yes_token_id', None)
        price = opp.yes_price if hasattr(opp, 'yes_price') else opp.entry_price
    else:
        token_id = opp.clob_token_ids[1] if hasattr(opp, 'clob_token_ids') else getattr(opp, 'no_token_id', None)
        price = opp.no_price if hasattr(opp, 'no_price') else (1 - opp.entry_price)
    
    if not token_id:
        return OrderResult(False, error="Missing token ID")
    
    limit_price = min(price + 0.01, 0.99)
    return executor.buy(token_id, position_size, limit_price)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Executor Test (DRY RUN)")
    
    ex = PolymarketExecutor(dry_run=True)
    result = ex.buy("test_token", 50.0, 0.35)
    
    print(f"Success: {result.success}")
    print(f"Order ID: {result.order_id}")
    print(f"Balance: ${ex.get_balance():.2f}")

