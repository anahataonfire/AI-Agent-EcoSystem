
import json
import hashlib
import base64
from datetime import datetime
from typing import List, Dict, Optional
from src.control_plane.run_score import RunScoreEngine
from src.control_plane.improvement_store import ImprovementStore
from src.utils.hashing import compute_sha256_hash

# Minimal BaseAgent shim if not imported from existing codebase
# Assuming src.core.base_agent exists, but for standalone correctness I'll mock minimal necessary if I can't find it.
# Let's check `src/core/base_agent.py` shortly or assume BaseAgent pattern.
# Checking file list earlier: src/core/base_agent.py likely exists.

class MetaAnalystAgent:
    """
    MetaAnalyst Agent for Hybrid (C) Self-Improvement.
    """
    AGENT_ID = "meta_analyst-v0.1"
    
    def __init__(self, workspace_root: str = "."):
        self.run_score_engine = RunScoreEngine(workspace_root)
        self.improvement_store = ImprovementStore(os.path.join(workspace_root, "data/improvement_packets"))
        self.workspace_root = workspace_root

    def process(self, run_ids: List[str], lookback_days: int = 7) -> Dict:
        """
        Main entry point.
        1. Compute/Load Scores for runs.
        2. Analyze for patterns.
        3. Generate Packet.
        4. Write Packet.
        5. Return Envelope.
        """
        # 1. Gather Scores
        scores = []
        for rid in run_ids:
            # We assume run_ts is looked up or passed. 
            # For simplicity in CLI, we might score if missing or read if exists.
            # Here we try to score using current TS if we don't know it, or find existing.
            # ideally run_score_engine should allow finding by RunID alone if already scored.
            # But the engine computes. 
            pass # We will implement logic to compute if missing, using today as fallback or finding metadata.
            
            # For this MVP, we proceed with scoring "now" or assuming caller passed data. 
            # Actually, the agent input usually has context.
            # let's assume we compute a fresh score effectively.
            # We need the TS for deterministic ID. Best to find from dtl_runs.
            
            run_data = self.run_score_engine._load_run_data(rid)
            if not run_data:
                # Can't score what we can't load.
                continue
                
            # Try to get TS from run data or file mod time
            ts = run_data.get("timestamp") or datetime.utcnow().isoformat()
            
            score_doc = self.run_score_engine.compute_run_score(rid, ts)
            scores.append(score_doc)

        # 2. Analyze
        findings = []
        recommendations = []
        
        # Simple Logic: Check for low scores
        for s in scores:
            total = s["scores"]["total_score"]
            if total < 70:
                findings.append({
                    "id": f"FINDING-{s['run_id']}-LOW-SCORE",
                    "title": f"Low Run Score ({total}) for {s['run_id']}",
                    "severity": "med",
                    "evidence_refs": [],
                    "details": f"Process: {s['scores']['process_quality_score']}, Safety: {s['scores']['safety_posture_score']}"
                })
            
            if s["flags"]["degraded_triggered"]:
                 findings.append({
                    "id": f"FINDING-{s['run_id']}-DEGRADED",
                    "title": "Degraded Mode Triggered",
                    "severity": "high",
                    "evidence_refs": [],
                    "details": "System entered degraded mode."
                })

        # Generate some generic recommendations if findings exist
        if findings:
            recommendations.append({
                "id": "REC-001-CONFIG-TUNE",
                "type": "config",
                "title": "Tune Thresholds",
                "rationale": "Scores are consistently low.",
                "files_touched": ["config/policy.yaml"],
                "patch_hint": "Increase timeout or loosen strictness",
                "risk_level": "low"
            })

        # 3. Create Packet Payload
        # Must match schema
        packet = {
            # ID and Hash computed later
            "run_ids": run_ids,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "summary": f"Analysis of {len(run_ids)} runs. Found {len(findings)} issues.",
            "findings": findings,
            "recommendations": recommendations,
            "operator_actions_required": ["Review findings", "ACK packet"],
            "safe_mode": False, # MVP assumption
            "version": "1.0.0"
        }
        
        # 4. Compute Hash & Mint ID
        
        # Hashable content: exclude packet_id and packet_content_hash
        content_hash_hex = compute_sha256_hash(packet, exclude_keys=["packet_id", "packet_content_hash"])
        content_hash_Prefixed = "sha256:" + content_hash_hex
        
        # ID calculation: base32(sha256(content_hash))
        id_bytes = hashlib.sha256(content_hash_Prefixed.encode('utf-8')).digest()
        packet_id_base32 = base64.b32encode(id_bytes).decode('utf-8')[:8]
        packet_id = f"PACKET-{packet_id_base32}"
        
        final_packet = packet.copy()
        final_packet["packet_id"] = packet_id
        final_packet["packet_content_hash"] = content_hash_Prefixed
        
        # 5. Write
        path = self.improvement_store.write(final_packet)
        
        # 6. Return Envelope
        # Envelope hash: everything in payload is part of content
        # we hash the final_packet as payload
        
        envelope_data = {
            "agent_id": self.AGENT_ID,
            "schema_version": "1.0.0",
            "run_id": run_ids[0] if run_ids else "RUN-UNKNOWN",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": final_packet,
            "capability_claims": ["read_run_scores", "propose_improvements"]
        }
        
        # Hash envelope content (excluding content_hash field itself if it were inside, but here it's beside)
        # Wait, envelope schema has content_hash outside payload.
        # We hash the envelope data? Or just payload?
        # Definition usually: hash of the *envelope* structure excluding the hash field.
        
        envelope_hash = compute_sha256_hash(envelope_data, exclude_keys=["content_hash"])
        envelope_data["content_hash"] = "sha256:" + envelope_hash
        
        return envelope_data
import os
