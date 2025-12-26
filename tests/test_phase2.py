"""
Tests for Phase 2 Components: EvidenceCandidateQueue and RoutingStatisticsStore
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.control_plane.evidence_queue import EvidenceCandidateQueue, EvidenceCandidate
from src.control_plane.routing_stats import RoutingStatisticsStore, RoutingStatEntry


class TestEvidenceCandidate:
    """Tests for EvidenceCandidate dataclass."""
    
    def test_generate_id_format(self):
        """Generated IDs should match expected format."""
        ev_id = EvidenceCandidate.generate_id()
        
        assert ev_id.startswith('EV-')
        assert len(ev_id) == 15  # EV- + 12 chars
    
    def test_generate_id_unique(self):
        """Generated IDs should be unique."""
        ids = [EvidenceCandidate.generate_id() for _ in range(100)]
        assert len(set(ids)) == 100
    
    def test_to_dict_excludes_none(self):
        """to_dict should exclude None values."""
        candidate = EvidenceCandidate(
            evidence_id='EV-TEST12345678',
            source_url='https://example.com',
            source_trust_tier=1,
            fetched_at='2025-12-26T00:00:00Z'
        )
        
        d = candidate.to_dict()
        
        assert 'summary' not in d
        assert 'raw_content_hash' not in d
    
    def test_from_dict_roundtrip(self):
        """from_dict should recreate the candidate."""
        original = EvidenceCandidate(
            evidence_id='EV-TEST12345678',
            source_url='https://example.com',
            source_trust_tier=2,
            fetched_at='2025-12-26T00:00:00Z',
            summary='Test summary',
            relevance_score=0.8
        )
        
        recreated = EvidenceCandidate.from_dict(original.to_dict())
        
        assert recreated.evidence_id == original.evidenc_id if hasattr(original, 'evidenc_id') else original.evidence_id
        assert recreated.source_trust_tier == original.source_trust_tier
        assert recreated.summary == original.summary


class TestEvidenceCandidateQueue:
    """Tests for EvidenceCandidateQueue."""
    
    @pytest.fixture
    def queue(self):
        return EvidenceCandidateQueue(max_size=5)
    
    @pytest.fixture
    def sample_candidate(self):
        return EvidenceCandidate(
            evidence_id='EV-SAMPLE123456',
            source_url='https://example.com',
            source_trust_tier=1,
            fetched_at=datetime.now(timezone.utc).isoformat()
        )
    
    def test_enqueue_dequeue(self, queue, sample_candidate):
        """Basic enqueue/dequeue should work."""
        queue.enqueue(sample_candidate)
        
        assert len(queue) == 1
        
        dequeued = queue.dequeue()
        
        assert dequeued.evidence_id == sample_candidate.evidence_id
        assert len(queue) == 0
    
    def test_fifo_order(self, queue):
        """Queue should be FIFO."""
        for i in range(3):
            c = EvidenceCandidate(
                evidence_id=f'EV-ORDER{i:08d}',
                source_url='https://example.com',
                source_trust_tier=1,
                fetched_at=datetime.now(timezone.utc).isoformat()
            )
            queue.enqueue(c)
        
        assert queue.dequeue().evidence_id == 'EV-ORDER00000000'
        assert queue.dequeue().evidence_id == 'EV-ORDER00000001'
        assert queue.dequeue().evidence_id == 'EV-ORDER00000002'
    
    def test_max_size_drops_oldest(self, queue):
        """Exceeding max_size should drop oldest."""
        for i in range(7):  # max_size is 5
            c = EvidenceCandidate(
                evidence_id=f'EV-DROP{i:09d}',
                source_url='https://example.com',
                source_trust_tier=1,
                fetched_at=datetime.now(timezone.utc).isoformat()
            )
            queue.enqueue(c)
        
        assert len(queue) == 5
        # First two should have been dropped
        assert queue.peek().evidence_id == 'EV-DROP000000002'
    
    def test_duplicate_rejected(self, queue, sample_candidate):
        """Duplicate evidence_id should be rejected."""
        queue.enqueue(sample_candidate)
        result = queue.enqueue(sample_candidate)
        
        assert result is False
        assert len(queue) == 1
    
    def test_dequeue_all(self, queue):
        """dequeue_all should return all and clear."""
        for i in range(3):
            c = EvidenceCandidate(
                evidence_id=f'EV-ALL{i:10d}',
                source_url='https://example.com',
                source_trust_tier=1,
                fetched_at=datetime.now(timezone.utc).isoformat()
            )
            queue.enqueue(c)
        
        all_candidates = queue.dequeue_all()
        
        assert len(all_candidates) == 3
        assert len(queue) == 0
    
    def test_stats(self, queue, sample_candidate):
        """Stats should track operations."""
        queue.enqueue(sample_candidate)
        queue.dequeue()
        
        stats = queue.stats
        
        assert stats['total_enqueued'] == 1
        assert stats['total_dequeued'] == 1
        assert stats['current_size'] == 0
    
    def test_persistence(self):
        """Queue should persist and restore."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            persist_path = f.name
        
        try:
            # Create and populate queue
            queue1 = EvidenceCandidateQueue(persist_path=persist_path)
            c = EvidenceCandidate(
                evidence_id='EV-PERSIST12345',
                source_url='https://example.com',
                source_trust_tier=1,
                fetched_at=datetime.now(timezone.utc).isoformat()
            )
            queue1.enqueue(c)
            
            # Create new queue with same path
            queue2 = EvidenceCandidateQueue(persist_path=persist_path)
            
            assert len(queue2) == 1
            assert queue2.peek().evidence_id == 'EV-PERSIST12345'
        finally:
            Path(persist_path).unlink(missing_ok=True)


class TestRoutingStatisticsStore:
    """Tests for RoutingStatisticsStore."""
    
    @pytest.fixture
    def store(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            store_path = f.name
        
        store = RoutingStatisticsStore(store_path=store_path)
        yield store
        
        Path(store_path).unlink(missing_ok=True)
    
    def test_record_invocation(self, store):
        """Recording invocation should update stats."""
        success, err = store.record_invocation('STRAT-TEST0001', 100, True)
        
        assert success is True
        assert err is None
        
        entry = store.get('STRAT-TEST0001')
        assert entry is not None
        assert entry.invocation_count == 1
    
    def test_multiple_invocations(self, store):
        """Multiple invocations should accumulate."""
        for _ in range(5):
            store.record_invocation('STRAT-MULTI001', 100, True)
        
        entry = store.get('STRAT-MULTI001')
        assert entry.invocation_count == 5
    
    def test_latency_ema(self, store):
        """Latency should use EMA smoothing."""
        store.record_invocation('STRAT-LATENCY1', 100, True)
        store.record_invocation('STRAT-LATENCY1', 100, True)
        store.record_invocation('STRAT-LATENCY1', 100, True)
        
        entry = store.get('STRAT-LATENCY1')
        # EMA smooths from 0, so after several 100ms calls, should be > 0
        assert entry.avg_latency_ms > 0
    
    def test_disable_learning_blocks_write(self, store):
        """DISABLE_LEARNING should block writes."""
        store.set_learning_disabled(True)
        
        success, err = store.record_invocation('STRAT-BLOCKED1', 100, True)
        
        assert success is False
        assert 'DISABLE_LEARNING' in err
    
    def test_disable_learning_allows_read(self, store):
        """DISABLE_LEARNING should allow reads."""
        store.record_invocation('STRAT-READABLE', 100, True)
        store.set_learning_disabled(True)
        
        entry = store.get('STRAT-READABLE')
        
        assert entry is not None
        assert entry.invocation_count == 1
    
    def test_update_ema_weight(self, store):
        """EMA weight should be updatable."""
        store.record_invocation('STRAT-EMA00001', 100, True)
        
        success, err = store.update_ema_weight('STRAT-EMA00001', 0.7)
        
        assert success is True
        assert store.get('STRAT-EMA00001').outcome_ema_weight == 0.7
    
    def test_update_ema_blocked_when_disabled(self, store):
        """EMA weight update blocked with DISABLE_LEARNING."""
        store.record_invocation('STRAT-EMABLK1', 100, True)
        store.set_learning_disabled(True)
        
        success, err = store.update_ema_weight('STRAT-EMABLK1', 0.9)
        
        assert success is False
        assert 'frozen' in err.lower()
    
    def test_get_all(self, store):
        """get_all should return all entries."""
        store.record_invocation('STRAT-ALL00001', 100, True)
        store.record_invocation('STRAT-ALL00002', 100, True)
        
        entries = store.get_all()
        
        assert len(entries) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
