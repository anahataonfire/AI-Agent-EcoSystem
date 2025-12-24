"""
Skill Scoring Tests (DTL-SKILL-SCORE v1).
"""

import pytest
import tempfile
import os


class TestScoreTracking:
    """Tests for score tracking."""

    def test_success_rate_calculation(self):
        """Success rate should be calculated correctly."""
        from src.core.skill_scoring import SkillScoreStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "scores.json")
            store = SkillScoreStore(storage_path=path)
            
            # Record 3 successes and 1 abort
            store.record_success("test_skill", steps=5, cost_units=10)
            store.record_success("test_skill", steps=3, cost_units=8)
            store.record_success("test_skill", steps=4, cost_units=12)
            store.record_abort("test_skill")
            
            score = store.get_score("test_skill")
            assert score.success_rate == 0.75  # 3/4
            assert score.abort_rate == 0.25   # 1/4


class TestScoreConvergence:
    """Tests for score convergence."""

    def test_avg_steps_convergence(self):
        """Average steps should converge with more runs."""
        from src.core.skill_scoring import SkillScoreStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "scores.json")
            store = SkillScoreStore(storage_path=path)
            
            steps_list = [5, 5, 5, 5, 5]  # Consistent steps
            for s in steps_list:
                store.record_success("test_skill", steps=s, cost_units=10)
            
            score = store.get_score("test_skill")
            assert score.avg_steps == 5.0  # Should converge to 5


class TestScoreDecay:
    """Tests for score decay."""

    def test_decay_reduces_counts(self):
        """Decay should reduce counts over time."""
        from src.core.skill_scoring import SkillScoreStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "scores.json")
            store = SkillScoreStore(storage_path=path)
            
            # Record runs
            for _ in range(10):
                store.record_success("test_skill", steps=5, cost_units=10)
            
            original_successful = store.get_score("test_skill").successful_runs
            
            # Apply decay
            store.apply_decay()
            
            new_successful = store.get_score("test_skill").successful_runs
            assert new_successful < original_successful


class TestPriorityOrdering:
    """Tests for priority ordering."""

    def test_priority_order_by_success(self):
        """Skills should be ordered by success rate."""
        from src.core.skill_scoring import SkillScoreStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "scores.json")
            store = SkillScoreStore(storage_path=path)
            
            # Skill A: 100% success
            store.record_success("skill_a", steps=5, cost_units=10)
            store.record_success("skill_a", steps=5, cost_units=10)
            
            # Skill B: 50% success
            store.record_success("skill_b", steps=5, cost_units=10)
            store.record_abort("skill_b")
            
            order = store.get_priority_order()
            assert order[0] == "skill_a"  # Higher success rate first
