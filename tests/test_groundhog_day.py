"""
Tests for Groundhog Day prevention logic.

These tests verify that identical queries within the 15-minute window
trigger clarification instead of redundant execution.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.graph.workflow import check_groundhog_day


class TestGroundhogDayDetection:
    """Test the check_groundhog_day helper function."""
    
    def test_no_last_run_proceeds_normally(self):
        """If no last_successful_run fact, should proceed."""
        result = check_groundhog_day("Get me the latest AI news", {})
        assert result is None
    
    def test_empty_identity_context_proceeds_normally(self):
        """If identity_context is None, should proceed."""
        result = check_groundhog_day("Get me the latest AI news", None)
        assert result is None
    
    def test_different_query_proceeds_normally(self):
        """If query hash differs, should proceed."""
        import hashlib
        
        # First query
        query1 = "Get me the latest AI news"
        query1_hash = hashlib.sha256(query1.encode()).hexdigest()[:16]
        
        # Identity context from prior run with different query
        identity = {
            "last_successful_run": {
                "query_hash": "different123456",  # Different hash
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "evidence_count": 10,
                "sources_used": ["rss:bbc"]
            }
        }
        
        result = check_groundhog_day(query1, identity)
        assert result is None
    
    def test_same_query_outside_window_proceeds_normally(self):
        """If query matches but completed_at is >15 minutes ago, should proceed."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        # 20 minutes ago
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": old_time,
                "evidence_count": 10,
                "sources_used": ["rss:bbc"]
            }
        }
        
        result = check_groundhog_day(query, identity)
        assert result is None
    
    def test_same_query_within_window_triggers_clarification(self):
        """If query matches and completed_at is <15 minutes ago, should clarify."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        # 5 minutes ago
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": recent_time,
                "evidence_count": 10,
                "sources_used": ["rss:bbc"]
            }
        }
        
        result = check_groundhog_day(query, identity)
        
        assert result is not None
        assert "[[CLARIFICATION_REQUIRED]]" in result
        assert "5 minutes ago" in result
        assert "10 items" in result
        assert "rss:bbc" in result
        assert "terminate" in result
    
    def test_malformed_timestamp_proceeds_normally(self):
        """If completed_at is malformed, should proceed."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": "not-a-valid-timestamp",
                "evidence_count": 10,
                "sources_used": ["rss:bbc"]
            }
        }
        
        result = check_groundhog_day(query, identity)
        assert result is None
    
    def test_missing_timestamp_proceeds_normally(self):
        """If completed_at is missing, should proceed."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                # No completed_at
                "evidence_count": 10,
                "sources_used": ["rss:bbc"]
            }
        }
        
        result = check_groundhog_day(query, identity)
        assert result is None
    
    def test_z_suffix_timestamp_handled(self):
        """Timestamps with Z suffix should be parsed correctly."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        # 3 minutes ago with Z suffix
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
        recent_time = recent_time.replace("+00:00", "Z")
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": recent_time,
                "evidence_count": 5,
                "sources_used": ["rss:reuters"]
            }
        }
        
        result = check_groundhog_day(query, identity)
        
        assert result is not None
        assert "[[CLARIFICATION_REQUIRED]]" in result


class TestGroundhogDayIntegration:
    """Test integration with pruned_thinker_node and reporter_node."""
    
    def test_clarification_message_has_correct_format(self):
        """Verify the clarification message format."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=7)).isoformat()
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": recent_time,
                "evidence_count": 12,
                "sources_used": ["rss:bbc", "rss:reuters"]
            }
        }
        
        result = check_groundhog_day(query, identity)
        
        # Check all required elements
        assert "[[CLARIFICATION_REQUIRED]]" in result
        assert "7 minutes ago" in result
        assert "12 items" in result
        assert "rss:bbc" in result
        assert "rss:reuters" in result
        assert "**A)**" in result
        assert "**B)**" in result
        assert "terminate" in result
    
    def test_empty_sources_handled(self):
        """If sources_used is empty, should show 'available sources'."""
        import hashlib
        
        query = "Get me the latest AI news"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash,
                "completed_at": recent_time,
                "evidence_count": 5,
                "sources_used": []  # Empty
            }
        }
        
        result = check_groundhog_day(query, identity)
        
        assert result is not None
        assert "available sources" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
