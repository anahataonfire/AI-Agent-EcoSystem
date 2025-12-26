"""
DTL v2.0 ADK Orchestration Runner

Implements the 8-step enforcement order with:
- Firewall validation between agent hops
- Kill switch enforcement
- Deterministic run_ts minting
- CommitGate validation before writes
- DegradedModeController for state transitions

SAFETY GUARANTEES:
- Prewrite only created after eligibility check
- Prewrite deleted if validation fails
- DegradedModeController gates all writes
"""

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any


class RunMode(Enum):
    MOCK = "mock"
    LIVE = "live"


@dataclass
class RunConfig:
    """Configuration for a DTL run."""
    run_id: str
    run_ts: str  # ISO8601 - minted by runner, used by all agents
    mode: RunMode
    policy_snapshot: dict
    kill_switches: list[str]
    runner_capabilities: list[str] = field(default_factory=list)
    manifest_capabilities: dict = field(default_factory=dict)  # P1-1: Agent -> allowed capabilities
    
    @classmethod
    def create(cls, run_id: Optional[str] = None, mode: RunMode = RunMode.MOCK) -> 'RunConfig':
        """
        Factory to create RunConfig with deterministic timestamps.
        
        IMPORTANT: run_ts is minted ONCE here and used throughout the run.
        """
        now = datetime.now(timezone.utc)
        
        if not run_id:
            run_id = f"RUN-{now.strftime('%Y%m%d_%H%M%S')}"
        
        return cls(
            run_id=run_id,
            run_ts=now.isoformat(),
            mode=mode,
            policy_snapshot={},
            kill_switches=[],
            runner_capabilities=[],
            manifest_capabilities={}
        )


@dataclass
class RunResult:
    """Result of a DTL run."""
    run_id: str
    success: bool
    system_state: str  # String to avoid import cycle
    steps_completed: list[str]
    errors: list[str] = field(default_factory=list)
    output: Optional[dict] = None


class DTLOrchestrator:
    """
    ADK SequentialAgent runner for DTL v2.0.
    
    Implements the 8-step enforcement order:
    1. Load policy snapshot
    2. Load capability manifests
    3. Enforce kill switches
    4. Run Strategist → (validate envelope)
    5. Run Researcher → (validate envelope)
    6. Run Reporter → build CommitBundle
    7. CommitGate validate (with proper prewrite lifecycle)
    8. Write to immutable stores (if accepted AND can_write)
    
    P0-2: DegradedModeController is wired for all state transitions.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.config_dir = self.project_root / 'config'
        self.data_dir = self.project_root / 'data'
        
        # Control plane components (lazy loaded)
        self._firewall = None
        self._commit_gate = None
        self._kill_switch_enforcer = None
        self._evidence_queue = None
        self._routing_stats = None
        self._degraded_controller = None  # P0-2: Add DegradedModeController
        
        # Runtime state
        self.steps_completed: list[str] = []
        self.errors: list[str] = []
    
    @property
    def firewall(self):
        if self._firewall is None:
            from src.control_plane.firewall import InterAgentFirewall
            self._firewall = InterAgentFirewall()
        return self._firewall
    
    @property
    def commit_gate(self):
        if self._commit_gate is None:
            from src.control_plane.commit_gate import CommitGate
            self._commit_gate = CommitGate()
        return self._commit_gate
    
    @property
    def kill_switch_enforcer(self):
        if self._kill_switch_enforcer is None:
            from src.control_plane.kill_switch import KillSwitchEnforcer
            self._kill_switch_enforcer = KillSwitchEnforcer()
        return self._kill_switch_enforcer
    
    @property
    def evidence_queue(self):
        if self._evidence_queue is None:
            from src.control_plane.evidence_queue import EvidenceCandidateQueue
            self._evidence_queue = EvidenceCandidateQueue()
        return self._evidence_queue
    
    @property
    def routing_stats(self):
        if self._routing_stats is None:
            from src.control_plane.routing_stats import RoutingStatisticsStore
            self._routing_stats = RoutingStatisticsStore()
        return self._routing_stats
    
    @property
    def degraded_controller(self):
        """P0-2: DegradedModeController for state transitions."""
        if self._degraded_controller is None:
            from src.control_plane.degraded_mode import DegradedModeController
            self._degraded_controller = DegradedModeController(
                config_path=self.config_dir / 'degraded_mode_policy.json',
                alert_log_path=self.data_dir / 'alerts' / 'degraded_mode.log'
            )
        return self._degraded_controller
    
    @property
    def current_state(self) -> str:
        """Get current system state."""
        return self.degraded_controller.current_state.value
    
    def run(self, config: RunConfig, market_context: Optional[dict] = None) -> RunResult:
        """
        Execute the full 8-step pipeline.
        
        Args:
            config: Run configuration with run_id, run_ts, etc.
            market_context: Optional market context for Strategist
        
        Returns:
            RunResult with success/failure and outputs
        """
        self.steps_completed = []
        self.errors = []
        
        try:
            # Step 1: Load policy snapshot
            self._step_1_load_policy(config)
            
            # Step 2: Load capability manifests
            if not self._step_2_load_manifests(config):
                return self._create_result(config, success=False)
            
            # Step 3: Enforce kill switches
            if not self._step_3_enforce_kill_switches(config):
                return self._create_result(config, success=False)
            
            # Step 4: Run Strategist
            strategist_output = self._step_4_run_strategist(config, market_context or {})
            if strategist_output is None:
                return self._create_result(config, success=False)
            
            # Step 5: Run Researcher
            researcher_output = self._step_5_run_researcher(config, strategist_output)
            if researcher_output is None:
                return self._create_result(config, success=False)
            
            # Step 6: Run Reporter → build CommitBundle
            reporter_output = self._step_6_run_reporter(config, researcher_output)
            if reporter_output is None:
                return self._create_result(config, success=False)
            
            # Step 7: CommitGate validation (with proper prewrite lifecycle)
            commit_result = self._step_7_commit_gate(config, reporter_output)
            if not commit_result['accepted']:
                return self._create_result(config, success=False, output=commit_result)
            
            # Step 8: Write to immutable stores (gated by DegradedModeController)
            write_result = self._step_8_write_stores(config, reporter_output)
            
            return self._create_result(config, success=write_result.get('success', False), output=write_result)
            
        except Exception as e:
            self.errors.append(f"Pipeline error: {str(e)}")
            # P0-2: Use DegradedModeController for state transition
            from src.control_plane.degraded_mode import TriggerCondition
            self.degraded_controller.enter_degraded_mode(
                config.run_id,
                config.run_ts,
                TriggerCondition.UNKNOWN,
                str(e)
            )
            return self._create_result(config, success=False)
    
    def _step_1_load_policy(self, config: RunConfig):
        """Step 1: Load policy snapshot."""
        # Load ADK determinism config
        adk_config_path = self.config_dir / 'adk_determinism.json'
        if adk_config_path.exists():
            with open(adk_config_path) as f:
                config.policy_snapshot['adk_determinism'] = json.load(f)
        
        # Load runtime fingerprint
        from src.control_plane.fingerprint import get_runtime_fingerprint
        config.policy_snapshot['runtime_fingerprint'] = get_runtime_fingerprint()
        
        # Record run_ts in policy for replay reference
        config.policy_snapshot['run_ts'] = config.run_ts
        
        self.steps_completed.append('load_policy')
    
    def _step_2_load_manifests(self, config: RunConfig) -> bool:
        """Step 2: Load capability manifests."""
        from src.agents.base import AGENTS_DIR, AgentManifest, ManifestParseError
        from src.control_plane.degraded_mode import TriggerCondition
        
        manifests = {}
        for skill_file in AGENTS_DIR.glob('*.skill.md'):
            try:
                manifest = AgentManifest(skill_file)
                manifests[manifest.agent_id] = {
                    'allowed': manifest.allowed,
                    'denied': manifest.denied
                }
                # P1-1: Store for capability enforcement
                config.manifest_capabilities[manifest.agent_id] = manifest.allowed
            except ManifestParseError as e:
                # P0-2: Missing manifest triggers HALT
                self.errors.append(f"Failed to load {skill_file}: {e}")
                self.degraded_controller.enter_degraded_mode(
                    config.run_id,
                    config.run_ts,
                    TriggerCondition.MANIFEST_MISSING,
                    str(e)
                )
                return False
        
        config.policy_snapshot['manifests'] = manifests
        self.steps_completed.append('load_manifests')
        return True
    
    def _step_3_enforce_kill_switches(self, config: RunConfig) -> bool:
        """Step 3: Enforce kill switches."""
        from src.control_plane.degraded_mode import TriggerCondition
        
        # Load kill switches
        ks_path = self.config_dir / 'kill_switches.json'
        if ks_path.exists():
            with open(ks_path) as f:
                ks_data = json.load(f)
                config.kill_switches = ks_data.get('active_switches', [])
        
        # Enforce - uses config loaded by enforcer
        result = self.kill_switch_enforcer.enforce(['run_agents', 'write_evidence'])
        
        if not result.can_proceed:
            self.errors.append(f"Kill switch blocked: {result.blocked_operations}")
            # P0-2: Use DegradedModeController
            self.degraded_controller.enter_degraded_mode(
                config.run_id,
                config.run_ts,
                TriggerCondition.KILL_SWITCH_ACTIVE,
                f"Blocked operations: {result.blocked_operations}"
            )
            return False
        
        # Set runner capabilities based on active switches
        if 'DISABLE_LEARNING' not in result.active_switches:
            config.runner_capabilities.append('read_routing_stats')
        
        self.steps_completed.append('enforce_kill_switches')
        return True
    
    def _step_4_run_strategist(self, config: RunConfig, market_context: dict) -> Optional[dict]:
        """Step 4: Run Strategist agent."""
        from src.agents import StrategistAgent
        from src.control_plane.degraded_mode import TriggerCondition
        
        try:
            strategist = StrategistAgent(
                run_id=config.run_id,
                run_ts=config.run_ts,
                routing_stats=self.routing_stats if 'read_routing_stats' in config.runner_capabilities else None,
                firewall=self.firewall,
                runner_capabilities=config.runner_capabilities
            )
            
            output = strategist.process({
                'market_context': market_context
            })
            
            # Firewall validation happens in wrap_output, but double-check
            result = self.firewall.validate(output.to_dict(), 'proposal_envelope')
            if not result.valid:
                self.errors.append(f"Strategist envelope rejected: {result.errors}")
                # P0-2: Firewall rejection triggers degraded mode
                self.degraded_controller.enter_degraded_mode(
                    config.run_id,
                    config.run_ts,
                    TriggerCondition.FIREWALL_REJECTION,
                    str(result.errors)
                )
                return None
            
            self.steps_completed.append('run_strategist')
            return output.payload
            
        except Exception as e:
            self.errors.append(f"Strategist error: {str(e)}")
            return None
    
    def _step_5_run_researcher(self, config: RunConfig, strategist_output: dict) -> Optional[dict]:
        """Step 5: Run Researcher agent."""
        from src.agents import ResearcherAgent
        from src.control_plane.degraded_mode import TriggerCondition
        
        try:
            researcher = ResearcherAgent(
                run_id=config.run_id,
                run_ts=config.run_ts,
                evidence_queue=self.evidence_queue,
                firewall=self.firewall,
                runner_capabilities=config.runner_capabilities
            )
            
            output = researcher.process({
                'plan': strategist_output
            })
            
            # Validate envelope
            result = self.firewall.validate(output.to_dict(), 'proposal_envelope')
            if not result.valid:
                self.errors.append(f"Researcher envelope rejected: {result.errors}")
                self.degraded_controller.enter_degraded_mode(
                    config.run_id,
                    config.run_ts,
                    TriggerCondition.FIREWALL_REJECTION,
                    str(result.errors)
                )
                return None
            
            self.steps_completed.append('run_researcher')
            return output.payload
            
        except Exception as e:
            self.errors.append(f"Researcher error: {str(e)}")
            return None
    
    def _step_6_run_reporter(self, config: RunConfig, researcher_output: dict) -> Optional[dict]:
        """Step 6: Run Reporter agent."""
        from src.agents import ReporterAgent
        from src.control_plane.degraded_mode import TriggerCondition
        
        try:
            reporter = ReporterAgent(
                run_id=config.run_id,
                run_ts=config.run_ts,
                commit_gate=self.commit_gate,
                evidence_queue=self.evidence_queue,
                firewall=self.firewall,
                runner_capabilities=config.runner_capabilities
            )
            
            output = reporter.process({
                'plan_id': researcher_output.get('plan_id', 'UNKNOWN'),
                'summary': f"Analyzed {len(researcher_output.get('evidence_candidates', []))} evidence items"
            })
            
            # Validate envelope
            result = self.firewall.validate(output.to_dict(), 'proposal_envelope')
            if not result.valid:
                self.errors.append(f"Reporter envelope rejected: {result.errors}")
                self.degraded_controller.enter_degraded_mode(
                    config.run_id,
                    config.run_ts,
                    TriggerCondition.FIREWALL_REJECTION,
                    str(result.errors)
                )
                return None
            
            self.steps_completed.append('run_reporter')
            return output.payload
            
        except Exception as e:
            self.errors.append(f"Reporter error: {str(e)}")
            return None
    
    def _step_7_commit_gate(self, config: RunConfig, reporter_output: dict) -> dict:
        """
        Step 7: CommitGate validation.
        
        P0-1: Proper prewrite lifecycle:
        1. Validate eligibility (checks 1-6)
        2. Create prewrite if eligible
        3. Full validate (checks 1-7)
        4. Delete prewrite if validation fails
        5. Promote if validation succeeds
        """
        from src.control_plane.commit_gate import CommitBundle
        from src.control_plane.degraded_mode import TriggerCondition
        
        bundle_data = reporter_output.get('commit_bundle', {})
        
        # Reconstruct CommitBundle
        bundle = CommitBundle(
            run_id=bundle_data.get('run_id', config.run_id),
            agent_id=bundle_data.get('agent_id', 'reporter-v0.1'),
            schema_version=bundle_data.get('schema_version', '2.0.0'),
            timestamp=bundle_data.get('timestamp', config.run_ts),
            content_hash=bundle_data.get('content_hash', ''),
            payload=bundle_data.get('payload', {}),
            evidence_refs=bundle_data.get('evidence_refs', []),
            capability_claims=bundle_data.get('capability_claims', [])
        )
        
        # P1-1: Get allowed capabilities from reporter manifest
        reporter_agent_id = bundle_data.get('agent_id', 'reporter-v0.1')
        allowed_caps = config.manifest_capabilities.get(reporter_agent_id, [])
        
        # Step 7a: Check eligibility BEFORE creating prewrite
        eligibility = self.commit_gate.validate_prewrite_eligibility(
            bundle,
            active_kill_switches=config.kill_switches,
            allowed_capabilities=allowed_caps
        )
        
        if not eligibility.accepted:
            self.errors.append(f"CommitGate eligibility failed: {eligibility.rejection.code if eligibility.rejection else 'UNKNOWN'}")
            self.degraded_controller.enter_degraded_mode(
                config.run_id,
                config.run_ts,
                TriggerCondition.COMMIT_GATE_REJECTION,
                eligibility.rejection.details if eligibility.rejection else None
            )
            return {
                'accepted': False,
                'rejection_code': eligibility.rejection.code if eligibility.rejection else 'UNKNOWN',
                'details': eligibility.rejection.details if eligibility.rejection else None
            }
        
        # Step 7b: Create prewrite (now safe)
        prewrite_path = self.commit_gate.create_prewrite(bundle)
        
        # Step 7c: Full validation (including prewrite check)
        result = self.commit_gate.validate(
            bundle,
            active_kill_switches=config.kill_switches,
            allowed_capabilities=allowed_caps
        )
        
        self.steps_completed.append('commit_gate_validate')
        
        if not result.accepted:
            # P0-1: Delete prewrite on failure
            self.commit_gate.delete_prewrite(bundle)
            self.errors.append(f"CommitGate rejected: {result.rejection.code if result.rejection else 'UNKNOWN'}")
            self.degraded_controller.enter_degraded_mode(
                config.run_id,
                config.run_ts,
                TriggerCondition.COMMIT_GATE_REJECTION,
                result.rejection.details if result.rejection else None
            )
            return {
                'accepted': False,
                'rejection_code': result.rejection.code if result.rejection else 'UNKNOWN',
                'details': result.rejection.details if result.rejection else None
            }
        
        # Step 7d: Promote prewrite to committed
        promote_result = self.commit_gate.promote_to_committed(bundle)
        if not promote_result.success:
            self.errors.append(f"Promote failed: {promote_result.message}")
            return {
                'accepted': False,
                'rejection_code': 'PROMOTE_FAILED',
                'details': promote_result.message
            }
        
        return {'accepted': True, 'bundle_hash': bundle.content_hash, 'committed_path': str(promote_result.path)}
    
    def _step_8_write_stores(self, config: RunConfig, reporter_output: dict) -> dict:
        """
        Step 8: Write to immutable stores.
        
        P0-2: Gated by DegradedModeController.can_write()
        """
        # P0-2: Check if writes are allowed
        if not self.degraded_controller.can_write():
            self.errors.append("Writes blocked (DEGRADED_MODE)")
            return {
                'success': False,
                'write_skipped': True,
                'reason': 'DEGRADED_MODE'
            }
        
        # Write run output
        output_dir = self.data_dir / 'dtl_runs'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{config.run_id}.json"
        
        run_data = {
            'run_id': config.run_id,
            'run_ts': config.run_ts,
            'mode': config.mode.value,
            'success': True,
            'policy_applied': config.policy_snapshot,
            'report': reporter_output.get('report', {}),
            'commit_bundle': reporter_output.get('commit_bundle', {})
        }
        
        with open(output_file, 'w') as f:
            json.dump(run_data, f, indent=2)
        
        self.steps_completed.append('write_stores')
        
        return {
            'success': True,
            'output_file': str(output_file),
            'report': reporter_output.get('report', {})
        }
    
    def _create_result(self, config: RunConfig, success: bool, output: Optional[dict] = None) -> RunResult:
        """Create RunResult."""
        return RunResult(
            run_id=config.run_id,
            success=success,
            system_state=self.current_state,
            steps_completed=self.steps_completed,
            errors=self.errors,
            output=output
        )


def run_pipeline(
    run_id: Optional[str] = None,
    mode: str = 'mock',
    market_context: Optional[dict] = None
) -> RunResult:
    """
    Convenience function to run the full DTL pipeline.
    
    Args:
        run_id: Optional run ID (auto-generated if not provided)
        mode: 'mock' or 'live'
        market_context: Market context for Strategist
    
    Returns:
        RunResult with success/failure and outputs
    """
    run_mode = RunMode.LIVE if mode == 'live' else RunMode.MOCK
    config = RunConfig.create(run_id=run_id, mode=run_mode)
    
    orchestrator = DTLOrchestrator()
    return orchestrator.run(config, market_context)
