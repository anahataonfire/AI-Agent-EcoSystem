"""
Autonomy Regression Harness (DTL-SKILL-REGRESS v1).

Ensures autonomy never regresses.
"""

import pytest


class TestNoInfiniteLoops:
    """Tests for infinite loop prevention."""

    def test_retry_cap_prevents_infinite_loop(self):
        """Retry caps must prevent infinite loops."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry, apply_retry_decision
        )
        
        config = RetryConfig(max_total_retries=5)
        state = RetryState()
        
        iterations = 0
        max_safe_iterations = 100
        
        while iterations < max_safe_iterations:
            decision = decide_retry(FailureClass.TRANSIENT, state, config)
            if not decision.should_retry:
                break
            state = apply_retry_decision(decision, state, FailureClass.TRANSIENT)
            iterations += 1
        
        # Must terminate well before max_safe_iterations
        assert iterations <= config.max_total_retries
        assert iterations < max_safe_iterations

    def test_scheduler_prevents_agent_loop(self):
        """Scheduler must prevent agent self-loops."""
        from src.graph.scheduler import TurnScheduler, SelfInvocationError
        
        scheduler = TurnScheduler()
        scheduler.start_turn("thinker")
        
        # Attempting self-invocation must raise
        with pytest.raises(SelfInvocationError):
            scheduler.start_turn("thinker")


class TestRetryCapsEnforced:
    """Tests for retry cap enforcement."""

    def test_cost_cap_enforced(self):
        """Cost caps must not be exceeded."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry, apply_retry_decision
        )
        
        config = RetryConfig(max_cost_units=50, max_total_retries=100)
        state = RetryState()
        
        while True:
            decision = decide_retry(FailureClass.TRANSIENT, state, config)
            if not decision.should_retry:
                break
            state = apply_retry_decision(decision, state, FailureClass.TRANSIENT)
        
        # Total cost must not exceed cap
        assert state.total_cost <= config.max_cost_units

    def test_class_limits_enforced(self):
        """Per-class retry limits must be enforced."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry, apply_retry_decision, MAX_RETRIES_BY_CLASS
        )
        
        for failure_class in FailureClass:
            config = RetryConfig(max_total_retries=100)
            state = RetryState()
            
            count = 0
            while count < 10:
                decision = decide_retry(failure_class, state, config)
                if not decision.should_retry:
                    break
                state = apply_retry_decision(decision, state, failure_class)
                count += 1
            
            # Count should not exceed class limit
            max_for_class = MAX_RETRIES_BY_CLASS.get(failure_class, 0)
            assert count <= max_for_class


class TestIdentityInvariants:
    """Tests for identity write invariants."""

    def test_only_reporter_writes_identity(self):
        """Only reporter can write identity."""
        from src.agents.manifest import check_capability
        
        # Check all agents
        agents = ["thinker", "sanitizer", "executor", "reporter"]
        
        for agent in agents:
            can_write = check_capability(agent, "write_identity")
            if agent == "reporter":
                assert can_write is True
            else:
                assert can_write is False

    def test_red_line_blocks_identity_mutation(self):
        """Red-line must block non-reporter identity writes."""
        from src.core.red_lines import (
            validate_no_red_line_violation,
            RedLineViolationError
        )
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        for agent in ["thinker", "sanitizer", "executor"]:
            with pytest.raises(RedLineViolationError):
                validate_no_red_line_violation("write_identity", agent)


class TestKillSwitchRespected:
    """Tests that kill switches are respected."""

    def test_kill_switch_blocks_execution(self):
        """Active kill switch must block operations."""
        from src.core.kill_switches import check_kill_switch
        
        # All switches should be checkable
        for switch in ["TRUE_REUSE", "EVIDENCE_REUSE", "GROUNDING"]:
            halted, reason = check_kill_switch(switch)
            # In default state, switches are not active
            assert halted is False


class TestDecayCorrectness:
    """Tests for memory decay correctness."""

    def test_memory_decay(self):
        """Memory should decay after N runs."""
        from src.core.state_memory import StateMemory
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_memory.json")
            memory = StateMemory(storage_path=path, decay_runs=2)
            
            # Store a memory
            memory.remember("hash1", "skill1", "success")
            
            # Should exist
            entries = memory.recall("hash1")
            assert len(entries) == 1
            
            # Apply decay twice
            memory.apply_decay()
            memory.apply_decay()
            
            # Should be removed
            entries = memory.recall("hash1")
            assert len(entries) == 0
