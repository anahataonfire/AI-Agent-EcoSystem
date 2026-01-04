"""
Content data models for the Smart Curator system.

Defines schemas for content entries, action items, and queue records.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import hashlib
import secrets


class ContentStatus(Enum):
    """Status of a content entry in the system."""
    PENDING = "pending"      # In queue, not yet processed
    UNREAD = "unread"        # Processed but not reviewed by user
    READ = "read"            # User has reviewed
    IMPLEMENTED = "implemented"  # Action items completed
    ARCHIVED = "archived"    # No longer active


class ActionType(Enum):
    """Type of action item identified from content."""
    ENHANCEMENT = "enhancement"  # Potential improvement to codebase
    CORRECTION = "correction"    # Bug fix or error correction
    RESEARCH = "research"        # Needs further investigation
    DOCUMENTATION = "documentation"  # Docs improvement
    IDEA = "idea"               # General idea for future


@dataclass
class ActionItem:
    """An action item extracted from content analysis."""
    action_type: ActionType
    description: str
    related_files: list[str] = field(default_factory=list)
    priority: int = 3  # 1=high, 5=low
    
    def to_dict(self) -> dict:
        return {
            "type": self.action_type.value,
            "description": self.description,
            "related_files": self.related_files,
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActionItem":
        return cls(
            action_type=ActionType(data["type"]),
            description=data["description"],
            related_files=data.get("related_files", []),
            priority=data.get("priority", 3),
        )


def generate_content_id() -> str:
    """Generate a unique content ID."""
    return f"CONTENT-{secrets.token_hex(4).upper()}"


@dataclass
class ContentEntry:
    """A processed content entry in the store."""
    id: str
    url: str
    title: str
    summary: str
    categories: list[str]
    relevance_score: float  # 0.0 to 1.0
    action_items: list[ActionItem]
    status: ContentStatus
    ingested_at: str
    source_hash: str
    raw_content: Optional[str] = None  # Full text, optional
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "categories": self.categories,
            "relevance_score": self.relevance_score,
            "action_items": [a.to_dict() for a in self.action_items],
            "status": self.status.value,
            "ingested_at": self.ingested_at,
            "source_hash": self.source_hash,
            "raw_content": self.raw_content,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContentEntry":
        return cls(
            id=data["id"],
            url=data["url"],
            title=data["title"],
            summary=data["summary"],
            categories=data["categories"],
            relevance_score=data["relevance_score"],
            action_items=[ActionItem.from_dict(a) for a in data.get("action_items", [])],
            status=ContentStatus(data["status"]),
            ingested_at=data["ingested_at"],
            source_hash=data["source_hash"],
            raw_content=data.get("raw_content"),
        )


@dataclass
class QueueRecord:
    """A record in the ingestion queue (from iOS/inbox file)."""
    url: str
    tags: list[str] = field(default_factory=list)
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed: bool = False
    
    @classmethod
    def parse_line(cls, line: str) -> Optional["QueueRecord"]:
        """Parse a queue line: 'url | tag1,tag2' or just 'url'."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        
        if "|" in line:
            url_part, tags_part = line.split("|", 1)
            url = url_part.strip()
            tags = [t.strip() for t in tags_part.split(",") if t.strip()]
        else:
            url = line
            tags = []
        
        if not url.startswith(("http://", "https://")):
            return None
            
        return cls(url=url, tags=tags)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
