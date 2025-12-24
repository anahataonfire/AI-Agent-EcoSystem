"""
Agent Character Consistency Tests (Prompt 9).

Ensures agents don't converge into generic behavior.
"""

import pytest


class TestAgentDecisionPaths:
    """Tests that agents take different decision paths."""

    def test_thinker_focuses_on_planning(self):
        """Thinker should focus on plan validation."""
        from src.agents.manifest import AGENT_MANIFESTS, check_capability
        
        thinker = AGENT_MANIFESTS["thinker"]
        
        # Thinker should read but not write evidence
        assert check_capability("thinker", "read_evidence") is True
        assert check_capability("thinker", "write_evidence") is False
        
        # Thinker should not write identity
        assert check_capability("thinker", "write_identity") is False

    def test_executor_focuses_on_tools(self):
        """Executor should focus on tool execution."""
        from src.agents.manifest import AGENT_MANIFESTS, get_allowed_tools, check_capability
        
        # Executor should have tool access
        tools = get_allowed_tools("executor")
        assert len(tools) > 0
        
        executor = AGENT_MANIFESTS["executor"]
        
        # Executor should not write identity
        assert check_capability("executor", "write_identity") is False

    def test_reporter_unique_write_access(self):
        """Reporter should have unique identity write access."""
        from src.agents.manifest import check_capability
        
        agents = ["thinker", "sanitizer", "executor", "reporter"]
        
        writers = [a for a in agents if check_capability(a, "write_identity")]
        
        # Only reporter can write
        assert writers == ["reporter"]


class TestAgentRefusalPatterns:
    """Tests that agents have different refusal patterns."""

    def test_thinker_has_limited_tools(self):
        """Thinker has limited tool access (planning only)."""
        from src.agents.manifest import AGENT_MANIFESTS
        
        thinker = AGENT_MANIFESTS["thinker"]
        
        # Thinker has read-only tools (no write evidence)
        assert thinker["write_evidence"] is False

    def test_sanitizer_refuses_content_generation(self):
        """Sanitizer should refuse to generate content."""
        from src.agents.manifest import AGENT_MANIFESTS, check_capability
        
        # Sanitizer cannot write identity (content)
        assert check_capability("sanitizer", "write_identity") is False
        # Sanitizer cannot write evidence (generate)
        assert check_capability("sanitizer", "write_evidence") is False

    def test_executor_refuses_report_generation(self):
        """Executor should refuse to generate reports."""
        from src.agents.manifest import check_capability
        
        assert check_capability("executor", "write_identity") is False


class TestInvariantCompliance:
    """Tests that all agents comply with same invariants."""

    def test_all_agents_respect_red_lines(self):
        """All agents should respect red-line prohibitions."""
        from src.core.red_lines import (
            validate_no_red_line_violation,
            RedLineViolationError
        )
        from src.core.run_ledger import reset_ledger
        
        agents = ["thinker", "sanitizer", "executor"]  # Not reporter
        
        for agent in agents:
            reset_ledger()
            with pytest.raises(RedLineViolationError):
                validate_no_red_line_violation("write_identity", agent)

    def test_all_agents_use_same_failure_codes(self):
        """All agents should use canonical failure codes."""
        from src.core.failures import get_all_codes
        
        codes = get_all_codes()
        
        # All codes should follow DTL-XXX-YYY format
        for name, fc in codes.items():
            assert fc.code.startswith("DTL-")
            assert len(fc.code.split("-")) == 3


class TestAgentPersonalityDistinctness:
    """Tests that agent behaviors are distinct, not generic."""

    def test_manifest_uniqueness(self):
        """Each agent manifest should be unique."""
        from src.agents.manifest import AGENT_MANIFESTS
        
        manifests = list(AGENT_MANIFESTS.values())
        
        # Check each pair is different
        for i, m1 in enumerate(manifests):
            for j, m2 in enumerate(manifests):
                if i < j:
                    # At least one capability should differ
                    differs = (
                        m1["read_identity"] != m2["read_identity"] or
                        m1["write_identity"] != m2["write_identity"] or
                        m1["read_evidence"] != m2["read_evidence"] or
                        m1["write_evidence"] != m2["write_evidence"] or
                        m1["invoke_tools"] != m2["invoke_tools"]
                    )
                    assert differs, f"Agents {i} and {j} have identical manifests"

    def test_capability_spread(self):
        """Capabilities should be spread across agents."""
        from src.agents.manifest import AGENT_MANIFESTS
        
        # Count how many agents have each capability
        read_identity = sum(1 for m in AGENT_MANIFESTS.values() if m["read_identity"])
        write_identity = sum(1 for m in AGENT_MANIFESTS.values() if m["write_identity"])
        invoke_tools = sum(1 for m in AGENT_MANIFESTS.values() if m["invoke_tools"])
        
        # Capabilities should not be all-or-nothing
        assert 0 < write_identity <= 1  # Only reporter
        assert read_identity >= 2  # Multiple can read
        assert 0 < invoke_tools < 4  # Some but not all
