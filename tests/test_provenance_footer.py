
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from src.graph.workflow import _build_provenance_footer, reporter_node
from src.graph.state import RunState, ItemStatus

class TestProvenanceFooterHelper:
    """Test the footer construction helper directly."""

    def test_footer_structure_and_timestamp(self):
        footer = _build_provenance_footer(
            mode="Normal",
            query_hash="abcdef1234567890",
            evidence_count=5,
            evidence_map={"1": {"source_url": "rss:bbc"}},
            identity_writes=True
        )
        
        assert "Execution Provenance" in footer
        assert "Mode: Normal" in footer
        assert "Query Hash: abcdef1234567890" in footer
        assert "Evidence Collected: 5" in footer
        assert "Sources Used: rss:bbc" in footer
        assert "Identity Writes: yes" in footer
        assert "Timestamp (UTC):" in footer
        
        # Verify timestamp is recent UTC
        import re
        ts_match = re.search(r"Timestamp \(UTC\): (.*)", footer)
        assert ts_match
        ts_str = ts_match.group(1).strip()
        # Should be ISO formatted
        dt = datetime.fromisoformat(ts_str)
        assert dt.tzinfo == timezone.utc

class TestProvenanceFooterIntegration:
    """Test integration in reporter_node."""

    @patch("src.core.identity_manager.update_identity")
    @patch("src.core.identity_manager.create_snapshot")
    def test_normal_success_footer(self, mock_create, mock_update):
        # Mock successful state
        mock_update.return_value = None
        mock_create.return_value = "mock_hash"
        
        state = RunState(
            messages=[HumanMessage(content="Test Query")],
            evidence_map={
                "e1": {"title": "T1", "source_url": "rss:bbc"},
                "e2": {"title": "T2", "source_url": "rss:reuters"}
            },
            circuit_breaker={"step_count": 3}
        )
        
        result = reporter_node(state)
        
        final_msg = result["messages"][0].content
        assert "Execution Provenance" in final_msg
        assert "Mode: Normal" in final_msg
        assert "Identity Writes: yes" in final_msg
        assert "Sources Used: rss:bbc, rss:reuters" in final_msg, "Sources order is sorted deteministically"

    def test_fallback_footer(self):
        # Mock specific failure path where no evidence is collected
        state = RunState(
            messages=[HumanMessage(content="Test Query")],
            evidence_map={}, # Empty implies fallback
            circuit_breaker={"step_count": 1}
        )
        
        result = reporter_node(state)
        
        final_msg = result["messages"][0].content
        assert "Execution Provenance" in final_msg
        assert "Mode: Fallback" in final_msg
        assert "Identity Writes: no" in final_msg
        assert "Evidence Collected: 0" in final_msg

    def test_clarification_footer(self):
        # Mock clarification logic
        clarification_text = "[[CLARIFICATION_REQUIRED]]\nterminate"
        state = RunState(
            messages=[
                HumanMessage(content="Test Query"),
                AIMessage(content=clarification_text) # Last message has marker to trigger early return
            ]
        )
        
        result = reporter_node(state)
        
        final_msg = result["messages"][0].content
        assert "Execution Provenance" in final_msg
        assert "Mode: Clarification Required" in final_msg
        assert "Identity Writes: no" in final_msg
        assert "Sources Used: none" in final_msg
