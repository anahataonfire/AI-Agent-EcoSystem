"""
Phase 6 Tests: DEGRADED_MODE Trigger and Adversarial Injection

T6.5: Integration test for DEGRADED_MODE trigger
T6.6: Adversarial test for injection attempts
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone


class TestDegradedModeTriggers:
    """T6.5: Integration test for DEGRADED_MODE trigger."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create config directory
        config_dir = temp_dir / 'config'
        config_dir.mkdir()
        
        # Create minimal configs
        (config_dir / 'kill_switches.json').write_text(json.dumps({
            "enforcement_order": ["DISABLE_WRITES", "DISABLE_LEARNING"],
            "switches": {}
        }))
        
        (config_dir / 'adk_determinism.json').write_text(json.dumps({
            "temperature": 0,
            "top_p": 1.0
        }))
        
        (config_dir / 'degraded_mode_policy.json').write_text(json.dumps({
            "trigger_conditions": {
                "conditions": [
                    {"id": "COMMIT_GATE_REJECTION", "action": "ENTER_DEGRADED"},
                    {"id": "FIREWALL_REJECTION", "action": "ENTER_DEGRADED"},
                    {"id": "MANIFEST_MISSING", "action": "HALT"},
                    {"id": "KILL_SWITCH_ACTIVE", "action": "ENTER_DEGRADED"}
                ]
            },
            "degraded_behavior": {
                "writes_blocked": True,
                "analysis_allowed": True
            },
            "alerts": {"channels": ["log"], "severity": "WARNING"}
        }))
        
        # Create data directories
        (temp_dir / 'data' / 'alerts').mkdir(parents=True)
        (temp_dir / 'data' / 'prewrite').mkdir(parents=True)
        (temp_dir / 'data' / 'evidence_store').mkdir(parents=True)
        
        # Create schema directory
        schemas_dir = config_dir / 'schemas'
        schemas_dir.mkdir()
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_firewall_rejection_triggers_degraded_mode(self):
        """Firewall rejection should trigger DEGRADED_MODE."""
        from src.control_plane.degraded_mode import (
            DegradedModeController, TriggerCondition, SystemState
        )
        
        controller = DegradedModeController()
        
        # Trigger DEGRADED_MODE
        new_state = controller.enter_degraded_mode(
            run_id='TEST-001',
            run_ts='2025-12-26T10:00:00+00:00',
            condition=TriggerCondition.FIREWALL_REJECTION,
            details='Schema validation failed'
        )
        
        assert new_state == SystemState.DEGRADED_MODE
        assert controller.can_write() == False
        assert controller.can_analyze() == True
    
    def test_manifest_missing_triggers_halt(self):
        """Missing manifest should trigger HALT state."""
        from src.control_plane.degraded_mode import (
            DegradedModeController, TriggerCondition, SystemState
        )
        
        controller = DegradedModeController()
        
        new_state = controller.enter_degraded_mode(
            run_id='TEST-002',
            run_ts='2025-12-26T10:00:00+00:00',
            condition=TriggerCondition.MANIFEST_MISSING,
            details='strategist.skill.md not found'
        )
        
        assert new_state == SystemState.HALTED
        assert controller.can_write() == False
        assert controller.can_analyze() == False
    
    def test_commit_gate_rejection_triggers_degraded(self):
        """CommitGate rejection should trigger DEGRADED_MODE."""
        from src.control_plane.degraded_mode import (
            DegradedModeController, TriggerCondition, SystemState
        )
        
        controller = DegradedModeController()
        
        new_state = controller.enter_degraded_mode(
            run_id='TEST-003',
            run_ts='2025-12-26T10:00:00+00:00',
            condition=TriggerCondition.COMMIT_GATE_REJECTION,
            details='HASH_MISMATCH'
        )
        
        assert new_state == SystemState.DEGRADED_MODE
        assert controller.can_write() == False
    
    def test_recovery_requires_operator_ack(self):
        """Recovery from DEGRADED_MODE requires operator acknowledgment."""
        from src.control_plane.degraded_mode import (
            DegradedModeController, TriggerCondition, SystemState
        )
        
        controller = DegradedModeController()
        
        # Enter degraded mode
        controller.enter_degraded_mode(
            run_id='TEST-004',
            run_ts='2025-12-26T10:00:00+00:00',
            condition=TriggerCondition.COMMIT_GATE_REJECTION,
            details='test'
        )
        
        # Attempt recovery without ack
        recovered = controller.recover('TEST-004', operator_ack=False)
        assert recovered == False
        assert controller.current_state == SystemState.DEGRADED_MODE
        
        # Recovery with ack
        recovered = controller.recover('TEST-004', operator_ack=True)
        assert recovered == True
        assert controller.current_state == SystemState.NORMAL
    
    def test_writes_blocked_in_degraded_mode(self):
        """Writes should be blocked when in DEGRADED_MODE."""
        from src.control_plane.degraded_mode import (
            DegradedModeController, TriggerCondition, SystemState
        )
        
        controller = DegradedModeController()
        
        # Initially writes allowed
        assert controller.can_write() == True
        
        # Enter degraded mode
        controller.enter_degraded_mode(
            run_id='TEST-005',
            run_ts='2025-12-26T10:00:00+00:00',
            condition=TriggerCondition.FIREWALL_REJECTION,
            details='test'
        )
        
        # Writes should now be blocked
        assert controller.can_write() == False


class TestAdversarialInjection:
    """T6.6: Adversarial test for injection attempts."""
    
    def test_firewall_blocks_script_injection(self):
        """Firewall should detect and block script injection."""
        from src.control_plane.firewall import InterAgentFirewall
        
        firewall = InterAgentFirewall()
        
        # Payload with script injection
        malicious_payload = {
            "agent_id": "strategist-v0.1",
            "schema_version": "2.0.0",
            "run_id": "RUN-20251226_100000",
            "timestamp": "2025-12-26T10:00:00+00:00",
            "content_hash": "sha256:abc123",
            "payload": {
                "plan_id": "PLAN-TEST123",
                "query": "<script>alert('xss')</script>"  # Injection attempt
            },
            "capability_claims": ["read_market_data"]
        }
        
        result = firewall.validate(malicious_payload, "proposal_envelope")
        
        # Should be rejected due to dangerous pattern
        assert result.valid == False
        assert any('dangerous pattern' in e.lower() or 'script' in e.lower() for e in result.errors)
    
    def test_firewall_blocks_sql_injection(self):
        """Firewall should detect and block SQL injection."""
        from src.control_plane.firewall import InterAgentFirewall
        
        firewall = InterAgentFirewall()
        
        # Payload with SQL injection
        malicious_payload = {
            "agent_id": "strategist-v0.1",
            "schema_version": "2.0.0",
            "run_id": "RUN-20251226_100000",
            "timestamp": "2025-12-26T10:00:00+00:00",
            "content_hash": "sha256:abc123",
            "payload": {
                "plan_id": "PLAN-TEST123",
                "query": "SELECT * FROM users; DROP TABLE users;--"  # SQL injection
            },
            "capability_claims": ["read_market_data"]
        }
        
        result = firewall.validate(malicious_payload, "proposal_envelope")
        
        # Should be rejected
        assert result.valid == False
    
    def test_firewall_blocks_command_injection(self):
        """Firewall should detect and block command injection."""
        from src.control_plane.firewall import InterAgentFirewall
        
        firewall = InterAgentFirewall()
        
        # Payload with command injection
        malicious_payload = {
            "agent_id": "strategist-v0.1",
            "schema_version": "2.0.0",
            "run_id": "RUN-20251226_100000",
            "timestamp": "2025-12-26T10:00:00+00:00",
            "content_hash": "sha256:abc123",
            "payload": {
                "plan_id": "PLAN-TEST123",
                "command": "; rm -rf /"  # Command injection
            },
            "capability_claims": ["read_market_data"]
        }
        
        result = firewall.validate(malicious_payload, "proposal_envelope")
        
        # Should be rejected
        assert result.valid == False
    
    def test_commit_gate_rejects_hash_mismatch(self):
        """CommitGate should reject bundles with tampered hash."""
        from src.control_plane.commit_gate import CommitGate, CommitBundle
        
        gate = CommitGate()
        
        # Create bundle with wrong hash
        bundle = CommitBundle(
            run_id='RUN-20251226_100000',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='sha256:aabbccdd11223344',  # Wrong hash but valid format
            payload={'data': 'test'},
            evidence_refs=[],
            capability_claims=['write_report']
        )
        
        result = gate.validate(bundle)
        
        assert result.accepted == False
        # Will be HASH_MISMATCH since the hash is valid format but doesn't match computed
        assert result.rejection.code == 'HASH_MISMATCH'
    
    def test_commit_gate_rejects_unauthorized_capability(self):
        """CommitGate should reject bundles claiming unauthorized capabilities."""
        from src.control_plane.commit_gate import CommitGate, CommitBundle
        
        gate = CommitGate()
        
        # Create valid bundle
        bundle = CommitBundle(
            run_id='RUN-20251226_100000',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'test'},
            evidence_refs=[],
            capability_claims=['dangerous_capability', 'unauthorized_action']
        )
        bundle.content_hash = bundle.compute_hash()
        
        # Validate with restricted allowed capabilities
        result = gate.validate(
            bundle,
            allowed_capabilities=['write_report']  # Claims don't match
        )
        
        assert result.accepted == False
        assert result.rejection.code == 'CAPABILITY_DENIED'
    
    def test_envelope_rejects_unauthorized_claims(self):
        """ProposalEnvelope should reject agents claiming unauthorized capabilities."""
        from src.agents.base import (
            BaseAgent, CapabilityDeniedError, ManifestParseError
        )
        
        # Use strategist which has defined capabilities
        from src.agents import StrategistAgent
        
        agent = StrategistAgent(
            run_id='TEST-001',
            run_ts='2025-12-26T10:00:00+00:00'
        )
        
        # Try to claim capability not in manifest
        with pytest.raises(CapabilityDeniedError):
            agent.validate_claims(['write_identity', 'execute_trade'])
    
    def test_manifest_loading_fails_on_missing_file(self):
        """Agent should fail to load if manifest is missing."""
        from src.agents.base import BaseAgent, ManifestParseError
        
        class FakeAgent(BaseAgent):
            SKILL_FILE = "nonexistent.skill.md"
            
            def process(self, input_data):
                pass
        
        with pytest.raises(ManifestParseError):
            FakeAgent(run_id='TEST-001', run_ts='2025-12-26T10:00:00+00:00')


class TestMutationDetection:
    """T6.3: Mutation tests for validator logic."""
    
    def test_hash_mutation_detected(self):
        """Mutating any bundle field should change the hash."""
        from src.control_plane.commit_gate import CommitBundle
        
        # Create baseline bundle
        baseline = CommitBundle(
            run_id='RUN-20251226_100000',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'test'},
            evidence_refs=['EV-001'],
            capability_claims=['write_report']
        )
        baseline.content_hash = baseline.compute_hash()
        original_hash = baseline.content_hash
        
        # Mutate run_id
        mutated = CommitBundle(
            run_id='RUN-20251226_100001',  # Changed
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'test'},
            evidence_refs=['EV-001'],
            capability_claims=['write_report']
        )
        assert mutated.compute_hash() != original_hash
        
        # Mutate payload
        mutated = CommitBundle(
            run_id='RUN-20251226_100000',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'MUTATED'},  # Changed
            evidence_refs=['EV-001'],
            capability_claims=['write_report']
        )
        assert mutated.compute_hash() != original_hash
        
        # Mutate evidence_refs
        mutated = CommitBundle(
            run_id='RUN-20251226_100000',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'test'},
            evidence_refs=['EV-002'],  # Changed
            capability_claims=['write_report']
        )
        assert mutated.compute_hash() != original_hash
    
    def test_envelope_mutation_detected(self):
        """Mutating any envelope field should change the hash."""
        from src.agents.base import ProposalEnvelope
        
        # Create baseline
        baseline = ProposalEnvelope.create(
            agent_id='strategist-v0.1',
            run_id='RUN-20251226_100000',
            timestamp='2025-12-26T10:00:00+00:00',
            payload={'plan_id': 'PLAN-TEST'},
            capability_claims=['read_market_data']
        )
        original_hash = baseline.content_hash
        
        # Mutate agent_id
        mutated = ProposalEnvelope.create(
            agent_id='researcher-v0.1',  # Changed
            run_id='RUN-20251226_100000',
            timestamp='2025-12-26T10:00:00+00:00',
            payload={'plan_id': 'PLAN-TEST'},
            capability_claims=['read_market_data']
        )
        assert mutated.content_hash != original_hash
        
        # Mutate capability_claims
        mutated = ProposalEnvelope.create(
            agent_id='strategist-v0.1',
            run_id='RUN-20251226_100000',
            timestamp='2025-12-26T10:00:00+00:00',
            payload={'plan_id': 'PLAN-TEST'},
            capability_claims=['read_market_data', 'extra_claim']  # Changed
        )
        assert mutated.content_hash != original_hash
    
    def test_validator_rejects_null_injection(self):
        """Validator should reject null byte injection attempts."""
        from src.control_plane.firewall import InterAgentFirewall
        
        firewall = InterAgentFirewall()
        
        # Try null byte injection
        payload = {
            "agent_id": "strategist-v0.1",
            "schema_version": "2.0.0",
            "run_id": "RUN-20251226_100000",
            "timestamp": "2025-12-26T10:00:00+00:00",
            "content_hash": "sha256:abc123",
            "payload": {
                "query": "normal\x00malicious"  # Null byte injection
            },
            "capability_claims": ["read_market_data"]
        }
        
        result = firewall.validate(payload, "proposal_envelope")
        
        # Should be rejected
        assert result.valid == False
    
    def test_prewrite_hash_mutation_rejected(self):
        """CommitGate should reject if prewrite hash doesn't match bundle."""
        from src.control_plane.commit_gate import CommitGate, CommitBundle
        import tempfile
        
        temp_dir = Path(tempfile.mkdtemp())
        prewrite_dir = temp_dir / 'prewrite'
        prewrite_dir.mkdir()
        
        gate = CommitGate(prewrite_path=prewrite_dir)
        
        # Create bundle
        bundle = CommitBundle(
            run_id='RUN-20251226_100000',
            agent_id='reporter-v0.1',
            schema_version='2.0.0',
            timestamp='2025-12-26T10:00:00+00:00',
            content_hash='placeholder',
            payload={'data': 'test'},
            evidence_refs=[],
            capability_claims=['write_report']
        )
        bundle.content_hash = bundle.compute_hash()
        
        # Create prewrite with different hash
        prewrite_file = prewrite_dir / f"PREWRITE-{bundle.run_id}.json"
        prewrite_file.write_text(json.dumps({
            "run_id": bundle.run_id,
            "bundle_hash": "sha256:different_hash_123",  # Wrong hash
            "timestamp": "2025-12-26T10:00:00+00:00",
            "agent_id": bundle.agent_id,
            "evidence_refs": [],
            "capability_claims": []
        }))
        
        # Validate should fail on prewrite check
        result = gate.validate(bundle)
        
        assert result.accepted == False
        assert result.rejection.code == 'HASH_MISMATCH'
        
        # Cleanup
        shutil.rmtree(temp_dir)
