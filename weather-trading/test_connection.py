"""
Test connection to Polymarket CLOB.
"""
import logging
from executor import PolymarketExecutor

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Polymarket Connection...")
    
    # Initialize in LIVE mode (not dry_run)
    try:
        ex = PolymarketExecutor(dry_run=False)
        balance = ex.get_balance()
        print(f"✅ Connection Successful!")
        print(f"💰 Account Balance: ${balance:.2f}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
