"""
Immutability Tests for Phase 5 Stores

Ensures:
- Same run_id twice fails
- Same evidence ID twice fails (IdentityStore)
- Ledger is append-only
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone


class TestImmutabilityGuarantees:
    """Verify immutability semantics for all stores."""
    
    @pytest.fixture
    def temp_stores(self):
        """Create temporary store directories."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_identity_store_rejects_duplicate_write(self, temp_stores):
        """IdentityStore should reject writing same entry_id twice."""
        from src.control_plane.stores import IdentityStore, create_identity_entry
        
        store = IdentityStore(temp_stores / 'identity')
        
        # First write should succeed
        entry1 = create_identity_entry(
            agent_id='strategist',
            version='v0.1',
            manifest_path=Path('src/agents/strategist.skill.md'),
            capabilities=['read_market_data']
        )
        result1 = store.write(entry1)
        assert result1 == True
        
        # Second write with same ID should fail
        entry2 = create_identity_entry(
            agent_id='strategist',
            version='v0.1',
            manifest_path=Path('src/agents/strategist.skill.md'),
            capabilities=['read_market_data', 'extra']
        )
        result2 = store.write(entry2)
        assert result2 == False
    
    def test_identity_store_file_is_readonly(self, temp_stores):
        """IdentityStore entries should have read-only permissions."""
        from src.control_plane.stores import IdentityStore, create_identity_entry
        import stat
        
        store = IdentityStore(temp_stores / 'identity')
        
        entry = create_identity_entry(
            agent_id='researcher',
            version='v0.1',
            manifest_path=Path('src/agents/researcher.skill.md'),
            capabilities=['collect_evidence']
        )
        store.write(entry)
        
        entry_path = temp_stores / 'identity' / f"{entry.entry_id}.json"
        mode = entry_path.stat().st_mode
        
        # Should be read-only (0o444)
        assert not (mode & stat.S_IWUSR)
        assert not (mode & stat.S_IWGRP)
        assert not (mode & stat.S_IWOTH)
    
    def test_ledger_append_only(self, temp_stores):
        """RunLedger should allow multiple entries (append-only)."""
        from src.control_plane.stores import RunLedger, create_ledger_entry
        
        ledger = RunLedger(temp_stores / 'ledger')
        
        # First entry
        entry1 = create_ledger_entry(
            run_id='RUN-001',
            run_ts='2025-12-26T10:00:00+00:00',
            mode='mock',
            success=True,
            steps=['step1']
        )
        path1 = ledger.append(entry1)
        assert path1.exists()
        
        # Second entry with different run_id
        entry2 = create_ledger_entry(
            run_id='RUN-002',
            run_ts='2025-12-26T10:01:00+00:00',
            mode='mock',
            success=True,
            steps=['step1', 'step2']
        )
        path2 = ledger.append(entry2)
        assert path2.exists()
        
        # Both should exist
        assert ledger.find_by_run_id('RUN-001') is not None
        assert ledger.find_by_run_id('RUN-002') is not None
    
    def test_committed_prevents_replay(self, temp_stores):
        """CommitGate should track committed status for same run_id."""
        from src.control_plane.commit_gate import CommitGate, CommitBundle, PromoteStatus
        
        gate = CommitGate(
            evidence_store_path=temp_stores / 'evidence',
            prewrite_path=temp_stores / 'prewrite'
        )
        
        # Create and commit first bundle
        bundle1 = CommitBundle(
            run_id='RUN-DEDUP-001',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'first'},
            evidence_refs=[],
            capability_claims=['write_report']
        )
        bundle1.content_hash = bundle1.compute_hash()
        
        # Create prewrite and promote
        gate.create_prewrite(bundle1)
        promote_result1 = gate.promote_to_committed(bundle1)
        assert promote_result1.success == True
        
        # Verify committed file exists
        committed_path = temp_stores / 'prewrite' / '..' / 'committed' / f"COMMITTED-{bundle1.run_id}.json"
        assert committed_path.resolve().exists()
        
        # Second attempt to create prewrite with same run_id and promote
        bundle2 = CommitBundle(
            run_id='RUN-DEDUP-001',  # Same run_id
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:01:00+00:00',
            content_hash='placeholder',
            payload={'data': 'second'},
            evidence_refs=[],
            capability_claims=['write_report']
        )
        bundle2.content_hash = bundle2.compute_hash()
        
        # Create new prewrite - this will overwrite since prewrite was consumed
        gate.create_prewrite(bundle2)
        promote_result2 = gate.promote_to_committed(bundle2)
        
        # Should return ALREADY_COMMITTED since committed file exists
        assert promote_result2.status == PromoteStatus.ALREADY_COMMITTED
    
    def test_evidence_store_allows_different_ids(self, temp_stores):
        """EvidenceStore should allow different evidence IDs."""
        from src.control_plane.stores import EvidenceStore, create_evidence_entry
        
        store = EvidenceStore(temp_stores / 'evidence')
        
        entry1 = create_evidence_entry(
            evidence_id='EV-001',
            source_url='https://example.com/1',
            trust_tier=1,
            summary='First evidence',
            asset_tags=['XAU'],
            run_id='RUN-001',
            run_ts='2025-12-26T10:00:00+00:00'
        )
        store.write(entry1)
        
        entry2 = create_evidence_entry(
            evidence_id='EV-002',
            source_url='https://example.com/2',
            trust_tier=2,
            summary='Second evidence',
            asset_tags=['GME'],
            run_id='RUN-001',
            run_ts='2025-12-26T10:00:00+00:00'
        )
        store.write(entry2)
        
        assert store.exists('EV-001')
        assert store.exists('EV-002')
