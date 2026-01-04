
import json
import hashlib
import base64
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.control_plane.run_score_store import RunScoreStore
from src.utils.hashing import compute_sha256_hash

# Constants
TARGET_EVIDENCE_DENSITY = 5
DEFAULT_OUTCOME_SCORE = 50

class RunScoreEngine:
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.ledger_path = self.workspace_root / "data" / "run_ledger.jsonl"
        self.evidence_path = self.workspace_root / "data" / "evidence_store.json"
        self.dtl_runs_dir = self.workspace_root / "data" / "dtl_runs"
        self.degraded_log_path = self.workspace_root / "logs" / "degraded_mode.log"
        self.reality_check_dir = self.workspace_root / "data" / "realitycheck"
        
        self.store = RunScoreStore(str(self.workspace_root / "data" / "run_scores"))

    def compute_run_score(self, run_id: str, run_ts: str) -> Dict:
        """
        Computes deterministic run score and writes it to store.
        Returns the score dictionary.
        Idempotent: if score exists for this run_id+ts, returns existing.
        """
        # Mint Deterministic ID first to check existence
        # ID = base32(sha256(canonical_json({run_id, run_ts})))[:8]
        # Using canonical hash ensures we are robust.
        # Note: Previous impl was run_id + run_ts string concat.
        
        id_inputs = {"run_id": run_id, "run_ts": run_ts}
        sha_hex = compute_sha256_hash(id_inputs)
        sha_bytes = bytes.fromhex(sha_hex)
        
        b32 = base64.b32encode(sha_bytes).decode("utf-8")
        run_score_id = f"RUNSCORE-{b32[:8]}"
        
        # Check existence
        existing = self.store.read(run_score_id)
        if existing:
            return existing

        # 1. Load Data
        ledger_entries = self._load_ledger_for_run(run_id) # Not strictly used in formula but good for flags
        run_data = self._load_run_data(run_id)
        evidence_store = self._load_evidence_store()
        degraded_events = self._load_degraded_events(run_id)
        reality_check = self._load_reality_check(run_id)

        # 2. Extract Metrics
        
        # Flags
        # Heuristic: check ledger/logs for specific event types if not in run_data
        # For this implementation, we dig into run_data or calculation
        
        firewall_rejections = self._count_ledger_event(ledger_entries, "firewall_rejection")
        commit_gate_rejections = self._count_ledger_event(ledger_entries, "commit_gate_rejection")
        degraded_triggered = len(degraded_events) > 0
        
        # Evidence Metrics from Run Data (bundle)
        # Assuming run_data contains list of evidence_ids used
        evidence_ids = self._extract_evidence_ids(run_data)
        evidence_metrics = self._compute_evidence_metrics(evidence_ids, evidence_store)
        
        # 3. Compute Scores (Hybrid C)
        
        # A) Process Quality
        # evidence_fresh_rate = fresh / max(1, count)
        count = evidence_metrics["evidence_count"]
        fresh = evidence_metrics["evidence_fresh_count"]
        fresh_rate = fresh / max(1, count)
        
        # evidence_density = min(1.0, count / target_count)
        density = min(1.0, count / TARGET_EVIDENCE_DENSITY)
        
        # avg_trust_tier normalized (tier/5.0)
        avg_trust = evidence_metrics["avg_trust_tier"]
        avg_trust_norm = avg_trust / 5.0
        
        process_quality = round(100 * (0.5 * fresh_rate + 0.3 * density + 0.2 * avg_trust_norm))
        process_quality = max(0, min(100, int(process_quality)))

        # B) Safety Posture
        # start 100
        safety = 100
        if degraded_triggered:
            safety -= 25
        safety -= 10 * min(3, firewall_rejections) # cap penalty at 30 -> 3 rejections
        safety -= 10 * min(3, commit_gate_rejections) # cap penalty at 30
        
        stale_count = evidence_metrics["evidence_expired_count"]
        safety -= 5 * min(5, stale_count) # cap penalty at 25
        
        safety_posture = max(0, min(100, int(safety)))

        # C) Outcome Proxy
        if reality_check and "alignment_score" in reality_check:
            outcome_proxy = reality_check["alignment_score"]
            rc_available = True
            rc_notes = reality_check.get("notes", "Reality check available")
            rc_score = outcome_proxy
        else:
            outcome_proxy = DEFAULT_OUTCOME_SCORE
            rc_available = False
            rc_notes = "No realitycheck artifact found"
            rc_score = 0 # Placeholder for simple struct

        total_score = round(0.4 * outcome_proxy + 0.35 * process_quality + 0.25 * safety_posture)
        total_score = max(0, min(100, int(total_score)))

        # 4. Construct Artifact
        # ID is already computed at start
        
        score_doc = {
            "run_score_id": run_score_id,
            "run_id": run_id,
            "run_ts": run_ts,
            # bundle_hash optional
            "scores": {
                "outcome_proxy_score": int(outcome_proxy),
                "process_quality_score": int(process_quality),
                "safety_posture_score": int(safety_posture),
                "total_score": int(total_score)
            },
            "flags": {
                "degraded_triggered": degraded_triggered,
                "firewall_rejections": firewall_rejections,
                "commit_gate_rejections": commit_gate_rejections,
                "evidence_stale_count": stale_count
            },
            "evidence_metrics": evidence_metrics,
            "realitycheck_metrics": {
                "available": rc_available,
                "alignment_score": int(rc_score) if rc_available else 0,
                "notes": rc_notes
            },
            "computed_at": datetime.utcnow().isoformat() + "Z", # naive utc
            "version": "1.0.0"
        }

        # 5. Write to Store
        self.store.write(score_doc)
        
        return score_doc

    def _load_ledger_for_run(self, run_id: str) -> List[Dict]:
        matches = []
        if self.ledger_path.exists():
            with open(self.ledger_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("run_id") == run_id:
                            matches.append(entry)
                    except:
                        pass
        return matches

    def _load_run_data(self, run_id: str) -> Dict:
        # Check dtl_runs/RUN-ID.json
        p = self.dtl_runs_dir / f"{run_id}.json"
        if p.exists():
            with open(p, 'r') as f:
                return json.load(f)
        return {} # Empty if not found

    def _load_evidence_store(self) -> Dict:
        if self.evidence_path.exists():
            with open(self.evidence_path, 'r') as f:
                return json.load(f)
        return {}

    def _load_degraded_events(self, run_id: str) -> List[str]:
        # Dummy impl: check log file for line containing run_id
        events = []
        if self.degraded_log_path.exists():
            with open(self.degraded_log_path, 'r') as f:
                for line in f:
                    if run_id in line:
                         events.append(line)
        return events

    def _load_reality_check(self, run_id: str) -> Optional[Dict]:
        # Look for REALITY-run_id.json or similar in reality_check_dir
        # Assuming filename convention or content search
        # Since strict schema says alignment available or not, we start simple
        # Try finding file with run_id
        if not self.reality_check_dir.exists():
             return None
             
        for p in self.reality_check_dir.glob("*.json"):
            try:
                with open(p, 'r') as f:
                    d = json.load(f)
                    if d.get("run_id") == run_id:
                        return d
            except:
                pass
        return None

    def _count_ledger_event(self, entries: List[Dict], event_type: str) -> int:
        count = 0
        for e in entries:
            if e.get("event") == event_type or e.get("type") == event_type:
                count += 1
        return count

    def _extract_evidence_ids(self, run_data: Dict) -> List[str]:
        # Helper to find evidence refs in run output
        # run_data might be a bundle or envelope
        ids = []
        # Recursively search for evidence_refs or similar keys
        # Implementation depends on exact bundle structure
        # For v2.0 we assume a flat list or specific location. 
        # Attempting generic search key "evidence_refs" or "used_evidence"
        
        def search(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ["evidence_refs", "evidence_ids", "related_evidence"]:
                        if isinstance(v, list):
                            ids.extend(v)
                    else:
                        search(v)
            elif isinstance(obj, list):
                for i in obj:
                    search(i)
                    
        search(run_data)
        return list(set(ids))

    def _compute_evidence_metrics(self, ids: List[str], store: Dict) -> Dict:
        total = len(ids)
        if total == 0:
            return {
                "evidence_count": 0,
                "evidence_fresh_count": 0,
                "evidence_expired_count": 0,
                "avg_trust_tier": 0.0
            }
            
        fresh = 0
        expired = 0
        trust_sum = 0
        
        # We need "now" for freshness. 
        # Use simple heuristic: if 'expires' > now. 
        # Assuming store has 'items' dict or is dict of id->item
        data_map = store.get("items", {}) if "items" in store else store
        
        now_iso = datetime.utcnow().isoformat()
        
        for eid in ids:
            item = data_map.get(eid)
            if not item:
                continue
                
            # Trust Tier
            tier = item.get("trust_tier", "low")
            score = 1
            if tier == "med": score = 3
            if tier == "high": score = 5
            trust_sum += score
            
            # Freshness
            # Check created_at vs today, or explicit expires
            # If no expiry, assume fresh? Strictly: check logic.
            # Let's check 'expires' field
            expires = item.get("expires")
            if expires:
                if expires < now_iso:
                    expired += 1
                else:
                    fresh += 1
            else:
                # Default fresh if no expiry? Or stale?
                # "Freshness" usually implies recent.
                # Assuming fresh for this implementations
                fresh += 1

        return {
            "evidence_count": total,
            "evidence_fresh_count": fresh,
            "evidence_expired_count": expired,
            "avg_trust_tier": round(trust_sum / total, 2)
        }
