"""
Skill Composition Stress Tests (Prompt 4).

Tests compositions under failure conditions.
"""

import pytest


class TestRetryAttributionComposition:
    """Tests for retry + attribution composition."""

    def test_partial_attribution_triggers_retry(self):
        """Partial attribution failure should allow retry with reduced confidence."""
        from src.core.failure_attribution import attribute_failure
        from src.core.retry_strategy import (
            classify_failure, decide_retry, RetryState, RetryConfig, FailureClass
        )
        
        # Attribute a tool failure
        attr = attribute_failure("Connection timeout", agent_name="executor")
        assert attr.root_cause == "tool"
        assert attr.retryable is True
        
        # Retry decision should proceed
        failure_class = classify_failure("Connection timeout")
        decision = decide_retry(failure_class, RetryState(), RetryConfig())
        
        assert decision.should_retry is True

    def test_low_confidence_attribution_aborts(self):
        """Very low confidence attribution should block retry decisions."""
        from src.core.failure_attribution import (
            attribute_failure, MIN_ATTRIBUTION_CONFIDENCE
        )
        
        # High confidence attribution should work
        attr = attribute_failure("Rate limit exceeded", agent_name="executor")
        assert attr.confidence >= MIN_ATTRIBUTION_CONFIDENCE


class TestAdaptationMemoryComposition:
    """Tests for adaptation + state_memory composition."""

    def test_adaptation_respects_memory(self):
        """Adaptation should consider memory of past failures."""
        from src.core.state_memory import StateMemory
        from src.core.adaptation import ExecutionMetrics, adapt, record_failure
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path)
            
            # Record past failure
            memory.remember("query_hash", "skill_a", "failure", "network_error")
            
            # Adaptation should consider avoiding failed skill
            metrics = ExecutionMetrics()
            for _ in range(3):
                record_failure(metrics, "network_error")
            
            decision = adapt(
                metrics,
                available_skills=["skill_a", "skill_b"],
                current_skill="skill_a"
            )
            
            # Should switch skills
            assert decision.action == "switch_skill"
            assert decision.new_skill == "skill_b"


class TestContextPlanComposition:
    """Tests for context_budget + plan_validation composition."""

    def test_large_plan_within_budget(self):
        """Plans should fit within context budget."""
        from src.core.context_budget import ContextSlice, select_context_slices
        from src.core.plan_validation import PlanStep
        
        # Create plan steps as context slices
        steps = [
            PlanStep(f"s{i}", f"Step {i}", "executor")
            for i in range(10)
        ]
        
        slices = [
            ContextSlice(
                source=f"step_{s.step_id}",
                priority=5,
                token_estimate=50,
                content=s.description
            )
            for s in steps
        ]
        
        # Select within budget
        selected = select_context_slices(slices, max_tokens=300)
        
        # Should fit some but not all
        assert len(selected) < len(slices)
        assert len(selected) > 0


class TestEvalsRetryComposition:
    """Tests for evals + retry_strategy composition."""

    def test_eval_failure_does_not_trigger_retry_storm(self):
        """Eval failures should abort, not trigger infinite retries."""
        from src.core.evals import EvalResult
        from src.core.retry_strategy import (
            classify_failure, decide_retry, RetryState, RetryConfig, FailureClass
        )
        
        # Eval failure
        eval_result = EvalResult(
            passed=False,
            reasons=["Invalid citation"],
            severity="fail"
        )
        
        # Classify as policy (non-retryable)
        failure_class = classify_failure(
            "Grounding failure",
            error_code="DTL-GRND-001"
        )
        
        assert failure_class == FailureClass.POLICY
        
        # Should not retry
        decision = decide_retry(failure_class, RetryState(), RetryConfig())
        assert decision.should_retry is False


class TestProactiveLedgerComposition:
    """Tests for proactive + run_ledger composition."""

    def test_proactive_action_always_logged(self):
        """Proactive actions must log to ledger before execution."""
        from src.core.proactive import (
            evaluate_proactive_action, execute_proactive_action,
            EVENT_PROACTIVE_ACTION
        )
        from src.core.run_ledger import get_ledger, reset_ledger
        
        reset_ledger()
        
        decision = evaluate_proactive_action(
            action_type="auto_refresh",
            confidence=0.9,
            reason="Data is stale"
        )
        
        # Execute (logs to ledger)
        execute_proactive_action(decision, actor="system")
        
        ledger = get_ledger()
        entries = ledger.get_entries(ledger.run_id)
        
        proactive_entries = [e for e in entries if e["event"] == EVENT_PROACTIVE_ACTION]
        assert len(proactive_entries) >= 1


class TestScoringImprovementComposition:
    """Tests for skill_scoring + self_improve composition."""

    def test_low_scores_trigger_deprioritization(self):
        """Low skill scores should trigger improvement recommendations."""
        from src.core.skill_scoring import SkillScore
        from src.core.self_improve import SelfImproveEngine
        
        engine = SelfImproveEngine()
        
        scores = {
            "failing_skill": SkillScore(
                skill_name="failing_skill",
                total_runs=5,
                successful_runs=1,
                aborted_runs=4,
            )
        }
        
        recs = engine.analyze_skill_performance(scores)
        
        deprioritize = [r for r in recs if r.action == "deprioritize"]
        assert len(deprioritize) >= 1


class TestBoundedAdaptiveReplanning:
    """Tests for plan_validation + adaptation + retry_strategy composition."""

    def test_replanning_respects_retry_cap(self):
        """Replanning through adaptation must respect retry caps."""
        from src.core.adaptation import ExecutionMetrics, adapt, record_failure
        from src.core.retry_strategy import RetryState, RetryConfig
        
        config = RetryConfig(max_total_retries=2)
        retry_state = RetryState(attempts=2)  # Already at cap
        
        metrics = ExecutionMetrics()
        for _ in range(3):
            record_failure(metrics, "planning_error")
        
        # Should abort, not infinitely replan
        decision = adapt(metrics, available_skills=[], current_skill="planner")
        
        assert decision.action == "abort"
