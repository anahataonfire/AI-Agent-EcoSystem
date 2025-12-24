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

    def test_override_tokens_bypass_check(self):
        """Query containing override tokens should proceed even if hash matches."""
        import hashlib
        
        # Base query logic that WOULD match if not for the override check
        # NOTE: In reality, adding 'force' changes the hash, so it naturally mis-matches 
        # a prior run that didn't have 'force'.
        # TO TEST THE LOGIC explicitly, we must simulate a case where the PRIOR run
        # ALSO had 'force', or we artificially match the hashes.
        
        # Let's simple use a query that contains 'force' and manually align expectation
        # If I run "backup force" -> and last run was "backup force" 5 mins ago.
        # It SHOULD TRIGGER groundhog day (same hash/time).
        # But because of the token, it MUST NOT.
        
        query = "Run backup force"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        
        identity = {
            "last_successful_run": {
                "query_hash": query_hash, # Same hash!
                "completed_at": recent_time,
                "evidence_count": 5,
                "sources_used": ["rss:reuters"]
            }
        }
        
        # 1. Verify it BYPASSES due to 'force'
        result = check_groundhog_day(query, identity)
        assert result is None  # Should proceed
        
        # 2. Test "ignore previous"
        query2 = "ignore previous runs please"
        query2_hash = hashlib.sha256(query2.encode()).hexdigest()[:16]
        identity["last_successful_run"]["query_hash"] = query2_hash
        assert check_groundhog_day(query2, identity) is None

        # 3. Test "refresh anyway"
        query3 = "Just refresh anyway ok"
        query3_hash = hashlib.sha256(query3.encode()).hexdigest()[:16]
        identity["last_successful_run"]["query_hash"] = query3_hash
        assert check_groundhog_day(query3, identity) is None
        
        # 4. Control: Same setup WITHOUT token should trigger
        query_control = "Run backup normally"
        query_control_hash = hashlib.sha256(query_control.encode()).hexdigest()[:16]
        identity["last_successful_run"]["query_hash"] = query_control_hash
        
        result_control = check_groundhog_day(query_control, identity)
        assert result_control is not None # Should trigger



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
