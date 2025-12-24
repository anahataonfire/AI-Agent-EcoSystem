"""
Evals Pipeline Tests (DTL-SKILL-EVAL v1).
"""

import pytest


class TestGroundingEval:
    """Tests for grounding evaluation."""

    def test_valid_citations_pass(self):
        """Valid citations should pass."""
        from src.core.evals import eval_grounding
        
        report = "The data shows [EVID:ev_001] that X happened [EVID:ev_002]."
        evidence_ids = ["ev_001", "ev_002"]
        
        result = eval_grounding(report, evidence_ids)
        
        assert result.passed is True
        assert result.severity == "info"

    def test_invalid_citations_fail(self):
        """Invalid citations should fail."""
        from src.core.evals import eval_grounding
        
        report = "According to [EVID:ev_fake], X happened."
        evidence_ids = ["ev_001", "ev_002"]
        
        result = eval_grounding(report, evidence_ids)
        
        assert result.passed is False
        assert result.severity == "fail"


class TestClaimDensityEval:
    """Tests for claim density evaluation."""

    def test_high_density_passes(self):
        """High claim density should pass."""
        from src.core.evals import eval_claim_density
        
        # 200 chars with 2 citations = good density
        report = "[EVID:a] " + "x" * 90 + " [EVID:b] " + "x" * 90
        
        result = eval_claim_density(report)
        
        assert result.passed is True


class TestEvidenceReuseSafety:
    """Tests for evidence reuse safety."""

    def test_same_query_passes(self):
        """Same query evidence should pass."""
        from src.core.evals import eval_evidence_reuse_safety
        
        result = eval_evidence_reuse_safety(
            evidence_ids=["ev_001", "ev_002"],
            query_hash="hash_abc",
            evidence_query_hashes={"ev_001": "hash_abc", "ev_002": "hash_abc"}
        )
        
        assert result.passed is True

    def test_cross_query_fails(self):
        """Cross-query evidence should fail."""
        from src.core.evals import eval_evidence_reuse_safety
        
        result = eval_evidence_reuse_safety(
            evidence_ids=["ev_001", "ev_002"],
            query_hash="hash_abc",
            evidence_query_hashes={"ev_001": "hash_abc", "ev_002": "hash_different"}
        )
        
        assert result.passed is False
        assert result.severity == "fail"


class TestEvalAbort:
    """Tests for eval-triggered abort."""

    def test_fail_severity_aborts(self):
        """Fail severity should trigger abort."""
        from src.core.evals import check_eval_pass, EvalResult, EvalFailureError
        
        results = [
            EvalResult(passed=True, reasons=[], severity="info"),
            EvalResult(passed=False, reasons=["Bad citation"], severity="fail"),
        ]
        
        with pytest.raises(EvalFailureError):
            check_eval_pass(results)
