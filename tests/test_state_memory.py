"""
State Memory Tests (DTL-SKILL-MEMORY v1).
"""

import pytest
import tempfile
import os


class TestMemoryDecay:
    """Tests for memory decay correctness."""

    def test_decay_removes_old_entries(self):
        """Old entries should be removed after decay."""
        from src.core.state_memory import StateMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path, decay_runs=3)
            
            memory.remember("hash1", "skill1", "success")
            
            # Decay 3 times
            for _ in range(3):
                memory.apply_decay()
            
            entries = memory.recall("hash1")
            assert len(entries) == 0

    def test_fresh_entries_persist(self):
        """Fresh entries should persist through partial decay."""
        from src.core.state_memory import StateMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path, decay_runs=5)
            
            memory.remember("hash1", "skill1", "success")
            
            # Decay only twice
            memory.apply_decay()
            memory.apply_decay()
            
            entries = memory.recall("hash1")
            assert len(entries) == 1


class TestRetryAvoidance:
    """Tests for retry avoidance."""

    def test_avoid_failed_skill(self):
        """Failed skills should be avoided."""
        from src.core.state_memory import StateMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path)
            
            memory.remember("hash1", "skill_a", "failure", failure_reason="timeout")
            
            should_avoid = memory.should_avoid_skill("hash1", "skill_a")
            assert should_avoid is True

    def test_allow_successful_skill(self):
        """Successful skills should not be avoided."""
        from src.core.state_memory import StateMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path)
            
            memory.remember("hash1", "skill_a", "success")
            
            should_avoid = memory.should_avoid_skill("hash1", "skill_a")
            assert should_avoid is False


class TestSkillRouting:
    """Tests for skill routing based on memory."""

    def test_preferred_skills_ordering(self):
        """Skills should be ordered by past performance."""
        from src.core.state_memory import StateMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path)
            
            memory.remember("hash1", "skill_a", "success")
            memory.remember("hash1", "skill_b", "failure")
            
            preferred = memory.get_preferred_skills(
                "hash1",
                available_skills=["skill_a", "skill_b", "skill_c"]
            )
            
            # skill_a succeeded, should be first
            # skill_c neutral, should be second
            # skill_b failed, should be last
            assert preferred[0] == "skill_a"
            assert preferred[-1] == "skill_b"
