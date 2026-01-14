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
import secrets
import sys
import hashlib
from src.utils.hashing import compute_sha256_hash
from src.control_plane.improvement_store import ImprovementStore
from src.control_plane.human_approval_gate import HumanApprovalGate
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Add project root to path for imports when running as script
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env with override=True so it takes priority over shell environment
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

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


def cmd_health(args) -> int:
    """
    Check system health: databases, LLM, API connectivity.
    
    Returns 0 if all checks pass, 1 if any check fails.
    """
    import sqlite3
    import requests
    from src.core.llm_config import validate_llm_connectivity
    
    print("\n" + "=" * 50)
    print("DTL System Health Check")
    print("=" * 50 + "\n")
    
    all_healthy = True
    
    # Check 1: Content Database
    content_db = PROJECT_ROOT / "data" / "content" / "content.db"
    try:
        if content_db.exists():
            conn = sqlite3.connect(content_db)
            count = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
            conn.close()
            print(f"✓ Content DB: {count} entries")
        else:
            print(f"✗ Content DB: Not found at {content_db}")
            all_healthy = False
    except Exception as e:
        print(f"✗ Content DB: Error - {e}")
        all_healthy = False
    
    # Check 2: Evidence Store
    evidence_db = PROJECT_ROOT / "data" / "evidence_store.db"
    try:
        if evidence_db.exists():
            conn = sqlite3.connect(evidence_db)
            count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
            conn.close()
            print(f"✓ Evidence Store: {count} entries")
        else:
            print(f"✗ Evidence Store: Not found")
            all_healthy = False
    except Exception as e:
        print(f"✗ Evidence Store: Error - {e}")
        all_healthy = False
    
    # Check 3: Planner Tasks
    planner_db = PROJECT_ROOT / "data" / "planner_tasks.db"
    try:
        if planner_db.exists():
            conn = sqlite3.connect(planner_db)
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            conn.close()
            print(f"✓ Planner DB: {count} tasks")
        else:
            print(f"⚠ Planner DB: Not found (optional)")
    except Exception as e:
        print(f"⚠ Planner DB: {e} (optional)")
    
    # Check 4: LLM Connectivity (CRITICAL)
    print("\nLLM Connectivity:")
    llm_status = validate_llm_connectivity()
    if llm_status.is_healthy():
        print(f"✓ LLM: {llm_status.model} - {llm_status.message}")
    elif llm_status.status == "unconfigured":
        print(f"✗ LLM: UNCONFIGURED - {llm_status.message}")
        all_healthy = False
    else:
        print(f"✗ LLM: ERROR - {llm_status.message}")
        all_healthy = False
    
    # Check 5: API Server
    print("\nAPI Server:")
    try:
        response = requests.get("http://localhost:8000/", timeout=2)
        if response.status_code == 200:
            print(f"✓ API Server: Running at http://localhost:8000")
        else:
            print(f"⚠ API Server: Status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ API Server: Not running (optional)")
    except Exception as e:
        print(f"⚠ API Server: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    if all_healthy:
        print("✓ All critical systems healthy")
        return 0
    else:
        print("✗ Some critical systems need attention")
        return 1


def cmd_status(args) -> int:
    """
    Show current DTL system status dashboard.
    Visualizes:
    1. Control Plane (Ledger, Engines, Stores)
    2. Agent Execution Zone (Strategist, Researcher, Reporter)
    3. Self-Improvement Loop (MetaAnalyst, Governance)
    """
    
    def _check_file(path_str):
        p = Path(PROJECT_ROOT) / path_str
        return "[INSTALLED]" if p.exists() else "[MISSING]"
        
    def _check_store(path_str):
        p = Path(PROJECT_ROOT) / path_str
        return "[LOCKED]" if p.exists() else "[MISSING]"
        
    def _check_ledger():
        p = Path(PROJECT_ROOT) / "data" / "run_ledger.jsonl"
        return "[ACTIVE]" if p.exists() else "[MISSING]"

    print("\nDTL v2.0 Ecosystem Status")
    print("=========================")

    print("\n[ Deterministic Control Plane ]")
    print(f"  - Run Ledger:       {_check_ledger()} (Found)")
    print(f"  - RunScore Engine:  [READY] (Store: data/run_scores)")
    print(f"  - RunScore Store:   {_check_store('data/run_scores')} (Append-Only)")

    print("\n[ Agent Execution Zone (Read-Only) ]")
    print(f"  - Strategist:       {_check_file('src/agents/strategist.py')} (src/agents/strategist.py)")
    print(f"  - Researcher:       {_check_file('src/agents/researcher.py')} (src/agents/researcher.py)")
    print(f"  - Reporter:         {_check_file('src/agents/reporter.py')} (src/agents/reporter.py)")
    print("  * NO WRITE AUTHORITY * Codebase modification is impossible.")

    print("\n[ Self-Improvement Loop ]")
    print(f"  - MetaAnalyst:      {_check_file('src/agents/meta_analyst.py')} (src/agents/meta_analyst.py)")
    print(f"  - Improvement Store:{_check_store('data/improvement_packets')} (Append-Only)")

    print("\n[ Governance ]")
    print("  - Human Gate:       [SECURE] (CLI-based ACK/Apply)")
    print("  - Patch Policy:     [STRICT] (Hash Validation + ACK Required)")
    print("")
    
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



def cmd_score(args) -> int:
    """Compute and write RunScore."""
    from src.control_plane.run_score import RunScoreEngine
    
    engine = RunScoreEngine(str(PROJECT_ROOT))
    
    # If TS not provided, try to find it or default to now?
    # Logic implies strictness. 
    ts = args.run_ts
    if not ts:
        # Try to find run file to get ts
        data = engine._load_run_data(args.run_id)
        if data and "timestamp" in data:
            ts = data["timestamp"]
        else:
            ts = datetime.utcnow().isoformat()
            
    try:
        score = engine.compute_run_score(args.run_id, ts)
        print(f"RunScore Computed:")
        print(f"  ID: {score['run_score_id']}")
        print(f"  Total Score: {score['scores']['total_score']}")
        print(f"  Process Quality: {score['scores']['process_quality_score']}")
        print(f"  Safety Posture: {score['scores']['safety_posture_score']}")
        print(f"  Outcome Proxy: {score['scores']['outcome_proxy_score']}")
        return 0
    except Exception as e:
        print(f"Error computing score: {e}")
        return 1


def cmd_propose_improvements(args) -> int:
    """Run MetaAnalyst to propose improvements."""
    from src.agents.meta_analyst import MetaAnalystAgent
    
    agent = MetaAnalystAgent(str(PROJECT_ROOT))
    run_ids = args.run_ids.split(',')
    
    try:
        envelope = agent.process(run_ids, lookback_days=int(args.lookback_days))
        packet = envelope['payload']
        print(f"Improvement Packet Generated:")
        print(f"  Packet ID: {packet['packet_id']}")
        print(f"  Content Hash: {packet['packet_content_hash']}")
        print(f"  Findings: {len(packet['findings'])}")
        print(f"  Recommendations: {len(packet['recommendations'])}")
        return 0
    except Exception as e:
        print(f"Error proposing improvements: {e}")
        return 1


def cmd_ack(args) -> int:
    """Generate ACK token for a packet."""
    from src.control_plane.human_approval_gate import HumanApprovalGate
    
    gate = HumanApprovalGate(str(PROJECT_ROOT))
    try:
        token = gate.create_ack(args.packet_id, args.packet_hash)
        print(f"ACK Token Generated for {args.packet_id}:")
        print(f"{token}")
        print("WARNING: This token is shown only once. Copy it now.")
        return 0
    except Exception as e:
        print(f"Error generating ACK: {e}")
        return 1


def cmd_apply(args) -> int:
    """Validate ACK and generate patch proposal."""
    from src.control_plane.human_approval_gate import HumanApprovalGate
    from src.control_plane.improvement_store import ImprovementStore

def cmd_apply(args):
    """
    Validates ACK and generates Patch Proposal file.
    Strict Sequence:
    1. Load Packet
    2. Recompute Hash
    3. Verify Hash matches Request
    4. Validate ACK
    """
    gate = HumanApprovalGate(PROJECT_ROOT)
    store = ImprovementStore(str(Path(PROJECT_ROOT) / "data" / "improvement_packets"))
    
    packet_id = args.packet_id
    provided_hash = args.packet_hash
    ack_token = args.ack_token
    
    # 1. Load Packet
    # We need to find the packet. Currently store.read uses ID.
    packet = store.read(packet_id)
    if not packet:
        print(f"Error: Packet {packet_id} not found.")
        sys.exit(1)
        
    # 2. Recompute Content Hash (Canonical)
    # The packet on disk has 'packet_id' and 'packet_content_hash'.
    # We must exclude them to get the content hash.
    # Note: If the file was tampered with, this recomputed hash will differ from what the operator 'thought' they signed (if they verified independently) 
    # OR it will differ from the 'packet_content_hash' field in the file (if we trusted that, which we don't for validation).
    
    # Actually, we compare the recomputed hash against the hash passed in the CLI (which matches the ACK).
    
    recomputed_hash_hex = compute_sha256_hash(packet, exclude_keys=["packet_id", "packet_content_hash"])
    recomputed_content_hash = f"sha256:{recomputed_hash_hex}"
    
    # 3. Verify Hash Matches Request/ACK
    if recomputed_content_hash != provided_hash:
        print(f"CRITICAL SECURITY FAILURE: Computed hash of packet {packet_id} on disk does not match the provided hash.")
        print(f"Disk Computed: {recomputed_content_hash}")
        print(f"Provided/ACKd: {provided_hash}")
        print("This implies the packet file has been tampered with or you are ACKing the wrong packet.")
        sys.exit(1)
        
    print(f"Packet Integrity Verified: {recomputed_content_hash}")

    # 4. Validate ACK
    if not gate.validate_ack(packet_id, recomputed_content_hash, ack_token):
        print("Error: Invalid ACK token for this packet/hash combination.")
        sys.exit(1)
        
    print("ACK Validated. Generating Patch Proposal...")
    
    # Generate Patch Proposal
    # Metadata Header
    ack_token_hash = hashlib.sha256(bytes.fromhex(ack_token)).hexdigest()
    
    today = datetime.now(timezone.utc)
    
    header = f"""---
packet_id: {packet_id}
packet_content_hash: {recomputed_content_hash}
ack_token_hash_prefix: {ack_token_hash[:8]}
generated_at: {today.isoformat()}
generated_by: dtl_cli
---

"""
    
    # Content
    content = []
    content.append(f"# Patch Proposal for {packet_id}")
    content.append(f"Summary: {packet.get('summary', 'No summary')}")
    content.append("\n## Recommendations")
    for r in packet.get("recommendations", []):
        content.append(f"- {r}")
        
    content.append("\n## Applied Changes (Simulated)")
    content.append("No automatic changes applied. Use this file as a guide.")
    
    full_content = header + "\n".join(content)
    
    # Write to data/patch_proposals/YYYY/MM/DD/PATCH-<id>.md
    today = datetime.now(timezone.utc)
    pp_dir = Path(PROJECT_ROOT) / "data" / "patch_proposals" / today.strftime("%Y/%m/%d")
    pp_dir.mkdir(parents=True, exist_ok=True)
    pp_file = pp_dir / f"PATCH-{packet_id}.md"
    
    with open(pp_file, 'w') as f:
        f.write(full_content)
        
    print(f"Patch Proposal written to: {pp_file}")
    print("ACTION REQUIRED: Review and apply manually.")


# =============================================================================
# Content Ingestion Commands
# =============================================================================

def cmd_ingest(args) -> int:
    """Ingest content from URL or queue file."""
    from src.agents.curator import CuratorAgent
    from src.content.store import ContentStore
    
    store = ContentStore()
    curator = CuratorAgent(content_store=store, dry_run=args.dry_run)
    
    # Process from queue file
    if args.from_inbox:
        inbox_path = Path(args.from_inbox)
        if not inbox_path.exists():
            print(f"Error: Inbox file not found: {inbox_path}")
            return 1
        
        print(f"Processing inbox: {inbox_path}")
        results = curator.process_queue(inbox_path)
        
        success_count = sum(1 for r in results if r["result"].get("status") == "ingested")
        print(f"\nProcessed {len(results)} URLs, {success_count} ingested")
        
        for r in results:
            status = r["result"].get("status", "error")
            if status == "ingested":
                entry = r["result"]["content_entry"]
                print(f"  ✓ {entry['id']}: {entry['title'][:50]}")
            elif status == "duplicate":
                print(f"  ⊘ {r['url'][:50]}... (duplicate)")
            else:
                print(f"  ✗ {r['url'][:50]}... ({r['result'].get('error', 'unknown error')})")
        
        return 0
    
    # Process single URL
    url = args.url
    if not url:
        # Try reading from stdin
        if not sys.stdin.isatty():
            url = sys.stdin.read().strip()
    
    if not url:
        print("Error: No URL provided. Use: dtl ingest <url> or dtl ingest --from-inbox <path>")
        return 1
    
    # Parse manual tags
    manual_tags = []
    if args.tags:
        manual_tags = [t.strip() for t in args.tags.split(",")]
    
    print(f"Ingesting: {url}")
    if manual_tags:
        print(f"Tags: {manual_tags}")
    
    result = curator.process({
        "url": url,
        "manual_tags": manual_tags,
    })
    
    payload = result.payload
    status = payload.get("status")
    
    if status == "ingested":
        entry = payload["content_entry"]
        print(f"\n✓ Ingested: {entry['id']}")
        print(f"  Title: {entry['title']}")
        print(f"  Summary: {entry['summary'][:200]}...")
        print(f"  Categories: {entry['categories']}")
        print(f"  Relevance: {entry['relevance_score']:.2f}")
        if entry["action_items"]:
            print(f"  Action Items: {len(entry['action_items'])}")
            for item in entry["action_items"][:3]:
                print(f"    - [{item['type']}] {item['description'][:60]}...")
        return 0
    elif status == "duplicate":
        print(f"\n⊘ Already ingested as: {payload.get('existing_id')}")
        return 0
    else:
        print(f"\n✗ Error: {payload.get('error', 'Unknown error')}")
        return 1


def cmd_browse(args) -> int:
    """Browse content by status or category."""
    from src.content.store import ContentStore
    from src.content.schemas import ContentStatus
    
    store = ContentStore()
    
    if args.category:
        entries = store.list_by_category(args.category, limit=args.limit)
        print(f"\nContent in category '{args.category}':")
    elif args.status:
        try:
            status = ContentStatus(args.status)
        except ValueError:
            print(f"Error: Invalid status '{args.status}'")
            print(f"Valid statuses: {[s.value for s in ContentStatus]}")
            return 1
        entries = store.list_by_status(status, limit=args.limit)
        print(f"\nContent with status '{args.status}':")
    else:
        # Default: show unread
        entries = store.list_by_status(ContentStatus.UNREAD, limit=args.limit)
        print("\nUnread content:")
    
    if not entries:
        print("  (none)")
        return 0
    
    for entry in entries:
        rel_bar = "█" * int(entry.relevance_score * 5) + "░" * (5 - int(entry.relevance_score * 5))
        print(f"\n  [{entry.id}] {entry.title[:60]}")
        print(f"    URL: {entry.url[:70]}")
        print(f"    Categories: {', '.join(entry.categories)}")
        print(f"    Relevance: {rel_bar} ({entry.relevance_score:.2f})")
        print(f"    Actions: {len(entry.action_items)} | Status: {entry.status.value}")
    
    return 0


def cmd_search(args) -> int:
    """Full-text search across content."""
    from src.content.store import ContentStore
    
    query = args.query
    if not query:
        print("Error: No search query provided")
        return 1
    
    store = ContentStore()
    entries = store.search(query, limit=args.limit)
    
    print(f"\nSearch results for '{query}':")
    
    if not entries:
        print("  No results found")
        return 0
    
    for entry in entries:
        print(f"\n  [{entry.id}] {entry.title[:60]}")
        print(f"    {entry.summary[:100]}...")
        print(f"    Categories: {', '.join(entry.categories)}")
    
    return 0


def cmd_insights(args) -> int:
    """Show action items from ingested content."""
    from src.content.store import ContentStore
    
    store = ContentStore()
    
    action_type = args.type if args.type else None
    items = store.get_action_items(action_type=action_type, limit=args.limit)
    
    if action_type:
        print(f"\nAction items ({action_type}):")
    else:
        print("\nAll action items:")
    
    if not items:
        print("  (none)")
        return 0
    
    for entry, action in items:
        print(f"\n  [{action.action_type.value.upper()}] P{action.priority}")
        print(f"    {action.description}")
        print(f"    From: {entry.title[:50]} ({entry.id})")
        if action.related_files:
            print(f"    Files: {', '.join(action.related_files)}")
    
    return 0


def cmd_content_status(args) -> int:
    """Show content store statistics."""
    from src.content.store import ContentStore
    
    store = ContentStore()
    counts = store.count_by_status()
    
    print("\nContent Store Status:")
    total = sum(counts.values())
    print(f"  Total entries: {total}")
    for status, count in sorted(counts.items()):
        print(f"    {status}: {count}")
    
    return 0


# =============================================================================
# Datamart Commands
# =============================================================================

def cmd_datamart_sync(args) -> int:
    """Sync datamart bundles to a destination folder (e.g., Google Drive)."""
    import shutil
    from src.content.datamart_bundler import DatamartBundler
    
    bundler = DatamartBundler()
    
    # Default destination
    dest_base = Path(args.dest) if args.dest else Path.home() / "Google Drive" / "NotebookLM"
    
    if args.topic_id:
        # Sync single topic
        topics = [args.topic_id]
    else:
        # Sync all active bundles
        bundles = bundler.list_bundles(include_archived=False)
        topics = [b.topic_id for b in bundles]
    
    if not topics:
        print("No datamart bundles found to sync.")
        return 0
    
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Datamart Sync")
    print(f"Destination: {dest_base}")
    print(f"Topics: {len(topics)}")
    print()
    
    synced_count = 0
    for topic_id in topics:
        summary = bundler.get_sync_summary(topic_id)
        if "error" in summary:
            print(f"  ✗ {topic_id}: {summary['error']}")
            continue
        
        src_path = Path(summary["bundle_path"])
        dest_path = dest_base / topic_id
        
        print(f"  {topic_id}:")
        print(f"    Version: v{summary['version']} | Sources: {summary['source_count']}")
        print(f"    Fingerprint: {summary['fingerprint'][:32]}...")
        print(f"    Files: {len(summary['files'])}")
        
        if args.dry_run:
            print(f"    → Would sync to: {dest_path}")
        else:
            # Create destination and copy files
            dest_path.mkdir(parents=True, exist_ok=True)
            (dest_path / "sources").mkdir(exist_ok=True)
            
            for file_rel in summary["files"]:
                src_file = src_path / file_rel
                dst_file = dest_path / file_rel
                if src_file.exists():
                    shutil.copy2(src_file, dst_file)
            
            print(f"    ✓ Synced to: {dest_path}")
            synced_count += 1
    
    print()
    if args.dry_run:
        print(f"Dry run complete. {len(topics)} bundle(s) would sync.")
    else:
        print(f"Sync complete. {synced_count} bundle(s) synced.")
    
    return 0


def cmd_datamarts(args) -> int:
    """List all datamart bundles."""
    from src.content.datamart_bundler import DatamartBundler
    
    bundler = DatamartBundler()
    bundles = bundler.list_bundles(include_archived=args.include_archived)
    
    print("\nDatamart Bundles:")
    
    if not bundles:
        print("  (none)")
        return 0
    
    for b in bundles:
        status_icon = "📦" if b.status == "active" else "📁"
        print(f"\n  {status_icon} [{b.topic_id}] {b.topic_name}")
        print(f"     Version: v{b.version} | Sources: {b.source_count}")
        print(f"     Tags: {', '.join(b.tags) if b.tags else '(none)'}")
        print(f"     Updated: {b.updated_at[:10]}")
    
    return 0


def cmd_datamart_show(args) -> int:
    """Show details for a specific datamart bundle."""
    from src.content.datamart_bundler import DatamartBundler
    
    bundler = DatamartBundler()
    manifest = bundler.read_manifest(args.topic_id)
    
    if not manifest:
        print(f"Error: Bundle not found: {args.topic_id}")
        return 1
    
    print(f"\nDatamart: {manifest.topic_name}")
    print(f"  Topic ID: {manifest.topic_id}")
    print(f"  Bundle ID: {manifest.bundle_id}")
    print(f"  Version: v{manifest.version}")
    print(f"  Status: {manifest.status}")
    print(f"  Fingerprint: {manifest.fingerprint}")
    print(f"  Created: {manifest.created_at}")
    print(f"  Updated: {manifest.updated_at}")
    
    if manifest.parent_topic_id:
        print(f"  Parent: {manifest.parent_topic_id}")
    
    if manifest.tags:
        print(f"  Tags: {', '.join(manifest.tags)}")
    
    print(f"\n  Sources ({manifest.source_count}):")
    for s in manifest.sources[:10]:  # Limit to 10
        print(f"    - [{s.content_id}] {s.title[:50]}")
        print(f"      Relevance: {s.relevance_score:.2f} | Added: {s.added_at[:10]}")
    
    if manifest.source_count > 10:
        print(f"    ... and {manifest.source_count - 10} more")
    
    return 0


def cmd_datamart_create(args) -> int:
    """Create a new datamart bundle."""
    import re
    from src.content.datamart_bundler import DatamartBundler
    
    topic_id = args.topic_id
    
    # Validate topic_id format
    if not re.match(r'^[a-z0-9-]+$', topic_id):
        print("Error: Topic ID must be lowercase letters, numbers, and hyphens only")
        return 1
    
    bundler = DatamartBundler()
    
    if bundler.bundle_exists(topic_id):
        print(f"Error: Bundle already exists: {topic_id}")
        return 1
    
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    
    manifest = bundler.create_bundle(
        topic_id=topic_id,
        topic_name=args.name,
        tags=tags,
    )
    
    print(f"\n✓ Created datamart bundle:")
    print(f"  Topic ID: {manifest.topic_id}")
    print(f"  Name: {manifest.topic_name}")
    print(f"  Bundle ID: {manifest.bundle_id}")
    if tags:
        print(f"  Tags: {', '.join(tags)}")
    
    return 0


def cmd_datamart_approve(args) -> int:
    """Approve a pending datamart topic."""
    import json
    
    registry_path = Path(PROJECT_ROOT) / "config" / "datamart_registry.json"
    if not registry_path.exists():
        print("Error: Registry not found")
        return 1
        
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    topic_id = args.topic_id
    if topic_id not in registry.get("topics", {}):
        print(f"Error: Topic '{topic_id}' not found in registry")
        return 1
    
    topic = registry["topics"][topic_id]
    if topic.get("status") == "active":
        print(f"Topic '{topic_id}' is already active.")
        return 0
    
    # Approve
    topic["status"] = "active"
    topic["approved_at"] = datetime.now(timezone.utc).isoformat()
    
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=4)
        
    print(f"✓ Topic '{topic_id}' approved and activated.")
    return 0


def cmd_datamart_rebuild(args) -> int:
    """Rebuild a datamart bundle from source truth."""
    from src.content.datamart_bundler import DatamartBundler
    from src.content.store import ContentStore
    
    topic_id = args.topic_id
    bundler = DatamartBundler()
    store = ContentStore()
    
    if not bundler.bundle_exists(topic_id):
        print(f"Error: Bundle '{topic_id}' not found.")
        return 1
    
    print(f"Rebuilding bundle: {topic_id}")
    
    # 1. Read current manifest to get source IDs
    manifest = bundler.read_manifest(topic_id)
    source_ids = [s.content_id for s in manifest.sources]
    print(f"  Found {len(source_ids)} sources in manifest.")
    
    # 2. Fetch fresh content from Store
    refreshed_sources = []
    missing_ids = []
    
    for cid in source_ids:
        entry = store.read(cid)
        if not entry:
            missing_ids.append(cid)
            continue
            
        # Re-construct DatamartSource from fresh ContentEntry
        from src.content.datamart_bundler import DatamartSource
        ds = DatamartSource(
            content_id=entry.id,
            url=entry.url,
            title=entry.title,
            relevance_score=entry.relevance_score,
            summary=entry.summary,
            added_at=entry.created_at, # Keep original added_at or update? logic implies freshness
            categories=entry.categories
        )
        # We need to preserve the original added_at if possible, strictly "rebuild" might imply using current data
        # For this implementation, we use current store data.
        refreshed_sources.append((ds, entry.raw_content))
    
    if missing_ids:
        print(f"  Warning: {len(missing_ids)} sources missing from ContentStore (skipping): {missing_ids}")
    
    # 3. Re-write bundle
    # We use internal methods or just re-add sources? 
    # Better to wipe sourcesdir and re-add.
    # Bundler doesn't expose "wipe".
    # We can use add_source to overwrite.
    
    updated_count = 0
    for ds, raw_content in refreshed_sources:
        bundler.add_source(
            topic_id=topic_id,
            content_id=ds.content_id,
            url=ds.url,
            title=ds.title,
            relevance_score=ds.relevance_score,
            summary=ds.summary,
            categories=ds.categories,
            raw_content=raw_content
        )
        updated_count += 1
        
    print(f"  ✓ Refreshed {updated_count} sources.")
    
    # 4. Verify fingerprint
    new_manifest = bundler.read_manifest(topic_id)
    print(f"  New Fingerprint: {new_manifest.fingerprint}")
    
    return 0


def cmd_datamart_health(args) -> int:
    """Print a Datamart Health Report."""
    from pathlib import Path
    from datetime import datetime, timezone, timedelta
    import re
    
    from src.content.datamart_bundler import DatamartBundler
    from src.content.store import ContentStore
    
    PROJECT_ROOT = Path(__file__).parent.parent
    
    print("=" * 60)
    print("            DATAMART HEALTH REPORT")
    print(f"            Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    
    # 1. Load registry and count by status
    registry_path = PROJECT_ROOT / "config" / "datamart_registry.json"
    registry = {}
    if registry_path.exists():
        with open(registry_path) as f:
            registry = json.load(f).get("topics", {})
    
    status_counts = {"active": 0, "pending": 0, "archived": 0}
    for topic_id, meta in registry.items():
        status = meta.get("status", "unknown")
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts[status] = status_counts.get(status, 0) + 1
    
    print("\n[1] TOPIC STATUS")
    print(f"    Active:   {status_counts.get('active', 0)}")
    print(f"    Pending:  {status_counts.get('pending', 0)}")
    print(f"    Archived: {status_counts.get('archived', 0)}")
    
    # 2. Last Sync Time & Outcome
    log_path = PROJECT_ROOT / "logs" / "datamart_sync.log"
    last_sync_time = "Never"
    last_sync_outcome = "Unknown"
    
    if log_path.exists():
        lines = log_path.read_text().strip().split("\n")
        for line in reversed(lines):
            if "Sync Complete. Success" in line:
                last_sync_outcome = "SUCCESS"
                match = re.search(r"\[(.*?)\]", line)
                if match:
                    last_sync_time = match.group(1)
                break
            elif "Sync Failed" in line:
                last_sync_outcome = "FAILED"
                match = re.search(r"\[(.*?)\]", line)
                if match:
                    last_sync_time = match.group(1)
                break
    
    print("\n[2] LAST SYNC")
    print(f"    Time:    {last_sync_time}")
    print(f"    Outcome: {last_sync_outcome}")
    
    # 3. Top 10 Topics by Source Count
    bundler = DatamartBundler()
    topic_source_counts = []
    
    datamarts_dir = bundler.base_path
    if datamarts_dir.exists():
        for topic_dir in datamarts_dir.iterdir():
            if topic_dir.is_dir():
                manifest = bundler.read_manifest(topic_dir.name)
                if manifest:
                    topic_source_counts.append((topic_dir.name, len(manifest.sources)))
    
    topic_source_counts.sort(key=lambda x: x[1], reverse=True)
    
    print("\n[3] TOP TOPICS BY SOURCE COUNT")
    if topic_source_counts:
        for i, (tid, count) in enumerate(topic_source_counts[:10], 1):
            print(f"    {i:2}. {tid}: {count} sources")
    else:
        print("    (No bundles found)")
    
    # 4. Fingerprint Mismatch Check
    print("\n[4] FINGERPRINT VALIDATION")
    mismatch_count = 0
    for topic_dir in (datamarts_dir.iterdir() if datamarts_dir.exists() else []):
        if topic_dir.is_dir():
            manifest = bundler.read_manifest(topic_dir.name)
            if manifest:
                # Recalculate fingerprint
                sources_dir = topic_dir / "sources"
                current_hash = ""
                if sources_dir.exists():
                    file_hashes = []
                    for f in sorted(sources_dir.glob("*.md")):
                        file_hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
                    if file_hashes:
                        current_hash = hashlib.sha256(":".join(file_hashes).encode()).hexdigest()[:16]
                
                if current_hash and manifest.fingerprint != current_hash:
                    mismatch_count += 1
                    print(f"    MISMATCH: {topic_dir.name} (stored={manifest.fingerprint}, actual={current_hash})")
    
    if mismatch_count == 0:
        print("    All fingerprints valid ✓")
    else:
        print(f"    {mismatch_count} mismatch(es) detected!")
    
    # 5. NOTIFY Count (Last 7 Days)
    store = ContentStore()
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    notify_count = 0
    planner_task_count = 0
    
    # Query content store for recent entries (approximate: last 1000)
    all_entries = store.list_entries(limit=1000)
    for entry in all_entries:
        try:
            ingested = datetime.fromisoformat(entry.ingested_at.replace("Z", "+00:00"))
            if ingested >= seven_days_ago:
                # Check if NOTIFY was triggered (check deep_analysis or routing)
                if hasattr(entry, 'deep_analysis') and entry.deep_analysis:
                    actions = entry.deep_analysis.system_actions or []
                    if 'NOTIFY' in [a.value if hasattr(a, 'value') else a for a in actions]:
                        notify_count += 1
                    route = entry.deep_analysis.route_destination
                    if route and hasattr(route, 'value') and route.value == 'PLANNER_TASK':
                        planner_task_count += 1
                    elif route == 'PLANNER_TASK':
                        planner_task_count += 1
        except Exception:
            continue
    
    print("\n[5] ACTIVITY (LAST 7 DAYS)")
    print(f"    NOTIFY triggers:    {notify_count}")
    print(f"    Planner tasks:      {planner_task_count}")
    
    print("\n" + "=" * 60)
    print("Report complete.")
    
    return 0



def main():
    parser = argparse.ArgumentParser(
        prog='dtl',
        description='DTL v2.0 - Runner Contract CLI'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Execute a DTL run')
    run_parser.add_argument('--mode', choices=['mock', 'live'], default='mock', help='Run mode')
    run_parser.add_argument('--run_id', help='Explicit run ID')
    run_parser.add_argument('--policy_snapshot', help='Path to policy snapshot JSON')
    run_parser.add_argument('--job', choices=['quant_premarket', 'realitycheck_eod', 'quant_intraday'], help='Job preset')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check system health (databases, LLM, API)')
    
    # Validate-bundle command
    validate_parser = subparsers.add_parser('validate-bundle', help='Validate a CommitBundle')
    validate_parser.add_argument('bundle_path', help='Path to bundle JSON')
    validate_parser.add_argument('--kill_switches', help='Comma-separated active kill switches')
    validate_parser.add_argument('--capabilities', help='Comma-separated allowed capabilities')
    validate_parser.add_argument('--evidence_store', default='data/evidence_store', help='Path to evidence store directory')
    validate_parser.add_argument('--prewrite_path', default='data/run_ledger/prewrite', help='Path to prewrite directory')

    # Score command
    score_parser = subparsers.add_parser('score', help='Compute and write RunScore')
    score_parser.add_argument('--run_id', required=True, help='Run ID to score')
    score_parser.add_argument('--run_ts', help='Run timestamp (ISO)')
    
    # Propose Improvements command
    propose_parser = subparsers.add_parser('propose-improvements', help='Run MetaAnalyst')
    propose_parser.add_argument('--run_ids', required=True, help='Comma-separated Run IDs')
    propose_parser.add_argument('--lookback_days', default=7, help='Lookback days')

    # ACK command
    ack_parser = subparsers.add_parser('ack', help='Generate ACK token')
    ack_parser.add_argument('--packet_id', required=True, help='Packet ID to ACK')
    ack_parser.add_argument('--packet_hash', required=True, help='Packet content hash')

    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Validate ACK and generate patch proposal')
    apply_parser.add_argument('--packet_id', required=True, help='Packet ID')
    apply_parser.add_argument('--packet_hash', required=True, help='Packet content hash')
    apply_parser.add_argument('--ack_token', required=True, help='ACK token')
    
    # ==========================================================================
    # Content Ingestion Commands
    # ==========================================================================
    
    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest content from URL')
    ingest_parser.add_argument('url', nargs='?', help='URL to ingest')
    ingest_parser.add_argument('--tags', help='Comma-separated tags')
    ingest_parser.add_argument('--from-inbox', dest='from_inbox', help='Process URLs from inbox file')
    ingest_parser.add_argument('--dry-run', dest='dry_run', action='store_true', help='Analyze without storing')
    
    # Browse command
    browse_parser = subparsers.add_parser('browse', help='Browse ingested content')
    browse_parser.add_argument('--status', help='Filter by status (unread, read, archived, etc.)')
    browse_parser.add_argument('--category', help='Filter by category')
    browse_parser.add_argument('--limit', type=int, default=20, help='Max results')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search ingested content')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=20, help='Max results')
    
    # Insights command
    insights_parser = subparsers.add_parser('insights', help='Show action items from content')
    insights_parser.add_argument('--type', choices=['enhancement', 'correction', 'research', 'documentation', 'idea'], help='Filter by action type')
    insights_parser.add_argument('--limit', type=int, default=20, help='Max results')
    
    # Content-status command
    content_status_parser = subparsers.add_parser('content-status', help='Show content store statistics')
    
    # ==========================================================================
    # Datamart Commands
    # ==========================================================================
    
    # Datamart sync command
    sync_parser = subparsers.add_parser('datamart-sync', help='Sync datamart bundles to Drive folder')
    sync_parser.add_argument('topic_id', nargs='?', help='Topic ID to sync (all if not specified)')
    sync_parser.add_argument('--dry-run', dest='dry_run', action='store_true', help='Preview sync without copying files')
    sync_parser.add_argument('--dest', help='Destination folder path (defaults to ~/Google Drive/NotebookLM)')
    
    # Datamart list command
    bundles_parser = subparsers.add_parser('datamarts', help='List all datamart bundles')
    bundles_parser.add_argument('--include-archived', dest='include_archived', action='store_true', help='Include archived bundles')
    
    # Datamart show command
    bundle_parser = subparsers.add_parser('datamart', help='Show datamart bundle details')
    bundle_parser.add_argument('topic_id', help='Topic ID to show')
    
    # Datamart create command
    create_dm_parser = subparsers.add_parser('datamart-create', help='Create a new datamart bundle')
    create_dm_parser.add_argument('topic_id', help='Topic ID (lowercase, hyphens only)')
    create_dm_parser.add_argument('--name', required=True, help='Display name for the topic')
    create_dm_parser.add_argument('--tags', help='Comma-separated tags')

    # Datamart approve command
    approve_dm_parser = subparsers.add_parser('datamart-approve', help='Approve a pending datamart topic')
    approve_dm_parser.add_argument('topic_id', help='Topic ID to approve')

    # Datamart rebuild command
    rebuild_dm_parser = subparsers.add_parser('datamart-rebuild', help='Rebuild bundle from source of truth')
    rebuild_dm_parser.add_argument('topic_id', help='Topic ID to rebuild')

    # Datamart health command
    health_parser = subparsers.add_parser('datamart-health', help='Print weekly datamart health report')


    
    args = parser.parse_args()
    
    if args.command == 'run':
        return cmd_run(args)
    elif args.command == 'status':
        return cmd_status(args)
    elif args.command == 'validate-bundle':
        return cmd_validate_bundle(args)
    elif args.command == 'score':
        return cmd_score(args)
    elif args.command == 'propose-improvements':
        return cmd_propose_improvements(args)
    elif args.command == 'ack':
        return cmd_ack(args)
    elif args.command == 'apply':
        return cmd_apply(args)
    elif args.command == 'ingest':
        return cmd_ingest(args)
    elif args.command == 'browse':
        return cmd_browse(args)
    elif args.command == 'search':
        return cmd_search(args)
    elif args.command == 'insights':
        return cmd_insights(args)
    elif args.command == 'content-status':
        return cmd_content_status(args)
    elif args.command == 'datamart-sync':
        return cmd_datamart_sync(args)
    elif args.command == 'datamarts':
        return cmd_datamarts(args)
    elif args.command == 'datamart':
        return cmd_datamart_show(args)
    elif args.command == 'datamart-create':
        return cmd_datamart_create(args)
    elif args.command == 'datamart-approve':
        return cmd_datamart_approve(args)
    elif args.command == 'datamart-rebuild':
        return cmd_datamart_rebuild(args)
    elif args.command == 'datamart-health':
        return cmd_datamart_health(args)
    elif args.command == 'health':
        return cmd_health(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())

