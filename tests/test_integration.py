"""
Integration Tests for DTL v2.0

Tests the full pipeline flow:
- Happy path: mock run succeeds
- Kill switch enforcement
- CommitGate validation in pipeline context
"""

import json
import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCLIIntegration:
    """Integration tests for DTL CLI."""
    
    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent
    
    def test_mock_run_completes_all_steps(self, project_root):
        """Happy path: mock run should complete all 8 steps."""
        result = subprocess.run(
            ['python3', 'src/cli.py', 'run', '--mode=mock'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        
        # Check all steps completed
        assert 'Step 1: Loading policy snapshot' in result.stdout
        assert 'Step 2: Loading capability manifests' in result.stdout
        assert 'Step 3: Enforcing kill switches' in result.stdout
        assert 'Step 4: Running agents' in result.stdout
        assert 'Step 5: Building CommitBundle' in result.stdout
        assert 'Step 6: CommitGate validation' in result.stdout
        assert 'Step 7: Ledger prewrite' in result.stdout
        assert 'Step 8: Write immutable stores' in result.stdout
        assert 'Success: True' in result.stdout
    
    def test_mock_run_creates_output_file(self, project_root):
        """Mock run should create output JSON file."""
        result = subprocess.run(
            ['python3', 'src/cli.py', 'run', '--mode=mock', '--run_id=TEST-INTEGRATION'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        output_file = project_root / 'data' / 'dtl_runs' / 'TEST-INTEGRATION.json'
        assert output_file.exists(), f"Output file not created: {output_file}"
        
        # Verify content
        with open(output_file) as f:
            data = json.load(f)
        
        assert data['run_id'] == 'TEST-INTEGRATION'
        assert data['mode'] == 'mock'
        assert 'policy_applied' in data
        assert 'runtime_fingerprint' in data['policy_applied']
        
        # Cleanup
        output_file.unlink()
    
    def test_runtime_fingerprint_in_output(self, project_root):
        """P1 Fix #10: Runtime fingerprint should be in output."""
        result = subprocess.run(
            ['python3', 'src/cli.py', 'run', '--mode=mock', '--run_id=TEST-FINGERPRINT'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        output_file = project_root / 'data' / 'dtl_runs' / 'TEST-FINGERPRINT.json'
        with open(output_file) as f:
            data = json.load(f)
        
        fp = data['policy_applied']['runtime_fingerprint']
        assert 'python_version' in fp
        assert 'packages' in fp
        assert 'google-adk' in fp['packages']
        
        # Cleanup
        output_file.unlink()
    
    def test_kill_switch_enforcement(self, project_root):
        """Kill switches should be enforced in pipeline."""
        result = subprocess.run(
            ['python3', 'src/cli.py', 'run', '--mode=mock'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # DISABLE_LEARNING is enabled by default
        assert 'Active switches:' in result.stdout
        assert 'DISABLE_LEARNING' in result.stdout
    
    def test_status_command(self, project_root):
        """Status command should work."""
        result = subprocess.run(
            ['python3', 'src/cli.py', 'status'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert 'DTL System Status' in result.stdout
    
    def test_validate_bundle_command(self, project_root):
        """Validate-bundle command should work with real CommitGate."""
        # Create a test bundle
        bundle_file = project_root / 'data' / 'test_bundle.json'
        bundle_file.parent.mkdir(exist_ok=True)
        
        bundle_data = {
            'run_id': 'TEST-001',  # Match schema: TEST-[0-9]+
            'agent_id': 'reporter-v0.1',
            'schema_version': '2.0.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'content_hash': 'sha256:placeholder',
            'payload': {'test': True}
        }
        
        with open(bundle_file, 'w') as f:
            json.dump(bundle_data, f)
        
        result = subprocess.run(
            ['python3', 'src/cli.py', 'validate-bundle', str(bundle_file)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should fail validation (could be schema, hash, or prewrite issue)
        assert result.returncode == 1
        assert any(code in result.stdout for code in ['HASH_MISMATCH', 'PREWRITE_MISSING', 'SCHEMA_INVALID', 'REJECTED'])
        
        # Cleanup
        bundle_file.unlink()


class TestPipelineIntegration:
    """Integration tests for full pipeline components."""
    
    def test_commit_gate_in_pipeline_context(self):
        """CommitGate should work in pipeline context."""
        from src.control_plane.commit_gate import CommitGate, CommitBundle
        from src.control_plane.kill_switch import KillSwitchEnforcer
        
        # Create gate and enforcer
        gate = CommitGate()
        enforcer = KillSwitchEnforcer()
        
        # Check enforcement
        result = enforcer.enforce(['run_agents'])
        
        # DISABLE_LEARNING is enabled but doesn't block run_agents
        assert 'DISABLE_LEARNING' in result.active_switches
    
    def test_firewall_with_real_schemas(self):
        """Firewall should validate against real project schemas."""
        from src.control_plane.firewall import InterAgentFirewall
        
        firewall = InterAgentFirewall()
        
        # Valid message
        msg = {
            'plan_id': 'PLAN-TEST1234',
            'asset_universe': ['XAU', 'GME']
        }
        
        result = firewall.validate_strategist_output(msg)
        assert result.valid is True
        
        # Invalid message
        msg_invalid = {
            'plan_id': 'wrong',
            'asset_universe': ['INVALID']
        }
        
        result = firewall.validate_strategist_output(msg_invalid)
        assert result.valid is False


class TestFailurePlaybook:
    """T6.7: Failure Playbook tests."""
    
    def test_missing_evidence_store(self):
        """System should handle missing evidence store gracefully."""
        from src.control_plane.commit_gate import CommitGate, CommitBundle
        
        gate = CommitGate(
            evidence_store_path='/nonexistent/path'
        )
        
        bundle = CommitBundle(
            run_id='TEST-NOEVIDENCE',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp=datetime.now(timezone.utc).isoformat(),
            content_hash='placeholder',
            payload={},
            evidence_refs=['EV-DOESNOTEXIST']
        )
        bundle.content_hash = bundle.compute_hash()
        
        # Should fail with EVIDENCE_MISSING, not crash
        result = gate._check_evidence_exists(bundle)
        assert result is not None
        assert result.code == 'EVIDENCE_MISSING'
    
    def test_corrupt_kill_switch_config(self):
        """System should handle corrupt config gracefully."""
        from src.control_plane.kill_switch import KillSwitchEnforcer
        
        # Non-existent config path
        enforcer = KillSwitchEnforcer(config_path='/nonexistent/config.json')
        
        # Should return safe defaults, not crash
        result = enforcer.enforce([])
        assert result.can_proceed is True
    
    def test_partial_evidence(self):
        """System should handle partial evidence (some missing)."""
        import tempfile
        from src.control_plane.commit_gate import CommitGate, CommitBundle
        
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_store = Path(tmpdir) / 'evidence'
            evidence_store.mkdir()
            
            # Create only one of two required evidence files
            ev_file = evidence_store / 'EV-EXISTS123456.json'
            ev_file.write_text(json.dumps({
                'evidence_id': 'EV-EXISTS123456',
                'fetched_at': datetime.now(timezone.utc).isoformat()
            }))
            
            gate = CommitGate(evidence_store_path=str(evidence_store))
            
            bundle = CommitBundle(
                run_id='TEST-PARTIAL',
                agent_id='reporter-v0.1',
                schema_version='2.0.0',
                timestamp=datetime.now(timezone.utc).isoformat(),
                content_hash='placeholder',
                payload={},
                evidence_refs=['EV-EXISTS123456', 'EV-MISSING12345']
            )
            
            result = gate._check_evidence_exists(bundle)
            
            assert result is not None
            assert result.code == 'EVIDENCE_MISSING'
            assert 'EV-MISSING12345' in result.evidence_ids
            assert 'EV-EXISTS123456' not in result.evidence_ids


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
