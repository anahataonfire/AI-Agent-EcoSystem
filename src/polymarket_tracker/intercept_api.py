#!/usr/bin/env python3
"""
Intercept Polymarket API calls to get neobrother's positions.
"""
from playwright.sync_api import sync_playwright
import json
import re

WALLET = "0x6297b93ea37ff92a57fd636410f3b71ebf74517e"

def intercept_positions():
    """Intercept API calls to get positions data."""
    
    captured_data = {
        "user": None,
        "positions": [],
        "activity": []
    }
    
    def handle_response(response):
        url = response.url
        
        # Capture user/profile data
        if "profile" in url.lower() or WALLET.lower() in url.lower():
            try:
                data = response.json()
                if isinstance(data, dict):
                    captured_data["user"] = data
                    print(f"[CAPTURED] User data from: {url[:80]}")
            except:
                pass
        
        # Capture positions
        if "position" in url.lower():
            try:
                data = response.json()
                if isinstance(data, list):
                    captured_data["positions"].extend(data)
                elif isinstance(data, dict) and "positions" in data:
                    captured_data["positions"].extend(data["positions"])
                print(f"[CAPTURED] Positions from: {url[:80]}")
            except:
                pass
        
        # Capture activity/trades
        if "activity" in url.lower() or "order" in url.lower():
            try:
                data = response.json()
                if isinstance(data, list):
                    captured_data["activity"].extend(data)
                print(f"[CAPTURED] Activity from: {url[:80]}")
            except:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Listen to all responses
        page.on("response", handle_response)
        
        print(f"Navigating to @neobrother profile...")
        page.goto("https://polymarket.com/@neobrother", wait_until="networkidle", timeout=60000)
        
        # Click on Positions tab if available
        try:
            page.click('text="Positions"', timeout=5000)
            page.wait_for_timeout(3000)
        except:
            print("Could not find Positions tab")
        
        # Wait a bit more for data to load
        page.wait_for_timeout(5000)
        
        browser.close()
    
    return captured_data


if __name__ == "__main__":
    data = intercept_positions()
    
    print("\n" + "="*50)
    print("CAPTURED DATA SUMMARY")
    print("="*50)
    
    if data["user"]:
        print(f"\nUser: {json.dumps(data['user'], indent=2)[:500]}...")
    else:
        print("\nNo user data captured")
    
    print(f"\nPositions: {len(data['positions'])}")
    for p in data["positions"][:3]:
        print(f"  - {p}")
    
    print(f"\nActivity: {len(data['activity'])}")
    
    # Save to file
    with open("/tmp/neobrother_intercepted.json", "w") as f:
        json.dump(data, f, indent=2)
    print("\nSaved to /tmp/neobrother_intercepted.json")
