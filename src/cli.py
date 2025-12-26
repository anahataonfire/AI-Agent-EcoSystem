#!/usr/bin/env python3
"""
DTL CLI - Runner Contract for DTL v2.0

Usage:
    dtl run --mode=mock|live --run_id=RUN-xxx [--policy_snapshot=path]
    dtl status
    dtl validate-bundle <bundle_path> [--kill_switches=...] [--capabilities=...]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Add project root to path for imports when running as script
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import from control_plane to avoid duplicate definitions
from src.control_plane.state import SystemState


class RunMode(Enum):
    """Run mode for CLI - distinct from SystemState."""
    MOCK = "mock"
    LIVE = "live"


@dataclass
class RunConfig:
    """Configuration for a single DTL run."""
    run_id: str
    mode: RunMode
    policy_snapshot_path: Optional[str]
    timestamp: str
    
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "mode": self.mode.value,
            "policy_snapshot_path": self.policy_snapshot_path,
            "timestamp": self.timestamp
        }


@dataclass 
class RunResult:
    """Result of a DTL run."""
    run_id: str
    success: bool
    state: SystemState
    steps_completed: list[str]
    errors: list[str]
    output_path: Optional[str]


def generate_run_id() -> str:
    """Generate a unique run ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"RUN-{ts}"


def load_policy_snapshot(path: Optional[str]) -> dict:
    """Load policy snapshot from file or return defaults."""
    if path and Path(path).exists():
        with open(path, 'r') as f:
            return json.load(f)
    
    # Default policy snapshot
    from src.control_plane.fingerprint import get_runtime_fingerprint
    return {
        "version": "2.0.0",
        "kill_switches": {
            "DISABLE_LEARNING": True,
            "DISABLE_REUSE": False
        },
        "capability_manifests": [],
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "runtime_fingerprint": get_runtime_fingerprint()
    }


def load_kill_switches(policy: dict) -> dict:
    """Extract kill switch state from policy."""
    return policy.get("kill_switches", {})


def enforce_kill_switches(switches: dict) -> tuple[bool, list[str], list[str]]:
    """
    Check kill switch compliance using KillSwitchEnforcer.
    Returns (can_proceed, active_switches, blocked_operations).
    
    DISABLE_WRITES = hard halt before Step 4
    DISABLE_LEARNING = blocks learning-related capability claims
    """
    from src.control_plane.kill_switch import KillSwitchEnforcer
    
    enforcer = KillSwitchEnforcer()
    
    # Define operations this run will attempt
    requested_ops = ["run_agents", "build_commit_bundle", "commit_gate_pass"]
    
    result = enforcer.enforce(requested_ops)
    
    return result.can_proceed, result.active_switches, result.blocked_operations


def run_mock_pipeline(config: RunConfig) -> RunResult:
    """
    Execute a mock pipeline run.
    This is for debugging/testing without external dependencies.
    """
    steps = []
    errors = []
    
    print(f"[MOCK] Starting run: {config.run_id}")
    
    # Step 1: Load policy snapshot
    print("[MOCK] Step 1: Loading policy snapshot...")
    policy = load_policy_snapshot(config.policy_snapshot_path)
    steps.append("load_policy_snapshot")
    
    # Step 2: Load capability manifests
    print("[MOCK] Step 2: Loading capability manifests...")
    # TODO: Load from skills/*.skill.md
    steps.append("load_capability_manifests")
    
    # Step 3: Enforce kill switches (FAIL-FAST before agents run)
    print("[MOCK] Step 3: Enforcing kill switches...")
    switches = load_kill_switches(policy)
    can_proceed, active, blocked = enforce_kill_switches(switches)
    
    if active:
        print(f"[MOCK]   Active switches: {active}")
    if blocked:
        print(f"[MOCK]   Blocked operations: {blocked}")
    
    steps.append("enforce_kill_switches")
    
    if not can_proceed:
        print(f"[MOCK] HALTED: Kill switch blocked execution")
        return RunResult(
            run_id=config.run_id,
            success=False,
            state=SystemState.HALTED,
            steps_completed=steps,
            errors=[f"Kill switch blocked: {blocked}"],
            output_path=None
        )
    
    # Step 4: Run agents (proposal only)
    print("[MOCK] Step 4: Running agents (mock proposals)...")
    # TODO: Run actual agents
    mock_proposals = {
        "strategist": {"plan_id": "PLAN-MOCK0001", "asset_universe": ["XAU", "GME"]},
        "researcher": {"evidence_candidates": []},
        "reporter": {"bundle": None}
    }
    steps.append("run_agents")
    
    # Step 5: Reporter builds CommitBundle
    print("[MOCK] Step 5: Building CommitBundle...")
    # TODO: Actual bundle construction
    steps.append("build_commit_bundle")
    
    # Step 6: CommitGate validation
    print("[MOCK] Step 6: CommitGate validation...")
    # TODO: Actual validation
    steps.append("commit_gate_validate")
    
    # Step 7: Ledger prewrite
    print("[MOCK] Step 7: Ledger prewrite...")
    steps.append("ledger_prewrite")
    
    # Step 8: Write immutable stores (skipped in mock)
    print("[MOCK] Step 8: Write immutable stores (SKIPPED - mock mode)")
    steps.append("write_stores_skipped")
    
    # Generate output
    output_dir = Path("data/dtl_runs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{config.run_id}.json"
    
    output = {
        "run_id": config.run_id,
        "mode": config.mode.value,
        "timestamp": config.timestamp,
        "policy_applied": policy,
        "proposals": mock_proposals,
        "steps_completed": steps
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"[MOCK] Output saved to: {output_path}")
    
    return RunResult(
        run_id=config.run_id,
        success=True,
        state=SystemState.NORMAL,
        steps_completed=steps,
        errors=errors,
        output_path=str(output_path)
    )


def run_live_pipeline(config: RunConfig) -> RunResult:
    """
    Execute a live pipeline run with real data.
    """
    print(f"[LIVE] Starting run: {config.run_id}")
    print("[LIVE] Live mode not yet implemented - falling back to mock")
    
    # For now, fall back to mock with a warning
    return run_mock_pipeline(config)


def cmd_run(args) -> int:
    """Execute the 'run' command."""
    from src.orchestrator import DTLOrchestrator, RunConfig as OrchestratorConfig, RunMode as OrchestratorMode
    
    mode = RunMode(args.mode)
    run_id = args.run_id or generate_run_id()
    
    # Job presets mapping
    JOB_PRESETS = {
        'quant_premarket': {
            'market_context': {
                'market_status': 'pre_market',
                'focus_assets': ['XAU', 'XAG', 'GME', 'BTC'],
                'timeframe': 'daily'
            },
            'policy_snapshot': 'config/quant_premarket_policy.json'
        },
        'realitycheck_eod': {
            'market_context': {
                'market_status': 'post_market',
                'focus_assets': [],
                'timeframe': 'eod_grading'
            },
            'policy_snapshot': 'config/realitycheck_eod_policy.json'
        },
        'quant_intraday': {
            'market_context': {
                'market_status': 'intraday',
                'focus_assets': ['GME'],
                'timeframe': 'hourly'
            },
            'policy_snapshot': 'config/quant_intraday_policy.json'
        }
    }
    
    # Apply job preset if specified
    market_context = {}
    policy_path = args.policy_snapshot
    
    if args.job:
        if args.job not in JOB_PRESETS:
            print(f"Error: Unknown job '{args.job}'")
            print(f"Available jobs: {list(JOB_PRESETS.keys())}")
            return 1
        
        preset = JOB_PRESETS[args.job]
        market_context = preset['market_context']
        if not policy_path and Path(preset['policy_snapshot']).exists():
            policy_path = preset['policy_snapshot']
        
        print(f"DTL Run Starting (Job: {args.job})")
    else:
        print(f"DTL Run Starting")
    
    print(f"  Run ID: {run_id}")
    print(f"  Mode: {mode.value}")
    print(f"  Policy: {policy_path or 'default'}")
    print()
    
    # Use orchestrator for live mode
    if mode == RunMode.LIVE:
        orchestrator = DTLOrchestrator()
        orch_mode = OrchestratorMode.LIVE
        orch_config = OrchestratorConfig.create(run_id=run_id, mode=orch_mode)
        
        result = orchestrator.run(orch_config, market_context)
        
        print()
        print(f"Run Complete")
        print(f"  Success: {result.success}")
        print(f"  State: {result.system_state}")
        print(f"  Steps: {result.steps_completed}")
        if result.errors:
            print(f"  Errors: {result.errors}")
        if result.output:
            print(f"  Output: {result.output}")
        
        return 0 if result.success else 1
    
    # Mock mode uses simple pipeline
    config = RunConfig(
        run_id=run_id,
        mode=mode,
        policy_snapshot_path=policy_path,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    result = run_mock_pipeline(config)
    
    print()
    print(f"Run Complete")
    print(f"  Success: {result.success}")
    print(f"  State: {result.state.value}")
    print(f"  Steps: {len(result.steps_completed)}")
    if result.errors:
        print(f"  Errors: {result.errors}")
    if result.output_path:
        print(f"  Output: {result.output_path}")
    
    return 0 if result.success else 1


def cmd_status(args) -> int:
    """Show current DTL system status."""
    print("DTL System Status")
    print("-" * 40)
    
    # Check for recent runs
    runs_dir = Path("data/dtl_runs")
    if runs_dir.exists():
        runs = sorted(runs_dir.glob("RUN-*.json"), reverse=True)[:5]
        print(f"Recent runs: {len(runs)}")
        for run in runs:
            print(f"  - {run.name}")
    else:
        print("No runs found")
    
    # Check system state
    print(f"\nSystem State: NORMAL")  # TODO: Persist state
    
    return 0


def cmd_validate_bundle(args) -> int:
    """
    Validate a CommitBundle file using real CommitGate.
    
    Uses actual validation with explicit inputs for all dependencies.
    """
    from src.control_plane.commit_gate import CommitGate, CommitBundle
    
    bundle_path = Path(args.bundle_path)
    
    if not bundle_path.exists():
        print(f"Error: Bundle not found: {bundle_path}")
        return 1
    
    print(f"Validating bundle: {bundle_path}")
    
    try:
        with open(bundle_path, 'r') as f:
            bundle_data = json.load(f)
        
        # Construct CommitBundle from file
        bundle = CommitBundle(
            run_id=bundle_data.get('run_id', 'UNKNOWN'),
            agent_id=bundle_data.get('agent_id', 'unknown-v0.0'),
            schema_version=bundle_data.get('schema_version', '2.0.0'),
            timestamp=bundle_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            content_hash=bundle_data.get('content_hash', ''),
            payload=bundle_data.get('payload', {}),
            evidence_refs=bundle_data.get('evidence_refs', []),
            capability_claims=bundle_data.get('capability_claims', [])
        )
        
        # Parse CLI args for validation context
        kill_switches = args.kill_switches.split(',') if args.kill_switches else []
        capabilities = args.capabilities.split(',') if args.capabilities else None
        
        # Create CommitGate with explicit paths
        gate = CommitGate(
            evidence_store_path=args.evidence_store,
            prewrite_path=args.prewrite_path
        )
        
        # Run real validation
        result = gate.validate(
            bundle,
            active_kill_switches=kill_switches if kill_switches else None,
            allowed_capabilities=capabilities
        )
        
        print(f"  Run ID: {bundle.run_id}")
        print(f"  Agent: {bundle.agent_id}")
        print(f"  Bundle Hash: {bundle.compute_hash()[:40]}...")
        print(f"  Validation: {result.status.value}")
        
        if result.rejection:
            print(f"  Rejection Code: {result.rejection.code}")
            print(f"  Violating Field: {result.rejection.violating_field}")
            print(f"  Details: {result.rejection.details}")
            return 1
        
        return 0
        
    except json.JSONDecodeError as e:
        print(f"  Parse error: {e}")
        return 1
    except Exception as e:
        print(f"  Validation error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog='dtl',
        description='DTL v2.0 - Runner Contract CLI'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Execute a DTL run')
    run_parser.add_argument(
        '--mode', 
        choices=['mock', 'live'], 
        default='mock',
        help='Run mode (default: mock)'
    )
    run_parser.add_argument(
        '--run_id',
        help='Explicit run ID (default: auto-generated)'
    )
    run_parser.add_argument(
        '--policy_snapshot',
        help='Path to policy snapshot JSON'
    )
    run_parser.add_argument(
        '--job',
        choices=['quant_premarket', 'realitycheck_eod', 'quant_intraday'],
        help='Job preset (sets market_context and default policy)'
    )
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    # Validate-bundle command
    validate_parser = subparsers.add_parser('validate-bundle', help='Validate a CommitBundle')
    validate_parser.add_argument('bundle_path', help='Path to bundle JSON')
    validate_parser.add_argument(
        '--kill_switches',
        help='Comma-separated active kill switches (e.g., DISABLE_LEARNING,DISABLE_WRITES)'
    )
    validate_parser.add_argument(
        '--capabilities',
        help='Comma-separated allowed capabilities'
    )
    validate_parser.add_argument(
        '--evidence_store',
        default='data/evidence_store',
        help='Path to evidence store directory'
    )
    validate_parser.add_argument(
        '--prewrite_path',
        default='data/run_ledger/prewrite',
        help='Path to prewrite directory'
    )
    
    args = parser.parse_args()
    
    if args.command == 'run':
        return cmd_run(args)
    elif args.command == 'status':
        return cmd_status(args)
    elif args.command == 'validate-bundle':
        return cmd_validate_bundle(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
