"""
Deterministic Turn Scheduler Tests (Prompt AD).

Tests for fixed agent order, turn limits, and self-invocation prevention.
"""

import pytest


class TestTurnLimits:
    """Tests for turn limit enforcement."""

    def test_enforce_turn_limit(self):
        """Agent must not exceed MAX_AGENT_TURNS."""
        from src.graph.scheduler import TurnScheduler, TurnLimitExceededError
        
        scheduler = TurnScheduler(max_turns=2)
        
        # First two turns should succeed
        scheduler.start_turn("thinker")
        scheduler.end_turn()
        scheduler.start_turn("thinker")
        scheduler.end_turn()
        
        # Third turn should fail
        with pytest.raises(TurnLimitExceededError) as exc_info:
            scheduler.start_turn("thinker")
        
        assert "turn limit exceeded" in str(exc_info.value).lower()


class TestSelfInvocation:
    """Tests for self-invocation prevention."""

    def test_prevent_self_invocation(self):
        """Agent must not invoke itself."""
        from src.graph.scheduler import TurnScheduler, SelfInvocationError
        
        scheduler = TurnScheduler()
        
        scheduler.start_turn("thinker")
        
        # Attempting to start another turn while current is active
        with pytest.raises(SelfInvocationError):
            scheduler.start_turn("thinker")


class TestDeterministicOrder:
    """Tests for deterministic execution order."""

    def test_deterministic_order(self):
        """Execution order must be fixed and predictable."""
        from src.graph.scheduler import TurnScheduler, AGENT_ORDER
        
        scheduler = TurnScheduler()
        
        # Verify fixed order matches expected
        assert scheduler.get_execution_order() == AGENT_ORDER
        assert AGENT_ORDER == ["thinker", "sanitizer", "executor", "reporter"]

    def test_execution_history_recorded(self):
        """Execution history must be recorded accurately."""
        from src.graph.scheduler import TurnScheduler
        
        scheduler = TurnScheduler()
        
        scheduler.start_turn("thinker")
        scheduler.end_turn()
        scheduler.start_turn("sanitizer")
        scheduler.end_turn()
        scheduler.start_turn("executor")
        scheduler.end_turn()
        
        history = scheduler.get_execution_history()
        assert history == ["thinker", "sanitizer", "executor"]


class TestNoStarvation:
    """Tests for agent starvation prevention."""

    def test_no_starvation(self):
        """Every agent should get at least one turn opportunity."""
        from src.graph.scheduler import TurnScheduler, validate_no_starvation
        
        scheduler = TurnScheduler()
        
        # Execute all agents once
        for agent in ["thinker", "sanitizer", "executor", "reporter"]:
            scheduler.start_turn(agent)
            scheduler.end_turn()
        
        assert validate_no_starvation(scheduler) is True

    def test_starvation_detected(self):
        """Starvation should be detected when agents don't execute."""
        from src.graph.scheduler import TurnScheduler, validate_no_starvation
        
        scheduler = TurnScheduler()
        
        # Only execute some agents
        scheduler.start_turn("thinker")
        scheduler.end_turn()
        
        assert validate_no_starvation(scheduler) is False
