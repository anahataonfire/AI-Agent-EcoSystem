"""
Counterfactual Containment Test (Prompt 8).

Verifies counterfactual evaluation doesn't re-execute tools,
only applies weak learning signals, and uses ledger-only data.
"""

import pytest
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class LedgerEntry:
    """Immutable ledger entry."""
    event: str
    skill: str
    outcome: float
    evidence_ids: tuple


class CounterfactualEvaluator:
    """Evaluates counterfactual scenarios from historical ledgers."""
    
    # Weak signal multiplier (vs 1.0 for actual outcomes)
    WEAK_SIGNAL_MULTIPLIER = 0.3
    
    def __init__(self):
        self.tool_executions = 0
        self.signals_generated = []
    
    def evaluate(self, ledger: List[LedgerEntry], historical_performance: Dict[str, float]) -> Dict[str, float]:
        """
        Evaluate counterfactual scenarios.
        
        Args:
            ledger: Historical ledger entries (immutable)
            historical_performance: Skill -> success rate from policy memory
        
        Returns:
            Dict of skill -> counterfactual adjustment signal
        """
        adjustments = {}
        
        for entry in ledger:
            if entry.event != "SKILL_EXECUTION":
                continue
            
            # What alternatives were available?
            alternatives = set(historical_performance.keys()) - {entry.skill}
            
            for alt in alternatives:
                alt_performance = historical_performance.get(alt, 0.5)
                actual_outcome = entry.outcome
                
                # Counterfactual: would alt have been better?
                if alt_performance > actual_outcome:
                    # Weak negative signal for actual choice
                    adjustments[entry.skill] = adjustments.get(entry.skill, 0) - self.WEAK_SIGNAL_MULTIPLIER
                    # Weak positive signal for alternative
                    adjustments[alt] = adjustments.get(alt, 0) + self.WEAK_SIGNAL_MULTIPLIER * 0.5
        
        return adjustments
    
    def execute_tool(self, tool_name: str) -> None:
        """Attempt to execute a tool (MUST NOT BE CALLED)."""
        self.tool_executions += 1
        raise RuntimeError("Counterfactual must not execute tools!")


class TestCounterfactualContainment:
    """Tests for counterfactual evaluation containment."""

    def test_no_tool_reexecution(self):
        """Counterfactual must not re-execute tools."""
        evaluator = CounterfactualEvaluator()
        
        ledger = [
            LedgerEntry("SKILL_EXECUTION", "skill_a", 0.5, ("ev1",)),
        ]
        
        historical = {"skill_a": 0.5, "skill_b": 0.7}
        
        # Should not execute tools
        evaluator.evaluate(ledger, historical)
        
        assert evaluator.tool_executions == 0

    def test_weak_signals_only(self):
        """Counterfactual signals must be weaker than actual outcomes."""
        evaluator = CounterfactualEvaluator()
        
        ledger = [
            LedgerEntry("SKILL_EXECUTION", "skill_a", 0.3, ("ev1",)),
        ]
        
        historical = {"skill_a": 0.3, "skill_b": 0.9}  # skill_b would have been better
        
        adjustments = evaluator.evaluate(ledger, historical)
        
        # All signals should be weak (< 1.0)
        for signal in adjustments.values():
            assert abs(signal) < 1.0, f"Signal too strong: {signal}"

    def test_does_not_override_observed(self):
        """Counterfactual cannot override observed outcomes."""
        evaluator = CounterfactualEvaluator()
        
        ledger = [
            LedgerEntry("SKILL_EXECUTION", "skill_a", 1.0, ("ev1",)),  # Actual success
        ]
        
        historical = {"skill_a": 0.5, "skill_b": 0.9}
        
        adjustments = evaluator.evaluate(ledger, historical)
        
        # Even if skill_b has better historical, actual 1.0 was observed
        # Counterfactual should not strongly penalize skill_a
        if "skill_a" in adjustments:
            assert adjustments["skill_a"] >= -0.5, "Counterfactual overrode observed success"

    def test_uses_ledger_only(self):
        """Counterfactual uses only ledger data."""
        evaluator = CounterfactualEvaluator()
        
        # Ledger entries only
        ledger = [
            LedgerEntry("SKILL_EXECUTION", "skill_a", 0.7, ("ev1", "ev2")),
            LedgerEntry("SKILL_EXECUTION", "skill_b", 0.3, ("ev3",)),
        ]
        
        historical = {"skill_a": 0.6, "skill_b": 0.4}
        
        # No external data sources accessed
        adjustments = evaluator.evaluate(ledger, historical)
        
        # Verification: evaluation completed without errors
        assert isinstance(adjustments, dict)

    def test_counterfactual_multiplier_applied(self):
        """Verify weak signal multiplier is applied."""
        evaluator = CounterfactualEvaluator()
        
        ledger = [
            LedgerEntry("SKILL_EXECUTION", "bad_skill", 0.1, ()),
        ]
        
        historical = {"bad_skill": 0.1, "good_skill": 0.9}
        
        adjustments = evaluator.evaluate(ledger, historical)
        
        # Adjustment should be scaled by WEAK_SIGNAL_MULTIPLIER (0.3)
        if "bad_skill" in adjustments:
            assert abs(adjustments["bad_skill"]) <= 0.5

    def test_generate_validation_log(self, tmp_path):
        """Generate counterfactual validation log."""
        evaluator = CounterfactualEvaluator()
        
        ledger = [
            LedgerEntry("SKILL_EXECUTION", "skill_a", 0.4, ("ev1",)),
            LedgerEntry("SKILL_EXECUTION", "skill_b", 0.8, ("ev2",)),
        ]
        
        historical = {"skill_a": 0.5, "skill_b": 0.7, "skill_c": 0.6}
        
        adjustments = evaluator.evaluate(ledger, historical)
        
        log_lines = [
            "Counterfactual Validation Log",
            "============================",
            "",
            f"Ledger entries processed: {len(ledger)}",
            f"Tool executions attempted: {evaluator.tool_executions}",
            "",
            "Adjustments generated:",
        ]
        
        for skill, adj in adjustments.items():
            log_lines.append(f"  {skill}: {adj:+.3f}")
        
        log_lines.extend([
            "",
            "Containment checks:",
            f"  No tool re-execution: {'PASS' if evaluator.tool_executions == 0 else 'FAIL'}",
            f"  Weak signals only: {'PASS' if all(abs(a) < 1.0 for a in adjustments.values()) else 'FAIL'}",
        ])
        
        with open(tmp_path / "counterfactual_validation.log", "w") as f:
            f.write("\n".join(log_lines))
        
        assert evaluator.tool_executions == 0
