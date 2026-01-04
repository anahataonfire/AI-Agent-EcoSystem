
import feedparser
from urllib.parse import quote_plus
import sys

def debug_fetch(query):
    url_template = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    url = url_template.replace("{query}", quote_plus(query))
    print(f"Fetching: {url}")
    
    # Try default fetch first (no custom headers, just what feedparser does)
    try:
        feed = feedparser.parse(url)
        print(f"Status: {getattr(feed, 'status', 'Unknown')}")
        print(f"Entries: {len(feed.entries)}")
        
        if hasattr(feed, "bozo") and feed.bozo:
            print(f"Bozo Exception: {feed.bozo_exception}")

        if not feed.entries:
            print("No entries found!")
        else:
            print(f"First entry title: {feed.entries[0].title}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Apple"
    debug_fetch(query)
