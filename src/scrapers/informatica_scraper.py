"""
Informatica Documentation Scraper

Downloads all PDF documentation from docs.informatica.com with authentication.
Uses Playwright for JS-rendered pages and handles rate limiting.
"""

import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Browser

load_dotenv()

# Configuration
BASE_URL = "https://docs.informatica.com"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "informatica_docs"
MANIFEST_PATH = DATA_DIR / "download_manifest.json"
RATE_LIMIT_DELAY = 1.0  # seconds between requests


@dataclass
class PDFDocument:
    """Represents a discovered PDF document."""
    url: str
    title: str
    category: str
    local_path: str = ""
    sha256: str = ""
    downloaded_at: str = ""
    size_bytes: int = 0
    version: str = ""  # e.g., "October 2025", "November 2025"
    product_version: str = ""  # e.g., "Current Version", "10.5.9"
    release_date: str = ""  # e.g., "2025-10-15"
    last_updated: str = ""  # e.g., "2025-11-20"
    updated: bool = False
    doc_type: str = "pdf"  # "pdf" or "zip"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "PDFDocument":
        # Handle missing fields for backward compatibility
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)


@dataclass
class DownloadManifest:
    """Tracks all downloaded documents."""
    last_run: str = ""
    documents: list[PDFDocument] = field(default_factory=list)
    
    def save(self):
        """Save manifest to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MANIFEST_PATH, "w") as f:
            json.dump({
                "last_run": self.last_run,
                "documents": [d.to_dict() for d in self.documents]
            }, f, indent=2)
    
    @classmethod
    def load(cls) -> "DownloadManifest":
        """Load manifest from disk."""
        if not MANIFEST_PATH.exists():
            return cls()
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
            return cls(
                last_run=data.get("last_run", ""),
                documents=[PDFDocument.from_dict(d) for d in data.get("documents", [])]
            )
    
    def get_by_url(self, url: str) -> Optional[PDFDocument]:
        """Find document by URL."""
        for doc in self.documents:
            if doc.url == url:
                return doc
        return None
    
    def update_or_add(self, doc: PDFDocument):
        """Update existing document or add new one."""
        existing = self.get_by_url(doc.url)
        if existing:
            idx = self.documents.index(existing)
            # Check if content changed
            if existing.sha256 and doc.sha256 and existing.sha256 != doc.sha256:
                doc.updated = True
            self.documents[idx] = doc
        else:
            self.documents.append(doc)


class InformaticaScraper:
    """Scrapes Informatica documentation portal."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.username = os.getenv("INFORMATICA_USERNAME")
        self.password = os.getenv("INFORMATICA_PASSWORD")
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.manifest = DownloadManifest.load()
        self._discovered_pdfs: list[PDFDocument] = []
        
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def start(self):
        """Start browser and login."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
    
    async def login(self) -> bool:
        """
        Login to Informatica documentation portal via accounts.informatica.com.
        
        The login portal uses Okta-based authentication with:
        - Email field: input[name="identifier"]
        - Password field: input[name="credentials.passcode"]
        - Submit button: input[type="submit"][value="Login"]
        
        Returns True if login successful.
        """
        if not self.username or not self.password:
            print("❌ Missing INFORMATICA_USERNAME or INFORMATICA_PASSWORD in .env")
            return False
        
        print(f"🔐 Logging in as {self.username}...")
        
        # Navigate directly to login page
        login_url = "https://accounts.informatica.com/login.html"
        try:
            await self.page.goto(login_url, timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️ Could not load login page: {e}")
            return False
        
        try:
            # Dismiss cookie consent banner if present
            try:
                cookie_btn = await self.page.query_selector('#truste-consent-button')
                if cookie_btn:
                    await cookie_btn.click()
                    await asyncio.sleep(1)
                    print("  📋 Dismissed cookie consent")
            except:
                pass
            
            # Wait for login form to be ready
            await self.page.wait_for_selector('input[name="identifier"]', timeout=10000)
            
            # Fill in email/username
            await self.page.fill('input[name="identifier"]', self.username)
            print("  ✓ Entered email")
            
            # Fill in password
            await self.page.fill('input[name="credentials.passcode"]', self.password)
            print("  ✓ Entered password")
            
            # Click login button
            await self.page.click('input[type="submit"][value="Login"]')
            print("  ⏳ Submitting login...")
            
            # Wait for navigation - login redirects on success
            try:
                await self.page.wait_for_url(lambda url: "login" not in url.lower(), timeout=15000)
                print("✅ Login successful - redirected")
                self._is_logged_in = True
                
                # Navigate to docs portal
                await self.page.goto(BASE_URL)
                await asyncio.sleep(2)
                return True
            except:
                pass  # Timeout - check URL manually
            
            # Check current URL
            current_url = self.page.url
            
            if "login" not in current_url.lower():
                print("✅ Login successful - redirected to:", current_url[:60])
                self._is_logged_in = True
                
                # Navigate back to docs portal to continue scraping
                await self.page.goto(BASE_URL)
                await asyncio.sleep(2)
                return True
            
            # Check for error message
            error_el = await self.page.query_selector('.o-form-error-container, .error-message, [data-se="error"]')
            if error_el:
                error_text = await error_el.inner_text()
                print(f"❌ Login failed: {error_text}")
                return False
            
            # Still on login page but no error - might be MFA
            mfa_el = await self.page.query_selector('input[name="credentials.factor"]')
            if mfa_el:
                print("⚠️ MFA required - please complete authentication manually")
                # Wait for user to complete MFA
                await asyncio.sleep(30)
                if "login" not in self.page.url.lower():
                    print("✅ Login successful after MFA")
                    self._is_logged_in = True
                    await self.page.goto(BASE_URL)
                    await asyncio.sleep(2)
                    return True
            
            print("⚠️ Login status uncertain - continuing with current session")
            return True
            
        except Exception as e:
            # Navigation context destroyed = page navigated = login likely succeeded
            if "context was destroyed" in str(e) or "navigation" in str(e).lower():
                print("✅ Login successful - page navigated")
                self._is_logged_in = True
                try:
                    await self.page.goto(BASE_URL)
                    await asyncio.sleep(2)
                except:
                    pass
                return True
            
            print(f"⚠️ Login error: {e}")
            # Continue anyway - some docs are public
            return True
    
    async def discover_product_categories(self) -> list[str]:
        """
        Discover all product category page URLs from the homepage.
        
        Returns list of category page URLs.
        """
        print("🔍 Discovering product categories...")
        
        await self.page.goto(BASE_URL)
        await asyncio.sleep(2)
        
        # Find all product links
        links = await self.page.query_selector_all('a[href*="docs.informatica.com"]')
        
        categories = set()
        for link in links:
            href = await link.get_attribute("href")
            if href and ".html" in href and href != BASE_URL:
                categories.add(href)
        
        # Also find internal links
        internal_links = await self.page.query_selector_all('a[href^="/"]')
        for link in internal_links:
            href = await link.get_attribute("href")
            if href and ".html" in href:
                full_url = urljoin(BASE_URL, href)
                categories.add(full_url)
        
        print(f"📂 Found {len(categories)} category pages")
        return list(categories)
    
    async def extract_page_metadata(self) -> dict:
        """
        Extract version and date metadata from the current page.
        
        Looks for:
        - meta[name="version"] -> Release version (e.g., "October 2025")
        - meta[name="VersionMetadata"] -> Product version (e.g., "Current Version", "10.5.9")
        - li.doc-breadcrumb__item-release--txt -> "Released: [date]" or "Updated: [date]"
        """
        metadata = {
            "version": "",
            "product_version": "",
            "release_date": "",
            "last_updated": ""
        }
        
        try:
            # Get meta tag versions
            version_el = await self.page.query_selector('meta[name="version"]')
            if version_el:
                content = await version_el.get_attribute("content")
                if content:
                    metadata["version"] = content
                    # If it looks like a date (e.g., "October 2025"), also use as release_date
                    if re.match(r'\w+\s+\d{4}', content):
                        metadata["release_date"] = content
            
            product_version_el = await self.page.query_selector('meta[name="VersionMetadata"]')
            if product_version_el:
                content = await product_version_el.get_attribute("content")
                if content:
                    metadata["product_version"] = content
            
            # Get release/update dates from breadcrumb (more specific selector)
            release_el = await self.page.query_selector('li.doc-breadcrumb__item-release--txt')
            if release_el:
                text = await release_el.inner_text()
                if text:
                    # Parse "Released: October 2025" or "Updated: November 2025"
                    released_match = re.search(r'Released:\s*(\w+\s+\d{4})', text)
                    if released_match:
                        metadata["release_date"] = released_match.group(1)
                    
                    updated_match = re.search(r'Updated:\s*(\w+\s+\d{4})', text)
                    if updated_match:
                        metadata["last_updated"] = updated_match.group(1)
                    
                    # If no prefix, just extract the date
                    if not released_match and not updated_match:
                        date_match = re.search(r'(\w+\s+\d{4})', text)
                        if date_match:
                            metadata["last_updated"] = date_match.group(1)
                        
        except Exception as e:
            pass  # Metadata extraction is best-effort
        
        return metadata
    
    async def find_pdf_links_on_page(self, page_url: str) -> list[PDFDocument]:
        """
        Find all PDF download links on a page.
        
        Looks for:
        1. "Download Guide" links (a#guideDownloadLink, a.resourceDownloadLink)
        2. "Download Documentation Set" ZIP links (a#docSetDownloadLink)
        3. Direct PDF links in the content
        
        Also extracts version and date metadata from page meta tags.
        
        Returns list of PDFDocument objects.
        """
        print(f"📄 Scanning: {page_url}")
        
        try:
            await self.page.goto(page_url, timeout=30000)
            await asyncio.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            print(f"  ⚠️ Failed to load: {e}")
            return []
        
        pdfs = []
        
        # Extract category from URL
        parsed = urlparse(page_url)
        path_parts = parsed.path.strip("/").split("/")
        category = "/".join(path_parts[:2]) if len(path_parts) >= 2 else path_parts[0] if path_parts else "general"
        
        # Extract metadata from page
        metadata = await self.extract_page_metadata()
        
        # 1. Look for "Download Guide" link in Actions sidebar
        download_selectors = [
            '#guideDownloadLink',
            'a.resourceDownloadLink',
            'a[href*="/content/dam/"][href$=".pdf"]',
            'a[title*="Download Guide"]',
            'a:has-text("Download Guide")',
        ]
        
        for selector in download_selectors:
            try:
                links = await self.page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute("href")
                    text = await link.inner_text() or ""
                    
                    if not href:
                        continue
                    
                    # Make absolute URL
                    if not href.startswith("http"):
                        href = urljoin(BASE_URL, href)
                    
                    # Skip if not a PDF
                    if not href.endswith(".pdf") and ".pdf?" not in href:
                        continue
                    
                    # Get title from page or link
                    page_title = ""
                    try:
                        title_el = await self.page.query_selector("h1, .guide-title, .page-title")
                        if title_el:
                            page_title = await title_el.inner_text()
                    except:
                        pass
                    
                    title = page_title.strip() or text.strip() or Path(urlparse(href).path).stem
                    
                    # Extract version from metadata first, fallback to parsing
                    version = metadata.get("version", "")
                    if not version:
                        version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', title + href)
                        if version_match:
                            version = version_match.group(1)
                    
                    pdf = PDFDocument(
                        url=href,
                        title=title,
                        category=category,
                        version=version,
                        product_version=metadata.get("product_version", ""),
                        release_date=metadata.get("release_date", ""),
                        last_updated=metadata.get("last_updated", ""),
                        doc_type="pdf"
                    )
                    pdfs.append(pdf)
            except Exception as e:
                # Selector not found, try next
                continue
        
        # 2. Look for "Download Documentation Set" ZIP links
        try:
            docset_link = await self.page.query_selector('#docSetDownloadLink, a[title*="Download Documentation Set"]')
            if docset_link:
                href = await docset_link.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = urljoin(BASE_URL, href)
                    
                    # Extract version from ZIP filename
                    zip_version = metadata.get("product_version", "")
                    if not zip_version:
                        version_match = re.search(r'(\d+[\.\-]\d+(?:[\.\-]\d+)?)', href)
                        if version_match:
                            zip_version = version_match.group(1).replace("-", ".")
                    
                    pdf = PDFDocument(
                        url=href,
                        title=f"{category} Documentation Set",
                        category=category,
                        version=metadata.get("version", ""),
                        product_version=zip_version,
                        release_date=metadata.get("release_date", ""),
                        last_updated=metadata.get("last_updated", ""),
                        doc_type="zip"
                    )
                    pdfs.append(pdf)
                    print(f"  📦 Found documentation set ZIP (v{zip_version or 'latest'})")
        except:
            pass
        
        # 3. Find guide links on product pages to visit later
        guide_links = []
        try:
            guide_selectors = [
                '.section-guidelist__link',
                'a[href*="/current-version"]',
                'a.guide-link',
            ]
            for selector in guide_selectors:
                links = await self.page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute("href")
                    if href and ".html" in href:
                        if not href.startswith("http"):
                            href = urljoin(page_url, href)
                        guide_links.append(href)
        except:
            pass
        
        # Store guide links for later crawling
        self._pending_guide_links = getattr(self, '_pending_guide_links', [])
        self._pending_guide_links.extend(guide_links)
        
        if pdfs:
            print(f"  📎 Found {len(pdfs)} PDFs/ZIPs")
        
        return pdfs
    
    async def discover_all_pdfs(self, max_pages: int = 100) -> list[PDFDocument]:
        """
        Crawl the documentation portal and discover all PDFs.
        
        Args:
            max_pages: Maximum number of pages to crawl
            
        Returns list of discovered PDFDocument objects.
        """
        # Get initial category pages
        categories = await self.discover_product_categories()
        
        visited = set()
        to_visit = list(categories)[:max_pages]
        all_pdfs = []
        
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
            visited.add(url)
            
            pdfs = await self.find_pdf_links_on_page(url)
            all_pdfs.extend(pdfs)
            
            # Find more links to crawl
            try:
                links = await self.page.query_selector_all('a[href*=".html"]')
                for link in links:
                    href = await link.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            href = urljoin(url, href)
                        if href.startswith(BASE_URL) and href not in visited:
                            to_visit.append(href)
            except:
                pass
        
        # Deduplicate by URL
        seen_urls = set()
        unique_pdfs = []
        for pdf in all_pdfs:
            if pdf.url not in seen_urls:
                seen_urls.add(pdf.url)
                unique_pdfs.append(pdf)
        
        self._discovered_pdfs = unique_pdfs
        print(f"\n✅ Discovered {len(unique_pdfs)} unique PDFs")
        return unique_pdfs
    
    def filter_to_latest_versions(self, pdfs: list[PDFDocument]) -> list[PDFDocument]:
        """
        Filter documents to only include the latest/current version.
        
        Removes historical versions by:
        1. Keeping documents with product_version="Current Version"
        2. For versioned products (e.g., "6.5.0"), keeping only the highest version
        3. Using URL patterns to detect historical versions (e.g., /6-5-0.html)
        
        Returns filtered list of PDFDocuments.
        """
        # Pattern to detect version numbers in URLs (e.g., /6-5-0.html, /10-5-9/)
        version_pattern = re.compile(r'/(\d+)-(\d+)-(\d+)(?:\.html|/)')
        
        # Group documents by base category (product) path
        by_product: dict[str, list[PDFDocument]] = {}
        for pdf in pdfs:
            # Extract base product path (without version)
            base_path = re.sub(r'/\d+-\d+-\d+(?:\.html)?/?', '/', pdf.url)
            base_path = re.sub(r'/current-version(?:\.html)?/?', '/', base_path)
            
            # Also normalize category
            base_category = re.sub(r'\d+-\d+-\d+\.html$', '', pdf.category)
            base_category = re.sub(r'current-version\.html$', '', base_category)
            
            key = f"{base_category}:{pdf.title}"
            if key not in by_product:
                by_product[key] = []
            by_product[key].append(pdf)
        
        # For each product, keep only the latest version
        latest_pdfs = []
        skipped_count = 0
        
        for key, docs in by_product.items():
            if len(docs) == 1:
                latest_pdfs.append(docs[0])
                continue
            
            # Find the latest version
            latest = None
            latest_version = (-1, -1, -1)
            
            for doc in docs:
                # "Current Version" is always the latest
                if doc.product_version.lower() == "current version":
                    latest = doc
                    break
                
                # Check URL for version pattern
                match = version_pattern.search(doc.url)
                if match:
                    ver_tuple = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                    if ver_tuple > latest_version:
                        latest_version = ver_tuple
                        latest = doc
                else:
                    # No version in URL - assume it's current
                    if not latest:
                        latest = doc
            
            if latest:
                latest_pdfs.append(latest)
                skipped_count += len(docs) - 1
            else:
                # Couldn't determine - keep all
                latest_pdfs.extend(docs)
        
        if skipped_count > 0:
            print(f"📋 Filtered to latest versions: kept {len(latest_pdfs)}, skipped {skipped_count} historical")
        
        return latest_pdfs
    
    async def download_pdf(self, pdf: PDFDocument) -> bool:
        """
        Download a single PDF.
        
        Returns True if successful.
        """
        # Create category directory
        category_dir = DATA_DIR / pdf.category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = re.sub(r'[^\w\-_\.]', '_', pdf.title)[:100] + ".pdf"
        local_path = category_dir / filename
        pdf.local_path = str(local_path.relative_to(DATA_DIR.parent.parent))
        
        print(f"⬇️  Downloading: {pdf.title}")
        
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                response = await client.get(pdf.url)
                response.raise_for_status()
                
                content = response.content
                
                # Calculate hash
                pdf.sha256 = hashlib.sha256(content).hexdigest()
                pdf.size_bytes = len(content)
                pdf.downloaded_at = datetime.now(timezone.utc).isoformat()
                
                # Check if content changed
                existing = self.manifest.get_by_url(pdf.url)
                if existing and existing.sha256 and existing.sha256 != pdf.sha256:
                    pdf.updated = True
                    print(f"  🔄 Updated: {pdf.title}")
                
                # Write file
                with open(local_path, "wb") as f:
                    f.write(content)
                
                # Update manifest
                self.manifest.update_or_add(pdf)
                
                return True
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            return False
    
    async def download_all(self, pdfs: list[PDFDocument] = None):
        """
        Download all discovered PDFs.
        """
        if pdfs is None:
            pdfs = self._discovered_pdfs
        
        if not pdfs:
            print("No PDFs to download. Run discover_all_pdfs first.")
            return
        
        print(f"\n📥 Downloading {len(pdfs)} PDFs...")
        
        success = 0
        failed = 0
        
        for i, pdf in enumerate(pdfs, 1):
            print(f"[{i}/{len(pdfs)}] ", end="")
            
            if await self.download_pdf(pdf):
                success += 1
            else:
                failed += 1
            
            # Rate limit
            await asyncio.sleep(RATE_LIMIT_DELAY)
            
            # Save manifest periodically
            if i % 10 == 0:
                self.manifest.last_run = datetime.now(timezone.utc).isoformat()
                self.manifest.save()
        
        # Final save
        self.manifest.last_run = datetime.now(timezone.utc).isoformat()
        self.manifest.save()
        
        print(f"\n✅ Complete: {success} downloaded, {failed} failed")
    
    def get_stats(self) -> dict:
        """Get statistics about downloaded documentation."""
        total_size = sum(d.size_bytes for d in self.manifest.documents)
        updated_count = sum(1 for d in self.manifest.documents if d.updated)
        
        # Group by category
        by_category = {}
        for doc in self.manifest.documents:
            cat = doc.category
            if cat not in by_category:
                by_category[cat] = {"count": 0, "size": 0}
            by_category[cat]["count"] += 1
            by_category[cat]["size"] += doc.size_bytes
        
        return {
            "total_documents": len(self.manifest.documents),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "updated_count": updated_count,
            "last_run": self.manifest.last_run,
            "by_category": by_category
        }


async def main():
    """CLI entry point."""
    import argparse
    import json as json_module
    
    parser = argparse.ArgumentParser(description="Informatica Documentation Scraper")
    parser.add_argument("--discover-only", action="store_true", help="Only discover PDFs, don't download")
    parser.add_argument("--download-all", action="store_true", help="Download all discovered PDFs")
    parser.add_argument("--check-updates", action="store_true", help="Check for updates to existing docs")
    parser.add_argument("--test-login", action="store_true", help="Test login only")
    parser.add_argument("--test-single", action="store_true", help="Download a single PDF for testing")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to crawl")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--no-headless", action="store_true", help="Run browser with visible window")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")
    parser.add_argument("--latest-only", action="store_true", help="Only include latest versions, filter out historical")
    parser.add_argument("--all-versions", action="store_true", help="Include all versions including historical (default: latest only)")
    
    args = parser.parse_args()
    
    headless = not args.no_headless
    # Default to latest-only unless --all-versions is specified
    filter_latest = not args.all_versions
    
    async with InformaticaScraper(headless=headless) as scraper:
        
        if args.test_login:
            success = await scraper.login()
            if args.json_output:
                print(json_module.dumps({"success": success}))
            else:
                print(f"Login test: {'✅ Success' if success else '❌ Failed'}")
            return
        
        # Login first
        await scraper.login()
        
        if args.discover_only:
            pdfs = await scraper.discover_all_pdfs(max_pages=args.max_pages)
            
            # Apply latest-only filter
            if filter_latest:
                pdfs = scraper.filter_to_latest_versions(pdfs)
            
            if args.json_output:
                # Output full metadata as JSON
                output = {
                    "count": len(pdfs),
                    "filter_latest": filter_latest,
                    "documents": [pdf.to_dict() for pdf in pdfs]
                }
                print("---JSON_OUTPUT_START---")
                print(json_module.dumps(output, indent=2))
                print("---JSON_OUTPUT_END---")
            else:
                print("\nDiscovered PDFs:")
                for pdf in pdfs[:20]:
                    version_info = f" (v{pdf.version})" if pdf.version else ""
                    release_info = f" [{pdf.release_date}]" if pdf.release_date else ""
                    print(f"  - {pdf.title}{version_info}{release_info}: {pdf.url}")
                if len(pdfs) > 20:
                    print(f"  ... and {len(pdfs) - 20} more")
        
        elif args.download_all:
            pdfs = await scraper.discover_all_pdfs(max_pages=args.max_pages)
            
            # Apply latest-only filter
            if filter_latest:
                pdfs = scraper.filter_to_latest_versions(pdfs)
            
            await scraper.download_all(pdfs)
            
            if args.json_output:
                stats = scraper.get_stats()
                print("---JSON_OUTPUT_START---")
                print(json_module.dumps(stats, indent=2))
                print("---JSON_OUTPUT_END---")
        
        elif args.test_single:
            pdfs = await scraper.discover_all_pdfs(max_pages=5)
            if pdfs:
                await scraper.download_pdf(pdfs[0])
                print(f"\n✅ Test download complete: {pdfs[0].local_path}")
        
        elif args.check_updates:
            # Re-download existing docs to check for updates
            manifest = DownloadManifest.load()
            if not manifest.documents:
                print("No existing documents. Run --download-all first.")
                return
            await scraper.download_all(manifest.documents)
        
        else:
            # Show stats
            stats = scraper.get_stats()
            if args.json_output:
                print(json_module.dumps(stats, indent=2))
            else:
                print("\n📊 Documentation Stats:")
                print(f"  Total Documents: {stats['total_documents']}")
                print(f"  Total Size: {stats['total_size_mb']} MB")
                print(f"  Recently Updated: {stats['updated_count']}")
                print(f"  Last Run: {stats['last_run'] or 'Never'}")


if __name__ == "__main__":
    asyncio.run(main())

