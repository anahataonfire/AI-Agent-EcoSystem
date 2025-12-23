"""
Tests for the Deterministic Identity Layer (DTL).

These tests verify the key invariants:
1. Write barrier rejects non-allowed source types
2. Snapshot-first invariant (no fact without snapshot hash for snapshot type)
3. Identity context size limit
4. Identity continuity across runs
"""

import pytest
import tempfile
from pathlib import Path

from src.core.identity_manager import IdentityManager, ALLOWED_SOURCE_TYPES


class TestWriteBarrier:
    """Test that the write barrier rejects illegal writes."""
    
    def setup_method(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_identity.db"
        self.manager = IdentityManager(db_path=self.db_path)
    
    def test_reject_llm_write(self):
        """LLM outputs must NEVER be persisted as facts."""
        with pytest.raises(ValueError) as exc_info:
            self.manager.update_identity(
                fact_key="llm_thought",
                fact_value="The user seems interested in AI news",
                source_type="llm_output"  # ILLEGAL
            )
        
        assert "Illegal source_type" in str(exc_info.value)
        assert "llm_output" in str(exc_info.value)
    
    def test_reject_inferred_write(self):
        """Inferred facts must not be persisted."""
        with pytest.raises(ValueError):
            self.manager.update_identity(
                fact_key="user_preference",
                fact_value="tech news",
                source_type="inferred"  # ILLEGAL
            )
    
    def test_accept_explicit_user_write(self):
        """Explicit user facts are allowed."""
        # Should not raise
        self.manager.update_identity(
            fact_key="user_name",
            fact_value="Adam",
            source_type="explicit_user"
        )
        
        facts = self.manager.load_identity()
        assert facts.get("user_name") == "Adam"
    
    def test_accept_admin_write(self):
        """Admin facts are allowed."""
        self.manager.update_identity(
            fact_key="system_version",
            fact_value="2.0.0",
            source_type="admin"
        )
        
        facts = self.manager.load_identity()
        assert facts.get("system_version") == "2.0.0"


class TestSnapshotFirstInvariant:
    """Test that snapshot-type facts require a valid snapshot hash."""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_identity.db"
        self.manager = IdentityManager(db_path=self.db_path)
    
    def test_snapshot_fact_without_hash_fails(self):
        """Snapshot facts without hash must fail."""
        with pytest.raises(ValueError) as exc_info:
            self.manager.update_identity(
                fact_key="last_run",
                fact_value={"query": "test"},
                source_type="snapshot",
                snapshot_hash=None  # Missing!
            )
        
        assert "require snapshot_hash" in str(exc_info.value)
    
    def test_snapshot_fact_with_nonexistent_hash_fails(self):
        """Snapshot facts referencing non-existent hash must fail."""
        with pytest.raises(ValueError) as exc_info:
            self.manager.update_identity(
                fact_key="last_run",
                fact_value={"query": "test"},
                source_type="snapshot",
                snapshot_hash="nonexistent_hash"
            )
        
        assert "not found" in str(exc_info.value)
    
    def test_snapshot_first_then_fact_succeeds(self):
        """Correct order: create snapshot, then reference it."""
        # Step 1: Create snapshot
        snapshot_data = {"query": "test", "result": "success"}
        snapshot_hash = self.manager.create_snapshot(snapshot_data)
        
        # Step 2: Create fact referencing snapshot
        self.manager.update_identity(
            fact_key="last_run",
            fact_value=snapshot_data,
            source_type="snapshot",
            snapshot_hash=snapshot_hash
        )
        
        facts = self.manager.load_identity()
        assert facts.get("last_run") == snapshot_data


class TestContextSizeLimit:
    """Test that identity context respects size limits."""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_identity.db"
        self.manager = IdentityManager(db_path=self.db_path)
    
    def test_serialization_limit_enforced(self):
        """Serialized context must not exceed 500 chars."""
        large_facts = {f"key_{i}": f"value_{i}" * 20 for i in range(50)}
        
        serialized = self.manager.serialize_for_prompt(large_facts)
        
        assert len(serialized) <= 500
        assert "truncated" in serialized


class TestIdentityContinuity:
    """Test that identity persists across manager instances."""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_identity.db"
    
    def test_load_empty_no_crash(self):
        """Loading from empty DB should not crash."""
        manager = IdentityManager(db_path=self.db_path)
        facts = manager.load_identity()
        
        assert facts == {}
    
    def test_identity_persists_across_instances(self):
        """Facts persist across manager instances (simulating runs)."""
        # Run 1: Create fact
        manager1 = IdentityManager(db_path=self.db_path)
        manager1.update_identity(
            fact_key="run_count",
            fact_value=1,
            source_type="admin"
        )
        
        # Run 2: Load fact
        manager2 = IdentityManager(db_path=self.db_path)
        facts = manager2.load_identity()
        
        assert facts.get("run_count") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
