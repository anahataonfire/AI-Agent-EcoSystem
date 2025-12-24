
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

class TestGroundhogDayResponses:
    """Test handling of user responses (A/B) to clarification."""

    @patch("src.graph.workflow.core_thinker_node")
    def test_response_A_triggers_reuse(self, mock_core_thinker):
        from src.graph.workflow import pruned_thinker_node
        from langchain_core.messages import AIMessage, HumanMessage

        clarification_msg = "[[CLARIFICATION_REQUIRED]] ... reply A or B ..."
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content=clarification_msg),
            HumanMessage(content="A")
        ]
        
        # Mock RunState
        mock_state = MagicMock()
        mock_state.messages = messages
        mock_state.identity_context = {}
        mock_state.evidence_map = {}

        result = pruned_thinker_node(mock_state)
        
        # Should return Reuse message
        assert "messages" in result
        msg_content = result["messages"][0].content
        assert "[[CLARIFICATION_REQUIRED]]" in msg_content
        assert "Prior Run Summary (Metadata Only)" in msg_content
        assert "DTL v0 Note" in msg_content
        assert "terminate" in msg_content
        
        # Should NOT call core thinker
        mock_core_thinker.assert_not_called()

    @patch("src.graph.workflow.core_thinker_node")
    def test_response_B_proceeds_to_execution(self, mock_core_thinker):
        from src.graph.workflow import pruned_thinker_node
        import hashlib
        from langchain_core.messages import AIMessage, HumanMessage
        
         # Setup condition that WOULD trigger groundhog if not bypassed
        query = "Same query"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        recent_time = datetime.now(timezone.utc).isoformat()
        
        clarification_msg = "[[CLARIFICATION_REQUIRED]] ... reply A or B ..."
        messages = [
            HumanMessage(content=query),
            AIMessage(content=clarification_msg),
            HumanMessage(content="B")
        ]
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": recent_time,
                "evidence_count": 5,
                "sources_used": ["rss:bbc"]
            }
        }
        
        mock_state = MagicMock()
        mock_state.messages = messages
        mock_state.identity_context = identity
        mock_state.evidence_map = {}
        
        # Mock core_thinker to return something specific
        mock_core_thinker.return_value = {"messages": [], "current_plan": "mock_plan"}
        
        result = pruned_thinker_node(mock_state)
        
        # Should call core thinker (meaning it bypassed the return clarification)
        mock_core_thinker.assert_called_once()
        assert result == {"messages": [], "current_plan": "mock_plan"}

    @patch("src.graph.workflow.core_thinker_node")
    def test_ambiguous_response_triggers_clarification_again(self, mock_core_thinker):
        from src.graph.workflow import pruned_thinker_node
        import hashlib
        from langchain_core.messages import AIMessage, HumanMessage
        
        # Same setup as B, but response "C"
        query = "Same query"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        recent_time = datetime.now(timezone.utc).isoformat()
        
        clarification_msg = "[[CLARIFICATION_REQUIRED]] ... reply A or B ..."
        messages = [
            HumanMessage(content=query),
            AIMessage(content=clarification_msg),
            HumanMessage(content="C") # Ambiguous
        ]
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": recent_time,
                "evidence_count": 5,
                "sources_used": ["rss:bbc"]
            }
        }
        
        mock_state = MagicMock()
        mock_state.messages = messages
        mock_state.identity_context = identity
        mock_state.evidence_map = {}
        
        result = pruned_thinker_node(mock_state)
        
        # Should NOT call core thinker
        mock_core_thinker.assert_not_called()
        
        # Should return clarification again
        assert "messages" in result
        assert "[[CLARIFICATION_REQUIRED]]" in result["messages"][0].content
        assert "minutes ago" in result["messages"][0].content
