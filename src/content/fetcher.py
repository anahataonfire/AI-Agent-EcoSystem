"""
Content fetcher for extracting text from URLs.

Handles:
- HTML pages (with article extraction)
- Plain text
- PDF (basic extraction)
- JavaScript-heavy sites (X/Twitter, etc.) via Playwright
"""

import re
import hashlib
from typing import Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class FetchResult:
    """Result of fetching content from a URL."""
    url: str
    title: str
    content: str
    content_hash: str
    success: bool
    error: Optional[str] = None


# Sites that require JavaScript rendering
JS_REQUIRED_DOMAINS = [
    "x.com",
    "twitter.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
]


class ContentFetcher:
    """Fetches and extracts text content from URLs."""
    
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    TIMEOUT = 30
    MAX_CONTENT_LENGTH = 500_000  # 500KB text limit
    
    def __init__(self, use_browser: bool = True):
        """
        Initialize fetcher.
        
        Args:
            use_browser: Whether to use Playwright for JS sites (default True)
        """
        self.use_browser = use_browser
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain,application/json",
        })
    
    def _is_twitter_url(self, url: str) -> bool:
        """Check if URL is X/Twitter."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return "x.com" in domain or "twitter.com" in domain
    
    def _is_reddit_url(self, url: str) -> bool:
        """Check if URL is Reddit."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return "reddit.com" in domain or "redd.it" in domain
    
    def _needs_browser(self, url: str) -> bool:
        """Check if URL requires browser-based fetching."""
        # Twitter/X and Reddit are handled specially via API
        if self._is_twitter_url(url) or self._is_reddit_url(url):
            return False
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return any(js_domain in domain for js_domain in JS_REQUIRED_DOMAINS)
    
    def fetch(self, url: str) -> FetchResult:
        """
        Fetch content from a URL.
        
        Returns:
            FetchResult with extracted title and content
        """
        # X/Twitter gets special handling via API
        if self._is_twitter_url(url):
            return self._fetch_twitter_via_api(url)
        
        # Reddit gets special handling via JSON API
        if self._is_reddit_url(url):
            return self._fetch_reddit_via_json(url)
        
        # Check if this URL needs browser-based fetching
        if self.use_browser and self._needs_browser(url):
            return self._fetch_with_browser(url)
        
        return self._fetch_simple(url)
    
    def _fetch_reddit_via_json(self, url: str) -> FetchResult:
        """Fetch Reddit content via public JSON API (no auth needed)."""
        try:
            # Clean URL and add .json
            parsed = urlparse(url)
            path = parsed.path.rstrip("/")
            
            # Handle different Reddit URL formats
            # Remove query params, add .json
            json_url = f"https://www.reddit.com{path}.json"
            
            headers = {
                "User-Agent": "DTL-ContentCurator/1.0 (AI Research Assistant)",
            }
            
            response = requests.get(json_url, headers=headers, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error=f"Reddit API error: {response.status_code}"
                )
            
            data = response.json()
            
            # Reddit returns a list: [post_data, comments_data]
            if not isinstance(data, list) or len(data) < 1:
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error="Invalid Reddit response format"
                )
            
            # Extract post data
            post_listing = data[0].get("data", {}).get("children", [])
            if not post_listing:
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error="No post found"
                )
            
            post = post_listing[0].get("data", {})
            
            title = post.get("title", "Reddit Post")
            author = post.get("author", "unknown")
            subreddit = post.get("subreddit", "")
            selftext = post.get("selftext", "")
            score = post.get("score", 0)
            
            # Build content
            content_parts = [
                f"**r/{subreddit}** • Posted by u/{author} • {score} upvotes",
                "",
                f"# {title}",
                "",
            ]
            
            if selftext:
                content_parts.append(selftext)
                content_parts.append("")
            
            # Get top comments if available
            if len(data) > 1:
                comments_listing = data[1].get("data", {}).get("children", [])
                top_comments = []
                
                for i, comment in enumerate(comments_listing[:5]):  # Top 5 comments
                    if comment.get("kind") != "t1":
                        continue
                    comment_data = comment.get("data", {})
                    comment_author = comment_data.get("author", "unknown")
                    comment_body = comment_data.get("body", "")
                    comment_score = comment_data.get("score", 0)
                    
                    if comment_body:
                        top_comments.append(f"**u/{comment_author}** ({comment_score} pts):\n{comment_body}")
                
                if top_comments:
                    content_parts.append("---")
                    content_parts.append("## Top Comments")
                    content_parts.append("")
                    content_parts.extend(top_comments)
            
            content = "\n".join(content_parts)
            
            # Truncate if too long
            if len(content) > self.MAX_CONTENT_LENGTH:
                content = content[:self.MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
            
            content_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
            
            full_title = f"[r/{subreddit}] {title}"
            
            return FetchResult(
                url=url,
                title=full_title,
                content=content,
                content_hash=content_hash,
                success=True,
            )
            
        except Exception as e:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error=f"Reddit error: {e}"
            )

    
    def _fetch_twitter_via_api(self, url: str) -> FetchResult:
        """Fetch X/Twitter content via official X API v2."""
        import os
        import re
        
        bearer_token = os.environ.get("X_BEARER_TOKEN")
        if not bearer_token:
            # Try to load from dotenv
            try:
                from dotenv import load_dotenv
                load_dotenv()
                bearer_token = os.environ.get("X_BEARER_TOKEN")
            except ImportError:
                pass
        
        if not bearer_token:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error="X_BEARER_TOKEN not set. Add to .env file."
            )
        
        try:
            # Extract tweet ID from URL
            # URLs like: https://x.com/username/status/1234567890
            match = re.search(r'/status/(\d+)', url)
            if not match:
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error="Could not extract tweet ID from URL"
                )
            
            tweet_id = match.group(1)
            
            # Call Twitter API v2
            api_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
            params = {
                "tweet.fields": "author_id,created_at,text,referenced_tweets,conversation_id",
                "expansions": "author_id,referenced_tweets.id",
                "user.fields": "name,username"
            }
            
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "User-Agent": self.USER_AGENT,
            }
            
            response = requests.get(api_url, params=params, headers=headers, timeout=self.TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                tweet_data = data.get("data", {})
                includes = data.get("includes", {})
                
                # Get tweet text
                text = tweet_data.get("text", "")
                
                # Get author info from includes
                author_name = "Unknown"
                author_handle = ""
                users = includes.get("users", [])
                author_id = tweet_data.get("author_id")
                for user in users:
                    if user.get("id") == author_id:
                        author_name = user.get("name", "Unknown")
                        author_handle = user.get("username", "")
                        break
                
                # Check for quoted/replied tweets
                referenced = tweet_data.get("referenced_tweets", [])
                ref_tweets = includes.get("tweets", [])
                for ref in referenced:
                    ref_id = ref.get("id")
                    ref_type = ref.get("type")  # "quoted", "replied_to", "retweeted"
                    for rt in ref_tweets:
                        if rt.get("id") == ref_id:
                            ref_text = rt.get("text", "")
                            if ref_text:
                                text += f"\n\n[{ref_type.replace('_', ' ').title()}]: {ref_text}"
                            break
                
                if not text:
                    return FetchResult(
                        url=url, title="", content="", content_hash="",
                        success=False, error="Tweet has no text content"
                    )
                
                title = f"Tweet by {author_name} (@{author_handle})"
                content_hash = f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"
                
                return FetchResult(
                    url=url,
                    title=title,
                    content=text,
                    content_hash=content_hash,
                    success=True,
                )
            
            elif response.status_code == 401:
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error="X API authentication failed. Check X_BEARER_TOKEN."
                )
            elif response.status_code == 404:
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error="Tweet not found (may be deleted or private)"
                )
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("detail", f"API error {response.status_code}")
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error=f"X API error: {error_msg}"
                )
                
        except Exception as e:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error=f"X API error: {e}"
            )
    
    def _fetch_simple(self, url: str) -> FetchResult:
        """Simple HTTP-based fetch using requests."""
        try:
            # Validate URL
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return FetchResult(
                    url=url, title="", content="", content_hash="",
                    success=False, error=f"Invalid scheme: {parsed.scheme}"
                )
            
            # Fetch
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            
            # Route by content type
            if "text/html" in content_type:
                title, content = self._extract_html(response.text, url)
            elif "text/plain" in content_type:
                title, content = self._extract_text(response.text, url)
            elif "application/pdf" in content_type:
                title, content = self._extract_pdf(response.content, url)
            else:
                # Try HTML extraction as fallback
                title, content = self._extract_html(response.text, url)
            
            # Check for JS-required indicators
            if self._content_indicates_js_required(content):
                if self.use_browser:
                    return self._fetch_with_browser(url)
                else:
                    return FetchResult(
                        url=url, title=title, content="JavaScript is not available.",
                        content_hash="", success=False, error="Site requires JavaScript"
                    )
            
            # Truncate if too long
            if len(content) > self.MAX_CONTENT_LENGTH:
                content = content[:self.MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
            
            content_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
            
            return FetchResult(
                url=url,
                title=title,
                content=content,
                content_hash=content_hash,
                success=True,
            )
            
        except requests.RequestException as e:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error=str(e),
            )
        except Exception as e:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error=f"Extraction error: {e}",
            )
    
    def _content_indicates_js_required(self, content: str) -> bool:
        """Check if content indicates JavaScript is required."""
        js_indicators = [
            "JavaScript is not available",
            "Please enable JavaScript",
            "You need to enable JavaScript",
            "This page requires JavaScript",
            "noscript",
        ]
        content_lower = content.lower()
        return any(ind.lower() in content_lower for ind in js_indicators) and len(content) < 1000
    
    def _fetch_with_browser(self, url: str) -> FetchResult:
        """Fetch using Playwright headless browser."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error="Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.USER_AGENT,
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                
                # Navigate with timeout - use domcontentloaded (not networkidle, which times out on X)
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # For X/Twitter, wait for tweet content to load
                if "x.com" in url or "twitter.com" in url:
                    try:
                        # Wait for tweet text to appear
                        page.wait_for_selector('[data-testid="tweetText"]', timeout=15000)
                    except Exception:
                        # If selector not found, wait a bit longer for any content
                        page.wait_for_timeout(5000)
                    title, content = self._extract_twitter_content(page, url)
                else:
                    # Wait a bit for dynamic content
                    page.wait_for_timeout(3000)
                    # Generic extraction
                    html = page.content()
                    title, content = self._extract_html(html, url)
                
                browser.close()
                
                if not content or len(content.strip()) < 50:
                    return FetchResult(
                        url=url, title=title or urlparse(url).netloc, 
                        content="Content could not be extracted from this page.",
                        content_hash="", success=False, error="Minimal content extracted"
                    )
                
                # Truncate if too long
                if len(content) > self.MAX_CONTENT_LENGTH:
                    content = content[:self.MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
                
                content_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
                
                return FetchResult(
                    url=url,
                    title=title,
                    content=content,
                    content_hash=content_hash,
                    success=True,
                )
                
        except Exception as e:
            return FetchResult(
                url=url, title="", content="", content_hash="",
                success=False, error=f"Browser fetch error: {e}",
            )
    
    def _extract_twitter_content(self, page, url: str) -> Tuple[str, str]:
        """Extract content from X/Twitter page."""
        try:
            # Try to get tweet text
            tweet_selectors = [
                '[data-testid="tweetText"]',
                'article [lang]',
                'article div[dir="auto"]',
            ]
            
            tweet_texts = []
            for selector in tweet_selectors:
                elements = page.query_selector_all(selector)
                for el in elements:
                    text = el.inner_text()
                    if text and len(text) > 10:
                        tweet_texts.append(text)
                if tweet_texts:
                    break
            
            # Get author name
            author = ""
            author_el = page.query_selector('[data-testid="User-Name"]')
            if author_el:
                author = author_el.inner_text().split('\n')[0]
            
            # Build content
            if tweet_texts:
                content = "\n\n".join(tweet_texts)
                title = f"Tweet by {author}" if author else "Tweet"
            else:
                # Fallback: get all visible text
                html = page.content()
                title, content = self._extract_html(html, url)
            
            return title, content
            
        except Exception:
            html = page.content()
            return self._extract_html(html, url)
    
    def _extract_html(self, html: str, url: str) -> Tuple[str, str]:
        """Extract title and main content from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Get title
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        if not title:
            title = urlparse(url).netloc
        
        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Try to find main content
        main_content = None
        for selector in ["article", "main", '[role="main"]', ".post-content", ".article-body"]:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            # Fall back to body
            body = soup.find("body")
            if body:
                text = body.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)
        
        # Clean up whitespace
        text = self._clean_text(text)
        
        return title, text
    
    def _extract_text(self, text: str, url: str) -> Tuple[str, str]:
        """Extract from plain text."""
        title = urlparse(url).path.split("/")[-1] or urlparse(url).netloc
        return title, self._clean_text(text)
    
    def _extract_pdf(self, content: bytes, url: str) -> Tuple[str, str]:
        """Basic PDF text extraction (requires pymupdf)."""
        try:
            import fitz  # pymupdf
            
            doc = fitz.open(stream=content, filetype="pdf")
            title = doc.metadata.get("title", "") or urlparse(url).path.split("/")[-1]
            
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            
            return title, self._clean_text("\n".join(text_parts))
            
        except ImportError:
            return urlparse(url).path.split("/")[-1], "[PDF extraction requires pymupdf]"
    
    def _clean_text(self, text: str) -> str:
        """Clean up extracted text."""
        # Collapse multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text)
        # Strip lines
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

