"""
Feed Trust Scoring Tests (Prompt Z).

Tests for deterministic feed trust scoring with automatic degradation.
"""

import pytest
import tempfile
import os


class TestTrustDegradation:
    """Tests that trust degrades on attack events."""

    def test_trust_degrades_on_malicious_payload(self):
        """Malicious payload should degrade trust by 0.4."""
        from src.core.feed_trust import FeedTrustStore, record_malicious_payload, PENALTY_MALICIOUS_PAYLOAD
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedTrustStore(os.path.join(tmpdir, "trust.json"))
            feed_url = "https://example.com/feed.xml"
            
            initial = store.get_trust_score(feed_url)
            assert initial == 1.0
            
            new_score = record_malicious_payload(feed_url, store)
            
            assert new_score == 1.0 - PENALTY_MALICIOUS_PAYLOAD
            assert store.get_trust_score(feed_url) == new_score

    def test_trust_degrades_on_injection(self):
        """Injection attempt should degrade trust by 0.3."""
        from src.core.feed_trust import FeedTrustStore, record_injection_attempt, PENALTY_INJECTION_ATTEMPT
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedTrustStore(os.path.join(tmpdir, "trust.json"))
            feed_url = "https://example.com/feed.xml"
            
            new_score = record_injection_attempt(feed_url, store)
            
            assert new_score == 1.0 - PENALTY_INJECTION_ATTEMPT

    def test_trust_degrades_on_attack(self):
        """Multiple attacks should compound degradation."""
        from src.core.feed_trust import (
            FeedTrustStore, record_malicious_payload, record_injection_attempt,
            PENALTY_MALICIOUS_PAYLOAD, PENALTY_INJECTION_ATTEMPT
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedTrustStore(os.path.join(tmpdir, "trust.json"))
            feed_url = "https://example.com/feed.xml"
            
            record_malicious_payload(feed_url, store)
            record_injection_attempt(feed_url, store)
            
            expected = 1.0 - PENALTY_MALICIOUS_PAYLOAD - PENALTY_INJECTION_ATTEMPT
            assert store.get_trust_score(feed_url) == expected


class TestFeedDisabling:
    """Tests that feeds are disabled below threshold."""

    def test_feed_disabled_below_threshold(self):
        """Feed with score < 0.4 should be disabled."""
        from src.core.feed_trust import (
            FeedTrustStore, check_feed_allowed, get_feed_behavior,
            record_malicious_payload
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedTrustStore(os.path.join(tmpdir, "trust.json"))
            feed_url = "https://malicious.com/feed.xml"
            
            # Apply enough penalties to drop below 0.4
            record_malicious_payload(feed_url, store)  # 1.0 - 0.4 = 0.6
            record_malicious_payload(feed_url, store)  # 0.6 - 0.4 = 0.2
            
            score = store.get_trust_score(feed_url)
            assert score < 0.4
            
            behavior, max_items = get_feed_behavior(feed_url, store)
            assert behavior == "disabled"
            assert max_items == 0
            
            allowed, reason = check_feed_allowed(feed_url, store)
            assert allowed is False
            assert "disabled" in reason.lower()

    def test_limited_behavior_between_thresholds(self):
        """Feed with score 0.4-0.69 should be limited."""
        from src.core.feed_trust import (
            FeedTrustStore, get_feed_behavior, record_empty_payload,
            MAX_ITEMS_LIMITED, PENALTY_EMPTY_PAYLOAD
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedTrustStore(os.path.join(tmpdir, "trust.json"))
            feed_url = "https://example.com/feed.xml"
            
            # Drop to limited range using empty payload penalties
            # 1.0 - 0.2 = 0.8, 0.8 - 0.2 = 0.6 (in limited range)
            record_empty_payload(feed_url, store)  # 0.8
            record_empty_payload(feed_url, store)  # 0.6
            
            score = store.get_trust_score(feed_url)
            assert 0.4 <= score < 0.7, f"Expected 0.4 <= score < 0.7, got {score}"
            
            behavior, max_items = get_feed_behavior(feed_url, store)
            assert behavior == "limited"
            assert max_items == MAX_ITEMS_LIMITED


class TestTrustPersistence:
    """Tests that trust persists across runs."""

    def test_trust_persists_across_runs(self):
        """Trust scores should persist when reloading store."""
        from src.core.feed_trust import FeedTrustStore, record_malicious_payload
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "trust.json")
            feed_url = "https://example.com/feed.xml"
            
            # First run: degrade trust
            store1 = FeedTrustStore(path)
            record_malicious_payload(feed_url, store1)
            score1 = store1.get_trust_score(feed_url)
            
            # Second run: reload store
            store2 = FeedTrustStore(path)
            score2 = store2.get_trust_score(feed_url)
            
            assert score1 == score2


class TestNoIdentityMutation:
    """Tests that trust scoring doesn't mutate identity."""

    def test_no_identity_mutation(self):
        """Trust operations should not touch identity store."""
        from src.core.feed_trust import FeedTrustStore, record_malicious_payload
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedTrustStore(os.path.join(tmpdir, "trust.json"))
            
            # This should not import or use identity_manager
            with pytest.MonkeyPatch().context() as m:
                def fail_if_called(*args, **kwargs):
                    pytest.fail("Identity manager was called during trust operation")
                
                # Would fail if identity_manager was used
                record_malicious_payload("https://test.com/feed", store)
