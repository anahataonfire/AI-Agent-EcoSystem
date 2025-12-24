"""
Goal Reformulation Guardrail Attack Test (Prompt 9).

Attempts adversarial goal reformulations and verifies strict rejection.
"""

import pytest
import json
from typing import Dict, Any, Tuple


# DTL-STRAT codes for reformulation
CODES = {
    "LOW_CONFIDENCE": "DTL-STRAT-007",
    "INTENT_DRIFT": "DTL-STRAT-008",
    "UNGROUNDED": "DTL-STRAT-009",
    "SCOPE_EXPANSION": "DTL-STRAT-010",
    "UNLOGGED": "DTL-STRAT-011",
}


class GoalReformulator:
    """Goal reformulation with guardrails."""
    
    MIN_CONFIDENCE = 0.9
    MIN_SIMILARITY = 0.95
    
    def __init__(self):
        self.ledger = []
    
    def reformulate(
        self,
        original: str,
        proposed: str,
        confidence: float,
        similarity: float,
        evidence_ids: list,
        log_first: bool = True
    ) -> Tuple[bool, str, str]:
        """
        Attempt goal reformulation.
        
        Returns:
            (success, result_goal, failure_code)
        """
        # Must log before execution
        if not log_first:
            return False, original, CODES["UNLOGGED"]
        
        # Log the attempt
        self.ledger.append({
            "event": "GOAL_REFORMULATION_ATTEMPT",
            "original": original,
            "proposed": proposed,
            "confidence": confidence,
            "similarity": similarity
        })
        
        # Check confidence
        if confidence < self.MIN_CONFIDENCE:
            return False, original, CODES["LOW_CONFIDENCE"]
        
        # Check similarity
        if similarity < self.MIN_SIMILARITY:
            return False, original, CODES["INTENT_DRIFT"]
        
        # Check evidence support
        if not evidence_ids:
            return False, original, CODES["UNGROUNDED"]
        
        # Check for scope expansion (heuristic: reformulation longer than original)
        if len(proposed.split()) > len(original.split()) * 1.5:
            return False, original, CODES["SCOPE_EXPANSION"]
        
        # Approved
        self.ledger.append({
            "event": "GOAL_REFORMULATION_APPROVED",
            "new_goal": proposed
        })
        return True, proposed, ""


class TestGoalReformulationAttack:
    """Tests for goal reformulation attack scenarios."""

    def test_scope_expansion_rejected(self):
        """Scope expansion should be rejected."""
        reformulator = GoalReformulator()
        
        success, result, code = reformulator.reformulate(
            original="Get Apple earnings",
            proposed="Get Apple and Google and Microsoft and Amazon earnings for all quarters",
            confidence=0.95,
            similarity=0.7,  # Low similarity due to expansion
            evidence_ids=["ev1"]
        )
        
        assert success is False
        assert code in [CODES["INTENT_DRIFT"], CODES["SCOPE_EXPANSION"]]

    def test_topic_drift_rejected(self):
        """Topic drift should be rejected."""
        reformulator = GoalReformulator()
        
        success, result, code = reformulator.reformulate(
            original="What's the weather today?",
            proposed="What are the stock market returns?",
            confidence=0.95,
            similarity=0.3,  # Very low similarity
            evidence_ids=["ev1"]
        )
        
        assert success is False
        assert code == CODES["INTENT_DRIFT"]

    def test_assumption_injection_rejected(self):
        """Assumption injection (ungrounded) should be rejected."""
        reformulator = GoalReformulator()
        
        success, result, code = reformulator.reformulate(
            original="Summarize the news",
            proposed="Summarize the news from New York",
            confidence=0.95,
            similarity=0.96,
            evidence_ids=[]  # No evidence for NYC assumption
        )
        
        assert success is False
        assert code == CODES["UNGROUNDED"]

    def test_confidence_spoofing_rejected(self):
        """Low confidence reformulation should be rejected."""
        reformulator = GoalReformulator()
        
        success, result, code = reformulator.reformulate(
            original="Get market data",
            proposed="Get S&P 500 data",
            confidence=0.6,  # Too low
            similarity=0.97,
            evidence_ids=["ev1"]
        )
        
        assert success is False
        assert code == CODES["LOW_CONFIDENCE"]

    def test_unlogged_reformulation_rejected(self):
        """Reformulation without logging should be rejected."""
        reformulator = GoalReformulator()
        
        success, result, code = reformulator.reformulate(
            original="Get data",
            proposed="Get specific data",
            confidence=0.95,
            similarity=0.98,
            evidence_ids=["ev1"],
            log_first=False
        )
        
        assert success is False
        assert code == CODES["UNLOGGED"]

    def test_valid_reformulation_passes(self):
        """Valid reformulation should be approved."""
        reformulator = GoalReformulator()
        
        success, result, code = reformulator.reformulate(
            original="Get latest news for today",
            proposed="Get news from past 24 hours",
            confidence=0.95,
            similarity=0.97,
            evidence_ids=["ev_freshness_001"]
        )
        
        assert success is True
        assert result == "Get news from past 24 hours"
        assert code == ""
        assert any(e["event"] == "GOAL_REFORMULATION_APPROVED" for e in reformulator.ledger)

    def test_generate_attack_matrix(self, tmp_path):
        """Generate full attack matrix."""
        reformulator = GoalReformulator()
        
        attacks = [
            {
                "name": "scope_expansion",
                "original": "Get Apple data",
                "proposed": "Get Apple and Google and Microsoft data",
                "confidence": 0.95,
                "similarity": 0.6,
                "evidence": ["ev1"],
                "expected_code": CODES["INTENT_DRIFT"]
            },
            {
                "name": "topic_drift",
                "original": "Weather forecast",
                "proposed": "Stock prices",
                "confidence": 0.95,
                "similarity": 0.1,
                "evidence": ["ev1"],
                "expected_code": CODES["INTENT_DRIFT"]
            },
            {
                "name": "assumption_injection",
                "original": "News summary",
                "proposed": "NYC tech news summary",
                "confidence": 0.95,
                "similarity": 0.96,
                "evidence": [],
                "expected_code": CODES["UNGROUNDED"]
            },
            {
                "name": "low_confidence",
                "original": "Market data",
                "proposed": "S&P 500 data",
                "confidence": 0.5,
                "similarity": 0.97,
                "evidence": ["ev1"],
                "expected_code": CODES["LOW_CONFIDENCE"]
            },
            {
                "name": "unlogged",
                "original": "Get info",
                "proposed": "Get specific info",
                "confidence": 0.95,
                "similarity": 0.98,
                "evidence": ["ev1"],
                "expected_code": CODES["UNLOGGED"],
                "log_first": False
            },
        ]
        
        results = []
        for attack in attacks:
            success, result, code = reformulator.reformulate(
                original=attack["original"],
                proposed=attack["proposed"],
                confidence=attack["confidence"],
                similarity=attack["similarity"],
                evidence_ids=attack["evidence"],
                log_first=attack.get("log_first", True)
            )
            
            results.append({
                "attack": attack["name"],
                "rejected": not success,
                "expected_code": attack["expected_code"],
                "actual_code": code,
                "correct": code == attack["expected_code"]
            })
        
        with open(tmp_path / "goal_reformulation_attack_matrix.json", "w") as f:
            json.dump(results, f, indent=2)
        
        # All attacks should be rejected with correct codes
        assert all(r["rejected"] for r in results), "Some attacks were not rejected"
        assert all(r["correct"] for r in results), "Some attacks got wrong failure codes"
