"""
CommitGate Tests for DTL v2.0

Branch coverage tests to lock in P0 fixes:
- Full bundle hash (not just payload)
- Prewrite token verification
- Timezone handling
- JSON pointer error format
- All 7 validation checks
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.control_plane.commit_gate import (
    CommitGate, 
    CommitBundle, 
    CommitStatus,
    RejectionPayload,
    PromoteStatus,
    PromoteResult
)


class TestCommitBundle:
    """Tests for CommitBundle dataclass."""
    
    def test_compute_hash_covers_full_bundle(self):
        """P0 Fix #2: Hash must cover full bundle, not just payload."""
        bundle = CommitBundle(
            run_id='TEST-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'test': 'data'},
            evidence_refs=['EV-123'],
            capability_claims=['read']
        )
        hash1 = bundle.compute_hash()
        
        # Change only metadata - hash MUST change
        bundle.evidence_refs = ['EV-456']
        hash2 = bundle.compute_hash()
        
        assert hash1 != hash2, "Hash must change when evidence_refs changes"
    
    def test_compute_hash_covers_capability_claims(self):
        """Hash must include capability claims."""
        bundle = CommitBundle(
            run_id='TEST-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'test': 'data'},
        )
        hash1 = bundle.compute_hash()
        
        bundle.capability_claims = ['write', 'execute']
        hash2 = bundle.compute_hash()
        
        assert hash1 != hash2, "Hash must change when capability_claims changes"
    
    def test_compute_hash_covers_agent_id(self):
        """Hash must include agent_id."""
        bundle = CommitBundle(
            run_id='TEST-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'test': 'data'},
        )
        hash1 = bundle.compute_hash()
        
        bundle.agent_id = 'malicious-v0.1'
        hash2 = bundle.compute_hash()
        
        assert hash1 != hash2, "Hash must change when agent_id changes"
    
    def test_compute_hash_is_deterministic(self):
        """Same bundle must produce same hash."""
        bundle1 = CommitBundle(
            run_id='TEST-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'a': 1, 'b': 2},
            evidence_refs=['EV-AAA', 'EV-BBB'],
        )
        bundle2 = CommitBundle(
            run_id='TEST-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'b': 2, 'a': 1},  # Different order
            evidence_refs=['EV-BBB', 'EV-AAA'],  # Different order
        )
        
        assert bundle1.compute_hash() == bundle2.compute_hash(), \
            "Hash must be deterministic (order-independent)"


class TestCommitGateValidation:
    """Tests for CommitGate validation checks."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        base = tempfile.mkdtemp()
        evidence_store = Path(base) / "evidence_store"
        prewrite_path = Path(base) / "prewrite"
        evidence_store.mkdir()
        prewrite_path.mkdir()
        yield evidence_store, prewrite_path
        shutil.rmtree(base)
    
    @pytest.fixture
    def gate(self, temp_dirs):
        """Create CommitGate with temp paths."""
        evidence_store, prewrite_path = temp_dirs
        return CommitGate(
            evidence_store_path=str(evidence_store),
            prewrite_path=str(prewrite_path),
            evidence_ttl_seconds=3600
        )
    
    @pytest.fixture
    def valid_bundle(self):
        """Create a valid bundle for testing."""
        bundle = CommitBundle(
            run_id='TEST-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'test': 'data'},
        )
        bundle.content_hash = bundle.compute_hash()
        return bundle
    
    def test_check_hash_accepts_valid(self, gate, valid_bundle):
        """Check 2: Valid hash passes."""
        result = gate._check_hash(valid_bundle)
        assert result is None
    
    def test_check_hash_rejects_mismatch(self, gate, valid_bundle):
        """Check 2: Mismatched hash is rejected."""
        valid_bundle.content_hash = 'sha256:wronghash'
        result = gate._check_hash(valid_bundle)
        
        assert result is not None
        assert result.code == CommitGate.HASH_MISMATCH
    
    def test_check_evidence_exists_accepts_present(self, gate, valid_bundle, temp_dirs):
        """Check 3: Present evidence passes."""
        evidence_store, _ = temp_dirs
        
        # Create evidence file
        ev_id = 'EV-ABCD12345678'
        valid_bundle.evidence_refs = [ev_id]
        ev_file = evidence_store / f"{ev_id}.json"
        ev_file.write_text(json.dumps({
            "evidence_id": ev_id,
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }))
        
        result = gate._check_evidence_exists(valid_bundle)
        assert result is None
    
    def test_check_evidence_exists_rejects_missing(self, gate, valid_bundle):
        """Check 3: Missing evidence is rejected."""
        valid_bundle.evidence_refs = ['EV-DOESNOTEXIST']
        
        result = gate._check_evidence_exists(valid_bundle)
        
        assert result is not None
        assert result.code == CommitGate.EVIDENCE_MISSING
        assert 'EV-DOESNOTEXIST' in result.evidence_ids
    
    def test_check_evidence_freshness_accepts_fresh(self, gate, valid_bundle, temp_dirs):
        """Check 4: Fresh evidence passes."""
        evidence_store, _ = temp_dirs
        
        ev_id = 'EV-FRESH1234567'
        valid_bundle.evidence_refs = [ev_id]
        ev_file = evidence_store / f"{ev_id}.json"
        ev_file.write_text(json.dumps({
            "evidence_id": ev_id,
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }))
        
        result = gate._check_evidence_freshness(valid_bundle)
        assert result is None
    
    def test_check_evidence_freshness_rejects_stale(self, gate, valid_bundle, temp_dirs):
        """Check 4: Stale evidence is rejected."""
        evidence_store, _ = temp_dirs
        
        ev_id = 'EV-STALE1234567'
        valid_bundle.evidence_refs = [ev_id]
        ev_file = evidence_store / f"{ev_id}.json"
        
        # Evidence from 8 days ago (TTL is 1 hour in fixture)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        ev_file.write_text(json.dumps({
            "evidence_id": ev_id,
            "fetched_at": old_time
        }))
        
        result = gate._check_evidence_freshness(valid_bundle)
        
        assert result is not None
        assert result.code == CommitGate.EVIDENCE_STALE
    
    def test_check_evidence_freshness_rejects_invalid_timezone(self, gate, valid_bundle, temp_dirs):
        """P0 Fix #4: Missing timezone is EVIDENCE_INVALID_TIMESTAMP, not stale."""
        evidence_store, _ = temp_dirs
        
        ev_id = 'EV-NOTZ12345678'
        valid_bundle.evidence_refs = [ev_id]
        ev_file = evidence_store / f"{ev_id}.json"
        
        # Naive datetime (no timezone)
        ev_file.write_text(json.dumps({
            "evidence_id": ev_id,
            "fetched_at": "2025-12-26T00:00:00"  # No Z or offset
        }))
        
        result = gate._check_evidence_freshness(valid_bundle)
        
        assert result is not None
        assert result.code == CommitGate.EVIDENCE_INVALID_TIMESTAMP
    
    def test_check_evidence_freshness_accepts_z_suffix(self, gate, valid_bundle, temp_dirs):
        """P0 Fix #4: Z suffix is valid timezone."""
        evidence_store, _ = temp_dirs
        
        ev_id = 'EV-ZULU12345678'
        valid_bundle.evidence_refs = [ev_id]
        ev_file = evidence_store / f"{ev_id}.json"
        ev_file.write_text(json.dumps({
            "evidence_id": ev_id,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }))
        
        result = gate._check_evidence_freshness(valid_bundle)
        assert result is None
    
    def test_check_capabilities_accepts_allowed(self, gate, valid_bundle):
        """Check 5: Allowed capabilities pass."""
        valid_bundle.capability_claims = ['read', 'analyze']
        
        result = gate._check_capabilities(valid_bundle, allowed=['read', 'analyze', 'write'])
        assert result is None
    
    def test_check_capabilities_rejects_unauthorized(self, gate, valid_bundle):
        """Check 5: Unauthorized capabilities are rejected."""
        valid_bundle.capability_claims = ['read', 'execute']
        
        result = gate._check_capabilities(valid_bundle, allowed=['read', 'analyze'])
        
        assert result is not None
        assert result.code == CommitGate.CAPABILITY_DENIED
    
    def test_check_kill_switches_blocks_disable_writes(self, gate, valid_bundle):
        """Check 6: DISABLE_WRITES blocks all commits."""
        result = gate._check_kill_switches(valid_bundle, ['DISABLE_WRITES'])
        
        assert result is not None
        assert result.code == CommitGate.KILL_SWITCH_BLOCKED
        assert result.kill_switch == 'DISABLE_WRITES'
    
    def test_check_kill_switches_blocks_learning_caps(self, gate, valid_bundle):
        """Check 6: DISABLE_LEARNING blocks learning capabilities."""
        valid_bundle.capability_claims = ['routing_statistics_write']
        
        result = gate._check_kill_switches(valid_bundle, ['DISABLE_LEARNING'])
        
        assert result is not None
        assert result.code == CommitGate.KILL_SWITCH_BLOCKED
        assert result.kill_switch == 'DISABLE_LEARNING'
    
    def test_check_prewrite_accepts_matching(self, gate, valid_bundle, temp_dirs):
        """Check 7: Matching prewrite passes."""
        _, prewrite_path = temp_dirs
        
        # Create prewrite with correct hash
        gate.create_prewrite(valid_bundle)
        
        result = gate._check_prewrite(valid_bundle)
        assert result is None
    
    def test_check_prewrite_rejects_missing(self, gate, valid_bundle):
        """Check 7: Missing prewrite is rejected."""
        result = gate._check_prewrite(valid_bundle)
        
        assert result is not None
        assert result.code == CommitGate.PREWRITE_MISSING
    
    def test_check_prewrite_rejects_hash_mismatch(self, gate, valid_bundle, temp_dirs):
        """P0 Fix #3: Prewrite hash must match full bundle hash."""
        _, prewrite_path = temp_dirs
        
        # Create prewrite
        gate.create_prewrite(valid_bundle)
        
        # Modify bundle after prewrite
        valid_bundle.evidence_refs = ['EV-MODIFIED123']
        valid_bundle.content_hash = valid_bundle.compute_hash()
        
        result = gate._check_prewrite(valid_bundle)
        
        assert result is not None
        assert result.code == CommitGate.HASH_MISMATCH
    
    def test_full_validation_happy_path(self, gate, valid_bundle, temp_dirs):
        """Full validation with all checks passing."""
        # Create prewrite
        gate.create_prewrite(valid_bundle)
        
        result = gate.validate(valid_bundle)
        
        assert result.status == CommitStatus.ACCEPTED
        assert result.rejection is None


class TestPromoteResult:
    """Tests for promote_to_committed."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        base = tempfile.mkdtemp()
        prewrite_path = Path(base) / "prewrite"
        prewrite_path.mkdir()
        yield prewrite_path
        shutil.rmtree(base)
    
    @pytest.fixture
    def gate(self, temp_dirs):
        """Create CommitGate with temp paths."""
        return CommitGate(
            evidence_store_path=str(temp_dirs / "evidence"),
            prewrite_path=str(temp_dirs)
        )
    
    @pytest.fixture
    def bundle(self):
        """Create test bundle."""
        bundle = CommitBundle(
            run_id='TEST-PROMOTE',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T00:00:00Z',
            content_hash='placeholder',
            payload={'test': 'data'},
        )
        bundle.content_hash = bundle.compute_hash()
        return bundle
    
    def test_promote_success(self, gate, bundle, temp_dirs):
        """P1 Fix #9: Successful promotion returns SUCCESS."""
        gate.create_prewrite(bundle)
        
        result = gate.promote_to_committed(bundle)
        
        assert result.status == PromoteStatus.SUCCESS
        assert result.success is True
        assert result.path is not None
        assert result.path.exists()
    
    def test_promote_already_committed(self, gate, bundle, temp_dirs):
        """P1 Fix #9: Already committed returns ALREADY_COMMITTED."""
        gate.create_prewrite(bundle)
        
        # Promote once
        gate.promote_to_committed(bundle)
        
        # Try to promote again
        result = gate.promote_to_committed(bundle)
        
        assert result.status == PromoteStatus.ALREADY_COMMITTED
        assert result.success is False
    
    def test_promote_prewrite_not_found(self, gate, bundle):
        """P1 Fix #9: Missing prewrite returns PREWRITE_NOT_FOUND."""
        result = gate.promote_to_committed(bundle)
        
        assert result.status == PromoteStatus.PREWRITE_NOT_FOUND
        assert result.success is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
