#!/usr/bin/env python3
"""
Informatica Documentation Scraper CLI

Usage:
    # Discover all available PDFs (dry run)
    python scripts/scrape_informatica.py --discover-only

    # Download all PDFs with auth
    python scripts/scrape_informatica.py --download-all

    # Check for updates only
    python scripts/scrape_informatica.py --check-updates

    # Test login
    python scripts/scrape_informatica.py --test-login
    
    # Test single download
    python scripts/scrape_informatica.py --test-single
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncio
from scrapers.informatica_scraper import main

if __name__ == "__main__":
    asyncio.run(main())
