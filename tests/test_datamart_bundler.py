"""
Unit tests for DatamartBundler module.

Tests bundle creation, source management, fingerprinting,
topic evolution, and sync operations.
"""

import pytest
import json
import tempfile
from pathlib import Path

from src.content.datamart_bundler import (
    DatamartBundler,
    DatamartManifest,
    DatamartSource,
    compute_bundle_fingerprint,
)


@pytest.fixture
def temp_bundler():
    """Create a bundler with temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundler = DatamartBundler(base_path=Path(tmpdir))
        yield bundler


class TestFingerprintDeterminism:
    """Tests for deterministic fingerprint calculation."""
    
    def test_fingerprint_same_sources_same_result(self):
        """Same sources produce same fingerprint."""
        fp1 = compute_bundle_fingerprint("test", 1, ["a", "b", "c"])
        fp2 = compute_bundle_fingerprint("test", 1, ["a", "b", "c"])
        assert fp1 == fp2
    
    def test_fingerprint_order_independent(self):
        """Source order doesn't affect fingerprint."""
        fp1 = compute_bundle_fingerprint("test", 1, ["a", "b", "c"])
        fp2 = compute_bundle_fingerprint("test", 1, ["c", "a", "b"])
        assert fp1 == fp2
    
    def test_fingerprint_version_matters(self):
        """Different version produces different fingerprint."""
        fp1 = compute_bundle_fingerprint("test", 1, ["a", "b"])
        fp2 = compute_bundle_fingerprint("test", 2, ["a", "b"])
        assert fp1 != fp2
    
    def test_fingerprint_topic_matters(self):
        """Different topic produces different fingerprint."""
        fp1 = compute_bundle_fingerprint("topic1", 1, ["a", "b"])
        fp2 = compute_bundle_fingerprint("topic2", 1, ["a", "b"])
        assert fp1 != fp2


class TestBundleCreation:
    """Tests for bundle creation."""
    
    def test_create_empty_bundle(self, temp_bundler):
        """Create an empty bundle."""
        manifest = temp_bundler.create_bundle(
            topic_id="test-topic",
            topic_name="Test Topic",
            tags=["test"],
        )
        
        assert manifest.topic_id == "test-topic"
        assert manifest.topic_name == "Test Topic"
        assert manifest.version == 1
        assert manifest.source_count == 0
        assert manifest.status == "active"
    
    def test_bundle_exists_check(self, temp_bundler):
        """bundle_exists returns correct status."""
        assert not temp_bundler.bundle_exists("nonexistent")
        
        temp_bundler.create_bundle("test-topic", "Test")
        assert temp_bundler.bundle_exists("test-topic")
    
    def test_read_manifest(self, temp_bundler):
        """Read manifest from disk."""
        temp_bundler.create_bundle("test-topic", "Test Topic", tags=["a", "b"])
        
        manifest = temp_bundler.read_manifest("test-topic")
        assert manifest is not None
        assert manifest.topic_name == "Test Topic"
        assert manifest.tags == ["a", "b"]


class TestSourceManagement:
    """Tests for adding/removing sources."""
    
    def test_add_source(self, temp_bundler):
        """Add a source to a bundle."""
        temp_bundler.create_bundle("test-topic", "Test")
        
        manifest = temp_bundler.add_source(
            topic_id="test-topic",
            content_id="CONTENT-001",
            url="https://example.com/article",
            title="Test Article",
            relevance_score=0.85,
            summary="Test summary",
            categories=["agents"],
        )
        
        assert manifest.version == 2  # Incremented
        assert manifest.source_count == 1
        assert manifest.sources[0].content_id == "CONTENT-001"
    
    def test_add_source_creates_file(self, temp_bundler):
        """Adding source creates markdown file."""
        temp_bundler.create_bundle("test-topic", "Test")
        temp_bundler.add_source(
            topic_id="test-topic",
            content_id="CONTENT-001",
            url="https://example.com",
            title="Test",
            relevance_score=0.8,
            raw_content="Full article content here.",
        )
        
        source_file = temp_bundler.get_bundle_path("test-topic") / "sources" / "CONTENT-001.md"
        assert source_file.exists()
        content = source_file.read_text()
        assert "Full article content here" in content
    
    def test_add_duplicate_source_noop(self, temp_bundler):
        """Adding duplicate source is a no-op."""
        temp_bundler.create_bundle("test-topic", "Test")
        
        m1 = temp_bundler.add_source(
            topic_id="test-topic",
            content_id="CONTENT-001",
            url="https://example.com",
            title="Test",
            relevance_score=0.8,
        )
        
        m2 = temp_bundler.add_source(
            topic_id="test-topic",
            content_id="CONTENT-001",  # Same ID
            url="https://example.com",
            title="Test",
            relevance_score=0.8,
        )
        
        assert m1.fingerprint == m2.fingerprint
        assert m1.version == m2.version
    
    def test_remove_source(self, temp_bundler):
        """Remove a source from a bundle."""
        temp_bundler.create_bundle("test-topic", "Test")
        temp_bundler.add_source(
            topic_id="test-topic",
            content_id="CONTENT-001",
            url="https://example.com",
            title="Test",
            relevance_score=0.8,
        )
        
        manifest = temp_bundler.remove_source("test-topic", "CONTENT-001")
        
        assert manifest.source_count == 0
        assert manifest.version == 3  # Create + add + remove


class TestTopicEvolution:
    """Tests for topic forking and archiving."""
    
    def test_archive_bundle(self, temp_bundler):
        """Archive a bundle."""
        temp_bundler.create_bundle("test-topic", "Test")
        
        manifest = temp_bundler.archive_bundle("test-topic")
        
        assert manifest.status == "archived"
    
    def test_cannot_add_to_archived(self, temp_bundler):
        """Cannot add sources to archived bundle."""
        temp_bundler.create_bundle("test-topic", "Test")
        temp_bundler.archive_bundle("test-topic")
        
        with pytest.raises(ValueError, match="archived"):
            temp_bundler.add_source(
                topic_id="test-topic",
                content_id="CONTENT-001",
                url="https://example.com",
                title="Test",
                relevance_score=0.8,
            )
    
    def test_fork_bundle(self, temp_bundler):
        """Fork a bundle into new topic."""
        temp_bundler.create_bundle("parent-topic", "Parent", tags=["tag1"])
        temp_bundler.add_source(
            topic_id="parent-topic",
            content_id="CONTENT-001",
            url="https://example.com/1",
            title="Article 1",
            relevance_score=0.8,
        )
        temp_bundler.add_source(
            topic_id="parent-topic",
            content_id="CONTENT-002",
            url="https://example.com/2",
            title="Article 2",
            relevance_score=0.7,
        )
        
        new_manifest = temp_bundler.fork_bundle(
            parent_topic_id="parent-topic",
            new_topic_id="child-topic",
            new_topic_name="Child Topic",
        )
        
        assert new_manifest.parent_topic_id == "parent-topic"
        assert new_manifest.source_count == 2
        assert new_manifest.tags == ["tag1"]
    
    def test_fork_with_filter(self, temp_bundler):
        """Fork bundle with filtered sources."""
        temp_bundler.create_bundle("parent-topic", "Parent")
        temp_bundler.add_source("parent-topic", "CONTENT-001", "url1", "A", 0.8)
        temp_bundler.add_source("parent-topic", "CONTENT-002", "url2", "B", 0.7)
        
        new_manifest = temp_bundler.fork_bundle(
            parent_topic_id="parent-topic",
            new_topic_id="filtered-topic",
            new_topic_name="Filtered",
            filter_content_ids=["CONTENT-001"],  # Only include first
        )
        
        assert new_manifest.source_count == 1
        assert new_manifest.sources[0].content_id == "CONTENT-001"


class TestSyncSummary:
    """Tests for sync summary generation."""
    
    def test_sync_summary_includes_all_files(self, temp_bundler):
        """Sync summary includes all bundle files."""
        temp_bundler.create_bundle("test-topic", "Test")
        temp_bundler.add_source(
            topic_id="test-topic",
            content_id="CONTENT-001",
            url="https://example.com",
            title="Test",
            relevance_score=0.8,
        )
        
        summary = temp_bundler.get_sync_summary("test-topic")
        
        assert "manifest.json" in summary["files"]
        assert "sources/CONTENT-001.md" in summary["files"]
        assert summary["source_count"] == 1
    
    def test_sync_summary_error_for_missing(self, temp_bundler):
        """Sync summary returns error for missing bundle."""
        summary = temp_bundler.get_sync_summary("nonexistent")
        assert "error" in summary


class TestListBundles:
    """Tests for listing bundles."""
    
    def test_list_active_bundles(self, temp_bundler):
        """List only active bundles by default."""
        temp_bundler.create_bundle("active-1", "Active 1")
        temp_bundler.create_bundle("active-2", "Active 2")
        temp_bundler.create_bundle("archived-1", "Archived 1")
        temp_bundler.archive_bundle("archived-1")
        
        bundles = temp_bundler.list_bundles(include_archived=False)
        topic_ids = [b.topic_id for b in bundles]
        
        assert "active-1" in topic_ids
        assert "active-2" in topic_ids
        assert "archived-1" not in topic_ids
    
    def test_list_all_bundles(self, temp_bundler):
        """List all bundles including archived."""
        temp_bundler.create_bundle("active-1", "Active 1")
        temp_bundler.create_bundle("archived-1", "Archived 1")
        temp_bundler.archive_bundle("archived-1")
        
        bundles = temp_bundler.list_bundles(include_archived=True)
        topic_ids = [b.topic_id for b in bundles]
        
        assert "active-1" in topic_ids
        assert "archived-1" in topic_ids

def test_rebuild_equivalence(temp_bundler):
    """Verify that rebuilding a bundle yields the exact same fingerprint."""
    # 1. Create initial bundle
    topic_id = "rebuild-test"
    temp_bundler.create_bundle(topic_id, "Rebuild Test")
    
    cid = "test-content-1"
    raw_content = "# Test Content"
    
    temp_bundler.add_source(
        topic_id=topic_id,
        content_id=cid,
        url="http://example.com",
        title="Test Doc",
        relevance_score=0.9,
        summary="Summary",
        categories=["test"],
        raw_content=raw_content
    )
    
    manifest1 = temp_bundler.read_manifest(topic_id)
    fp1 = manifest1.fingerprint
    
    # 2. Rebuild (simulate by re-adding exact same content)
    # In a real rebuild cli, we fetch from store. Here we just re-call add_source.
    # We must assume add_source is idempotent or handles updates correctly.
    # Ideally, we should wipe the source file first to prove recreation works.
    
    source_path = temp_bundler.datamart_root / topic_id / "sources" / f"{cid}.md"
    assert source_path.exists()
    source_path.unlink() # Delete source file
    assert not source_path.exists()
    
    # Re-add
    temp_bundler.add_source(
        topic_id=topic_id,
        content_id=cid,
        url="http://example.com",
        title="Test Doc",
        relevance_score=0.9,
        summary="Summary",
        categories=["test"],
        raw_content=raw_content
    )
    
    manifest2 = temp_bundler.read_manifest(topic_id)
    fp2 = manifest2.fingerprint
    
    assert fp1 == fp2
    assert source_path.exists()
