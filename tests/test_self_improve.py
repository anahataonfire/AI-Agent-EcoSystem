"""
Self-Improvement Tests (DTL-SKILL-IMPROVE v1).
"""

import pytest


class TestPriorityAdjustments:
    """Tests for priority adjustment recommendations."""

    def test_deprioritize_low_success(self):
        """Low success rate should trigger deprioritization."""
        from src.core.self_improve import SelfImproveEngine
        from src.core.skill_scoring import SkillScore
        
        engine = SelfImproveEngine()
        
        scores = {
            "bad_skill": SkillScore(
                skill_name="bad_skill",
                total_runs=5,
                successful_runs=2,
                aborted_runs=3,
            )
        }
        
        recs = engine.analyze_skill_performance(scores)
        
        deprioritize = [r for r in recs if r.action == "deprioritize"]
        assert len(deprioritize) >= 1

    def test_promote_high_success(self):
        """High success rate should trigger promotion."""
        from src.core.self_improve import SelfImproveEngine
        from src.core.skill_scoring import SkillScore
        
        engine = SelfImproveEngine()
        
        scores = {
            "good_skill": SkillScore(
                skill_name="good_skill",
                total_runs=10,
                successful_runs=10,
                aborted_runs=0,
            )
        }
        
        recs = engine.analyze_skill_performance(scores)
        
        promote = [r for r in recs if r.action == "promote"]
        assert len(promote) >= 1


class TestRetryTuning:
    """Tests for retry tuning recommendations."""

    def test_increase_backoff_on_tool_failures(self):
        """Many tool failures should increase backoff."""
        from src.core.self_improve import SelfImproveEngine
        from src.core.failure_attribution import FailureAttribution
        
        engine = SelfImproveEngine()
        
        attributions = [
            FailureAttribution(
                failure_class="tool",
                originating_agent="executor",
                tool_name="DataFetchRSS",
                stage="execute",
                root_cause="tool",
                retryable=True,
                confidence=0.9
            )
            for _ in range(6)
        ]
        
        recs = engine.analyze_failures(attributions)
        
        retry_tuning = [r for r in recs if r.recommendation_type == "retry_tuning"]
        assert len(retry_tuning) >= 1


class TestDeterministicRecommendations:
    """Tests that recommendations are deterministic."""

    def test_same_input_same_output(self):
        """Same inputs should produce identical recommendations."""
        from src.core.self_improve import SelfImproveEngine
        from src.core.skill_scoring import SkillScore
        from src.core.failure_attribution import FailureAttribution
        from src.core.evals import EvalResult
        
        scores = {"skill_a": SkillScore(skill_name="skill_a", total_runs=5, successful_runs=3)}
        attributions = []
        evals = [EvalResult(passed=True, reasons=[], severity="info")]
        
        engine1 = SelfImproveEngine()
        recs1 = engine1.generate_recommendations(scores, attributions, evals)
        
        engine2 = SelfImproveEngine()
        recs2 = engine2.generate_recommendations(scores, attributions, evals)
        
        # Should produce identical recommendations
        assert len(recs1) == len(recs2)
        for r1, r2 in zip(recs1, recs2):
            assert r1.target == r2.target
            assert r1.action == r2.action
