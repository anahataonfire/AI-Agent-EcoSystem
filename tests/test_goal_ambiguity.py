"""
Adversarial Goal Ambiguity Tests (Prompt 8).

Tests autonomy when goals are underspecified or conflicting.
"""

import pytest


class TestAmbiguousSuccessCriteria:
    """Tests for behavior when success is ambiguous."""

    def test_plan_requires_explicit_steps(self):
        """Plans must have explicit steps, not vague goals."""
        from src.core.plan_validation import validate_plan, InvalidPlanError
        
        # Empty plan should fail
        with pytest.raises(InvalidPlanError):
            validate_plan("Do something vague", [])

    def test_plan_rejects_undefined_owners(self):
        """Plans must have valid owners for each step."""
        from src.core.plan_validation import validate_plan, PlanStep, InvalidPlanError
        
        steps = [
            PlanStep("s1", "Vague step", "somebody"),  # Invalid owner
        ]
        
        with pytest.raises(InvalidPlanError):
            validate_plan("Goal", steps)


class TestConflictingEvidence:
    """Tests for behavior when evidence conflicts with intent."""

    def test_grounding_requires_valid_evidence(self):
        """System should reject claims that cite invalid evidence."""
        from src.core.evals import eval_grounding
        
        report = "According to [EVID:ev_a], X is true. But [EVID:ev_b] says opposite."
        evidence_ids = ["ev_a"]  # ev_b doesn't exist
        
        result = eval_grounding(report, evidence_ids)
        
        assert result.passed is False
        assert "ev_b" in str(result.reasons)


class TestBorderlineProactive:
    """Tests for borderline proactive trigger conditions."""

    def test_borderline_confidence_blocks(self):
        """Borderline confidence should err on side of blocking."""
        from src.core.proactive import evaluate_proactive_action, MIN_PROACTIVE_CONFIDENCE
        
        # Just below threshold
        decision = evaluate_proactive_action(
            action_type="auto_action",
            confidence=MIN_PROACTIVE_CONFIDENCE - 0.01,
            reason="Maybe should act"
        )
        
        assert decision.blocked is True

    def test_exactly_at_threshold_allowed(self):
        """Exactly at threshold should be allowed."""
        from src.core.proactive import evaluate_proactive_action, MIN_PROACTIVE_CONFIDENCE
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        decision = evaluate_proactive_action(
            action_type="auto_action",
            confidence=MIN_PROACTIVE_CONFIDENCE,
            reason="Should act"
        )
        
        assert decision.blocked is False


class TestClarificationOverAssumption:
    """Tests that system prefers clarity over assumptions."""

    def test_low_attribution_confidence_visible(self):
        """Low attribution confidence should be visible in output."""
        from src.core.failure_attribution import attribute_failure
        
        # Ambiguous error
        attr = attribute_failure("Something happened somewhere")
        
        # Confidence should be moderate (not high)
        assert attr.confidence < 0.9
        # Root cause should be explicit even if unknown
        assert attr.root_cause in ["unknown", "tool", "data", "prompt", "policy"]


class TestAbortOverHallucinatedCompletion:
    """Tests that system aborts rather than hallucinate."""

    def test_empty_evidence_fails_grounding(self):
        """Reports with no citations should fail."""
        from src.core.evals import eval_grounding
        
        report = "The data clearly shows that X happened and Y is true."
        
        result = eval_grounding(report, evidence_ids=["ev_001"])
        
        assert result.passed is False
        assert result.severity == "fail"

    def test_fabricated_evidence_fails(self):
        """Fabricated evidence citations should fail."""
        from src.core.evals import eval_grounding
        
        report = "According to [EVID:made_up_id], the market moved."
        
        result = eval_grounding(report, evidence_ids=["ev_real_001"])
        
        assert result.passed is False


class TestConservativeConfidenceLabeling:
    """Tests for conservative confidence scoring."""

    def test_unknown_errors_get_low_confidence(self):
        """Unknown error patterns should get lower confidence."""
        from src.core.failure_attribution import attribute_failure
        
        # Known pattern
        known = attribute_failure("Connection timeout occurred")
        
        # Unknown pattern
        unknown = attribute_failure("Xyzzy frobnicator failed")
        
        # Unknown should have lower or equal confidence
        assert unknown.confidence <= known.confidence

    def test_proactive_suppression_on_uncertainty(self):
        """High uncertainty should suppress proactive actions."""
        from src.core.proactive import suppress_false_positive
        
        context = {"context_uncertainty": 0.5}  # High uncertainty
        
        should_suppress = suppress_false_positive("auto_action", context)
        
        assert should_suppress is True
