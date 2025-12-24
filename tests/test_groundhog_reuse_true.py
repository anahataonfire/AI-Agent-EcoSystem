
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from src.graph.workflow import pruned_thinker_node, get_latest_final_report_by_query_hash
from src.core.evidence_store import EvidenceStore

class TestGroundhogReuseTrue:
    """Test the True Reuse logic using Evidence Store."""

    @pytest.fixture
    def mock_store(self):
        with patch("src.graph.workflow.EvidenceStore") as mock:
            yield mock

    def test_get_report_returns_markdown(self, mock_store):
        # Setup
        mock_instance = mock_store.return_value
        mock_instance.get.return_value = {"markdown": "# Full Report"}
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result == "# Full Report"
        mock_instance.get.assert_called_with("report:abc1234")

    def test_get_report_returns_none_if_missing(self, mock_store):
        mock_instance = mock_store.return_value
        mock_instance.get.return_value = None
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result is None

    def test_A_path_returns_full_report_if_available(self, mock_store):
        # Setup specific mock behavior
        mock_instance = mock_store.return_value
        mock_instance.get.return_value = {"markdown": "# Full Content from Store"}
        
        # Mock State
        clarification_msg = "[[CLARIFICATION_REQUIRED]] ... reply A or B ..."
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content=clarification_msg),
            HumanMessage(content="A")
        ]
        
        identity = {
            "last_successful_run": {
                "query_hash": "abc1234",
                "completed_at": "now",
            }
        }
        
        mock_state = MagicMock()
        mock_state.messages = messages
        mock_state.identity_context = identity
        
        result = pruned_thinker_node(mock_state)
        
        msg_content = result["messages"][0].content
        assert "# Full Content from Store" in msg_content
        assert "[[CLARIFICATION_REQUIRED]]" in msg_content
        assert "terminate" in msg_content
        # Ensure we didn't get the fallback metadata table
        assert "Prior Run Summary (Metadata Only)" not in msg_content

    def test_A_path_falls_back_to_metadata(self, mock_store):
        # Setup: Missing evidence
        mock_instance = mock_store.return_value
        mock_instance.get.return_value = None
        
        # Mock State (Same as above)
        clarification_msg = "[[CLARIFICATION_REQUIRED]] ... reply A or B ..."
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content=clarification_msg),
            HumanMessage(content="A")
        ]
        
        identity = {
            "last_successful_run": {
                "query_hash": "abc1234",
                "completed_at": "2025-01-01",
                "evidence_count": 99,
                "sources_used": ["rss:bbc"]
            }
        }
        
        mock_state = MagicMock()
        mock_state.messages = messages
        mock_state.identity_context = identity
        
        result = pruned_thinker_node(mock_state)
        
        msg_content = result["messages"][0].content
        # Should have Metadata Table
        assert "Prior Run Summary (Metadata Only)" in msg_content
        assert "evidence cache miss" in msg_content
        assert "Evidence Count:** 99" in msg_content
