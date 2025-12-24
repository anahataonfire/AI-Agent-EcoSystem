
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from src.graph.workflow import get_latest_final_report_by_query_hash


class TestGroundhogReuseSafety:
    """Test hardening of Groundhog reuse logic."""

    @pytest.fixture
    def mock_store(self):
        with patch("src.graph.workflow.EvidenceStore") as mock:
            yield mock

    def test_reject_mismatched_query_hash(self, mock_store):
        """Report stored with different hash should be rejected."""
        mock_instance = mock_store.return_value
        mock_instance.get_with_metadata.return_value = {
            "payload": {"markdown": "# Report\n\n### Execution Provenance\n..."},
            "metadata": {
                "query_hash": "DIFFERENT_HASH",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "type": "final_report"
            }
        }
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result is None

    def test_reject_stale_completed_at(self, mock_store):
        """Report older than 15 minutes should be rejected."""
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        
        mock_instance = mock_store.return_value
        mock_instance.get_with_metadata.return_value = {
            "payload": {"markdown": "# Report\n\n### Execution Provenance\n..."},
            "metadata": {
                "query_hash": "abc1234",
                "completed_at": stale_time,
                "type": "final_report"
            }
        }
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result is None

    def test_reject_missing_footer(self, mock_store):
        """Report without Execution Provenance footer should be rejected."""
        mock_instance = mock_store.return_value
        mock_instance.get_with_metadata.return_value = {
            "payload": {"markdown": "# Report without footer"},
            "metadata": {
                "query_hash": "abc1234",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "type": "final_report"
            }
        }
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result is None

    def test_reject_wrong_type(self, mock_store):
        """Evidence with type != final_report should be rejected."""
        mock_instance = mock_store.return_value
        mock_instance.get_with_metadata.return_value = {
            "payload": {"markdown": "# Report\n\n### Execution Provenance\n..."},
            "metadata": {
                "query_hash": "abc1234",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "type": "rss_item"  # Wrong type
            }
        }
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result is None

    def test_accept_valid_report(self, mock_store):
        """Valid report with all checks passing should be returned."""
        valid_markdown = "# Report\n\n### Execution Provenance\n- Mode: Normal"
        mock_instance = mock_store.return_value
        mock_instance.get_with_metadata.return_value = {
            "payload": {"markdown": valid_markdown},
            "metadata": {
                "query_hash": "abc1234",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "type": "final_report"
            }
        }
        
        result = get_latest_final_report_by_query_hash("abc1234")
        
        assert result == valid_markdown

    def test_accept_report_within_custom_window(self, mock_store):
        """Report within custom time window should be accepted."""
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat()
        valid_markdown = "# Report\n\n### Execution Provenance\n- Mode: Normal"
        
        mock_instance = mock_store.return_value
        mock_instance.get_with_metadata.return_value = {
            "payload": {"markdown": valid_markdown},
            "metadata": {
                "query_hash": "abc1234",
                "completed_at": recent_time,
                "type": "final_report"
            }
        }
        
        # 25 min old, but within_minutes=30 should pass
        result = get_latest_final_report_by_query_hash("abc1234", within_minutes=30)
        
        assert result == valid_markdown
