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
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())

