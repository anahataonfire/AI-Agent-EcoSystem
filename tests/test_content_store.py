"""
Tests for the ContentStore SQLite backend.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from src.content.store import ContentStore
from src.content.schemas import (
    ContentEntry,
    ContentStatus,
    ActionItem,
    ActionType,
    generate_content_id,
)


@pytest.fixture
def temp_store():
    """Create a temporary content store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_content.db"
        store = ContentStore(db_path=db_path)
        yield store


@pytest.fixture
def sample_entry():
    """Create a sample content entry for testing."""
    return ContentEntry(
        id=generate_content_id(),
        url="https://example.com/test-article",
        title="Test Article About AI Agents",
        summary="This is a test article about AI agents and multi-agent systems.",
        categories=["agents", "llm", "python"],
        relevance_score=0.85,
        action_items=[
            ActionItem(
                action_type=ActionType.ENHANCEMENT,
                description="Consider adding agent coordination patterns",
                related_files=["src/agents/base.py"],
                priority=2,
            ),
            ActionItem(
                action_type=ActionType.RESEARCH,
                description="Explore LangGraph state management",
                related_files=[],
                priority=3,
            ),
        ],
        status=ContentStatus.UNREAD,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        source_hash="sha256:abc123def456",
        raw_content="Full article content here...",
    )


class TestContentStore:
    """Tests for ContentStore operations."""
    
    def test_write_and_read(self, temp_store, sample_entry):
        """Test basic write and read."""
        # Write
        success = temp_store.write(sample_entry)
        assert success is True
        
        # Read back
        retrieved = temp_store.read(sample_entry.id)
        assert retrieved is not None
        assert retrieved.id == sample_entry.id
        assert retrieved.url == sample_entry.url
        assert retrieved.title == sample_entry.title
        assert retrieved.summary == sample_entry.summary
        assert retrieved.categories == sample_entry.categories
        assert retrieved.relevance_score == sample_entry.relevance_score
        assert len(retrieved.action_items) == 2
        assert retrieved.status == ContentStatus.UNREAD
    
    def test_read_by_url(self, temp_store, sample_entry):
        """Test reading by URL."""
        temp_store.write(sample_entry)
        
        retrieved = temp_store.read_by_url("https://example.com/test-article")
        assert retrieved is not None
        assert retrieved.id == sample_entry.id
    
    def test_duplicate_url_rejected(self, temp_store, sample_entry):
        """Test that duplicate URLs are rejected."""
        success1 = temp_store.write(sample_entry)
        assert success1 is True
        
        # Try to write same URL with different ID
        duplicate = ContentEntry(
            id=generate_content_id(),
            url=sample_entry.url,  # Same URL
            title="Different Title",
            summary="Different summary",
            categories=["other"],
            relevance_score=0.5,
            action_items=[],
            status=ContentStatus.UNREAD,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            source_hash="sha256:different",
        )
        
        success2 = temp_store.write(duplicate)
        assert success2 is False
    
    def test_update_status(self, temp_store, sample_entry):
        """Test status update."""
        temp_store.write(sample_entry)
        
        # Update status
        updated = temp_store.update_status(sample_entry.id, ContentStatus.READ)
        assert updated is True
        
        # Verify
        retrieved = temp_store.read(sample_entry.id)
        assert retrieved.status == ContentStatus.READ
    
    def test_list_by_status(self, temp_store):
        """Test listing by status."""
        # Create entries with different statuses
        for i, status in enumerate([ContentStatus.UNREAD, ContentStatus.UNREAD, ContentStatus.READ]):
            entry = ContentEntry(
                id=generate_content_id(),
                url=f"https://example.com/article-{i}",
                title=f"Article {i}",
                summary=f"Summary {i}",
                categories=["test"],
                relevance_score=0.5,
                action_items=[],
                status=status,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                source_hash=f"sha256:{i}",
            )
            temp_store.write(entry)
        
        unread = temp_store.list_by_status(ContentStatus.UNREAD)
        assert len(unread) == 2
        
        read = temp_store.list_by_status(ContentStatus.READ)
        assert len(read) == 1
    
    def test_list_by_category(self, temp_store):
        """Test filtering by category."""
        # Create entries with different categories
        entries_data = [
            (["agents", "python"], "Article A"),
            (["llm", "python"], "Article B"),
            (["agents", "llm"], "Article C"),
        ]
        
        for i, (cats, title) in enumerate(entries_data):
            entry = ContentEntry(
                id=generate_content_id(),
                url=f"https://example.com/cat-{i}",
                title=title,
                summary=f"Summary {i}",
                categories=cats,
                relevance_score=0.5,
                action_items=[],
                status=ContentStatus.UNREAD,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                source_hash=f"sha256:cat{i}",
            )
            temp_store.write(entry)
        
        agents = temp_store.list_by_category("agents")
        assert len(agents) == 2
        
        python = temp_store.list_by_category("python")
        assert len(python) == 2
        
        llm = temp_store.list_by_category("llm")
        assert len(llm) == 2
    
    def test_search(self, temp_store):
        """Test full-text search."""
        entries_data = [
            ("LangGraph Workflow Tutorial", "Learn how to build workflows"),
            ("Python Async Programming", "Understanding async/await"),
            ("Multi-Agent Coordination", "Coordinating multiple AI agents"),
        ]
        
        for i, (title, summary) in enumerate(entries_data):
            entry = ContentEntry(
                id=generate_content_id(),
                url=f"https://example.com/search-{i}",
                title=title,
                summary=summary,
                categories=["test"],
                relevance_score=0.5,
                action_items=[],
                status=ContentStatus.UNREAD,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                source_hash=f"sha256:search{i}",
            )
            temp_store.write(entry)
        
        # Search for "workflow"
        results = temp_store.search("workflow")
        assert len(results) >= 1
        assert any("Workflow" in r.title for r in results)
        
        # Search for "agent"
        results = temp_store.search("agent")
        assert len(results) >= 1
    
    def test_get_action_items(self, temp_store, sample_entry):
        """Test retrieving action items."""
        temp_store.write(sample_entry)
        
        # Get all action items
        items = temp_store.get_action_items()
        assert len(items) == 2
        
        # Get by type
        enhancements = temp_store.get_action_items(action_type="enhancement")
        assert len(enhancements) == 1
        assert enhancements[0][1].action_type == ActionType.ENHANCEMENT
    
    def test_count_by_status(self, temp_store):
        """Test status count."""
        for i, status in enumerate([ContentStatus.UNREAD, ContentStatus.UNREAD, ContentStatus.READ, ContentStatus.ARCHIVED]):
            entry = ContentEntry(
                id=generate_content_id(),
                url=f"https://example.com/count-{i}",
                title=f"Article {i}",
                summary=f"Summary {i}",
                categories=["test"],
                relevance_score=0.5,
                action_items=[],
                status=status,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                source_hash=f"sha256:count{i}",
            )
            temp_store.write(entry)
        
        counts = temp_store.count_by_status()
        assert counts.get("unread", 0) == 2
        assert counts.get("read", 0) == 1
        assert counts.get("archived", 0) == 1


class TestActionItemSerialization:
    """Tests for ActionItem serialization."""
    
    def test_to_dict(self):
        """Test ActionItem to dict conversion."""
        action = ActionItem(
            action_type=ActionType.ENHANCEMENT,
            description="Test description",
            related_files=["file1.py", "file2.py"],
            priority=2,
        )
        
        d = action.to_dict()
        assert d["type"] == "enhancement"
        assert d["description"] == "Test description"
        assert d["related_files"] == ["file1.py", "file2.py"]
        assert d["priority"] == 2
    
    def test_from_dict(self):
        """Test ActionItem from dict conversion."""
        d = {
            "type": "correction",
            "description": "Fix bug",
            "related_files": ["buggy.py"],
            "priority": 1,
        }
        
        action = ActionItem.from_dict(d)
        assert action.action_type == ActionType.CORRECTION
        assert action.description == "Fix bug"
        assert action.related_files == ["buggy.py"]
        assert action.priority == 1
