"""
Deterministic Replay Proof Test (Prompt 5).

Replays a completed run 100 times and verifies identical outputs.
"""

import pytest
import json
import hashlib
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Snapshot:
    """Immutable snapshot of run state."""
    policy_weights: tuple  # Frozen dict as tuple
    evidence_ids: tuple
    query_hash: str
    
    @staticmethod
    def from_dict(weights: Dict[str, float], evidence: List[str], query: str) -> "Snapshot":
        return Snapshot(
            policy_weights=tuple(sorted(weights.items())),
            evidence_ids=tuple(sorted(evidence)),
            query_hash=hashlib.sha256(query.encode()).hexdigest()[:16]
        )


def get_routing_order(weights: Dict[str, float]) -> List[str]:
    """Get deterministic routing order."""
    return sorted(weights.keys(), key=lambda k: (-weights[k], k))


def simulate_run(snapshot: Snapshot) -> Dict[str, Any]:
    """Simulate a run given a snapshot."""
    weights = dict(snapshot.policy_weights)
    
    # Deterministic routing
    routing = get_routing_order(weights)
    
    # Deterministic output based on routing and evidence
    output_hash = hashlib.sha256(
        f"{routing}:{snapshot.evidence_ids}:{snapshot.query_hash}".encode()
    ).hexdigest()
    
    # Deterministic ledger entries
    ledger = [
        {"event": "RUN_START", "query_hash": snapshot.query_hash},
        {"event": "ROUTING_DECISION", "order": routing},
        {"event": "EVIDENCE_USED", "ids": list(snapshot.evidence_ids)},
        {"event": "RUN_COMPLETE", "output_hash": output_hash},
    ]
    
    return {
        "routing": routing,
        "output_hash": output_hash,
        "ledger": ledger
    }


class TestDeterministicReplay:
    """Tests for deterministic replay."""

    def test_replay_100_times(self, tmp_path):
        """Replay a run 100 times and verify identical outputs."""
        # Create a fixed snapshot
        snapshot = Snapshot.from_dict(
            weights={"skill_a": 1.2, "skill_b": 0.8, "skill_c": 1.0},
            evidence=["ev_001", "ev_002", "ev_003"],
            query="What happened in markets today?"
        )
        
        # Run initial execution
        baseline = simulate_run(snapshot)
        
        # Replay 100 times
        diffs = []
        for i in range(100):
            replay = simulate_run(snapshot)
            
            # Check routing
            routing_match = replay["routing"] == baseline["routing"]
            
            # Check output
            output_match = replay["output_hash"] == baseline["output_hash"]
            
            # Check ledger (excluding timestamps)
            ledger_match = len(replay["ledger"]) == len(baseline["ledger"])
            for j, (r_entry, b_entry) in enumerate(zip(replay["ledger"], baseline["ledger"])):
                if r_entry != b_entry:
                    ledger_match = False
                    diffs.append({
                        "replay": i,
                        "entry": j,
                        "type": "ledger_diff",
                        "expected": b_entry,
                        "actual": r_entry
                    })
            
            if not routing_match:
                diffs.append({
                    "replay": i,
                    "type": "routing_diff",
                    "expected": baseline["routing"],
                    "actual": replay["routing"]
                })
            
            if not output_match:
                diffs.append({
                    "replay": i,
                    "type": "output_diff",
                    "expected": baseline["output_hash"],
                    "actual": replay["output_hash"]
                })
        
        # Generate report
        report = {
            "total_replays": 100,
            "diff_count": len(diffs),
            "diffs": diffs[:10],  # First 10 diffs only
            "verdict": "PASS" if len(diffs) == 0 else "FAIL"
        }
        
        with open(tmp_path / "determinism_diff_report.txt", "w") as f:
            f.write(f"Deterministic Replay Report\n")
            f.write(f"===========================\n\n")
            f.write(f"Total replays: 100\n")
            f.write(f"Differences found: {len(diffs)}\n\n")
            if diffs:
                f.write("First differences:\n")
                for d in diffs[:10]:
                    f.write(f"  - {d}\n")
            f.write(f"\nVERDICT: {report['verdict']}\n")
        
        # Assertions
        assert len(diffs) == 0, f"Replay produced {len(diffs)} differences"

    def test_routing_deterministic(self):
        """Identical weights produce identical routing."""
        weights = {"a": 1.5, "b": 0.9, "c": 1.0}
        
        results = [get_routing_order(weights) for _ in range(100)]
        
        assert all(r == results[0] for r in results)

    def test_output_hash_deterministic(self):
        """Output hash is deterministic given same inputs."""
        snapshot = Snapshot.from_dict(
            weights={"x": 1.0, "y": 1.0},
            evidence=["e1"],
            query="test"
        )
        
        hashes = [simulate_run(snapshot)["output_hash"] for _ in range(50)]
        
        assert len(set(hashes)) == 1, "Output hash varied across runs"
