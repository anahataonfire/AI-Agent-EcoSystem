#!/usr/bin/env python3
"""
Polymarket CLOB API Key Setup

Derives API credentials from your Polymarket wallet private key.
These credentials are required for live trading.

IMPORTANT: Never share your private key or API credentials!
"""

import os
import json
import sys
import time
import hmac
import hashlib
from urllib.request import urlopen, Request
from urllib.error import HTTPError

# Try to import eth_account for signing
try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    HAS_ETH_ACCOUNT = True
except ImportError:
    HAS_ETH_ACCOUNT = False


CLOB_BASE_URL = "https://clob.polymarket.com"


def derive_api_key(private_key: str) -> dict:
    """
    Derive API credentials from wallet private key.
    
    Returns:
        Dict with api_key, api_secret, api_passphrase
    """
    if not HAS_ETH_ACCOUNT:
        print("ERROR: eth_account not installed")
        print("Run: pip install eth-account")
        sys.exit(1)
    
    # Remove 0x prefix if present
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    
    # Get account from private key
    account = Account.from_key(private_key)
    address = account.address
    
    print(f"Wallet address: {address}")
    
    # Generate nonce (timestamp)
    nonce = int(time.time() * 1000)
    
    # Create message to sign
    message = f"I am signing this message to derive my API credentials for Polymarket CLOB\nnonce:{nonce}"
    
    # Sign the message
    message_hash = encode_defunct(text=message)
    signed = Account.sign_message(message_hash, private_key)
    signature = signed.signature.hex()
    
    print(f"Signed message with nonce: {nonce}")
    
    # Call derive-api-key endpoint
    url = f"{CLOB_BASE_URL}/auth/derive-api-key"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "WeatherTrader/1.0"
    }
    
    payload = json.dumps({
        "address": address,
        "nonce": nonce,
        "signature": signature
    }).encode()
    
    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return {
                "address": address,
                "api_key": data.get("apiKey"),
                "api_secret": data.get("secret"),
                "api_passphrase": data.get("passphrase"),
            }
    except HTTPError as e:
        print(f"API Error: {e.code} - {e.reason}")
        error_body = e.read().decode() if e.fp else ""
        print(f"Response: {error_body}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def update_env_file(credentials: dict, env_path: str = ".env"):
    """Add or update Polymarket credentials in .env file."""
    
    # Read existing .env
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_lines = f.readlines()
    
    # Remove existing POLYMARKET entries
    env_lines = [
        line for line in env_lines 
        if not line.strip().startswith("POLYMARKET_")
    ]
    
    # Add new entries
    env_lines.append("\n# Polymarket CLOB API Credentials\n")
    env_lines.append(f"POLYMARKET_ADDRESS={credentials['address']}\n")
    env_lines.append(f"POLYMARKET_API_KEY={credentials['api_key']}\n")
    env_lines.append(f"POLYMARKET_API_SECRET={credentials['api_secret']}\n")
    env_lines.append(f"POLYMARKET_API_PASSPHRASE={credentials['api_passphrase']}\n")
    env_lines.append("POLYMARKET_PAPER_MODE=false\n")
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(env_lines)
    
    print(f"\n✅ Credentials saved to {env_path}")


def main():
    print("\n" + "=" * 60)
    print("  POLYMARKET CLOB API KEY SETUP")
    print("=" * 60)
    
    if not HAS_ETH_ACCOUNT:
        print("\n❌ eth-account package not installed")
        print("   Run: pip install eth-account")
        sys.exit(1)
    
    print("""
To get your Polymarket wallet private key:
1. Go to polymarket.com
2. Click on your balance/wallet
3. Click the three dots (...)
4. Select "Export Private Key"
5. Copy the key (starts with 0x)

⚠️  NEVER share your private key with anyone!
""")
    
    # Get private key from user or environment
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    
    if not private_key:
        print("Enter your Polymarket private key (or set POLYMARKET_PRIVATE_KEY env var):")
        private_key = input("> ").strip()
    
    if not private_key:
        print("❌ No private key provided")
        sys.exit(1)
    
    print("\nDeriving API credentials...")
    credentials = derive_api_key(private_key)
    
    if not credentials:
        print("\n❌ Failed to derive API credentials")
        sys.exit(1)
    
    print("\n✅ API credentials derived successfully!")
    print(f"   Address: {credentials['address']}")
    print(f"   API Key: {credentials['api_key'][:20]}...")
    
    # Ask to save
    print("\nSave credentials to .env file? (y/n)")
    save = input("> ").strip().lower()
    
    if save == 'y':
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(project_root, ".env")
        update_env_file(credentials, env_path)
        
        print("\n🎉 Setup complete! You can now run live trading.")
        print("   Use: python -m src.weather_trading.trader")
    else:
        print("\nCredentials not saved. Add manually to .env:")
        print(f"   POLYMARKET_ADDRESS={credentials['address']}")
        print(f"   POLYMARKET_API_KEY={credentials['api_key']}")
        print(f"   POLYMARKET_API_SECRET={credentials['api_secret']}")
        print(f"   POLYMARKET_API_PASSPHRASE={credentials['api_passphrase']}")


if __name__ == "__main__":
    main()
