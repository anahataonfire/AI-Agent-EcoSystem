"""
Compliance Snapshot Export (Prompt AL).

Export a single JSON artifact for auditors containing:
- Run ledger
- Evidence IDs
- Provenance footer
- Grounding contract version
- Kill-switch state

Read-only, no LLM access, deterministic ordering.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ComplianceExport:
    """
    Read-only compliance export for auditors.
    
    No LLM access. Deterministic ordering.
    """
    
    # Grounding contract version
    GROUNDING_CONTRACT_VERSION = "1.0.0"
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._export_data: Optional[Dict[str, Any]] = None
    
    def generate(
        self,
        ledger_entries: list,
        evidence_ids: list,
        provenance_footer: str,
        kill_switch_state: dict,
        telemetry: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate compliance export.
        
        Returns:
            Read-only export dict
        """
        self._export_data = {
            "metadata": {
                "run_id": self.run_id,
                "grounding_contract_version": self.GROUNDING_CONTRACT_VERSION,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "export_version": "1.0",
            },
            "run_ledger": sorted(
                ledger_entries,
                key=lambda x: (x.get("sequence", 0), x.get("timestamp", ""))
            ),
            "evidence_ids": sorted(evidence_ids),
            "provenance_footer": provenance_footer,
            "kill_switch_state": {
                k: v for k, v in sorted(kill_switch_state.items())
            },
            "telemetry": telemetry or {},
        }
        
        return self._export_data
    
    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        if self._export_data is None:
            raise ValueError("Export not generated. Call generate() first.")
        return json.dumps(self._export_data, indent=indent, default=str, sort_keys=True)
    
    def save(self, path: str) -> str:
        """Save export to file."""
        if self._export_data is None:
            raise ValueError("Export not generated. Call generate() first.")
        
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        
        return str(output_path)
    
    def get_export(self) -> Optional[Dict[str, Any]]:
        """Get the generated export (read-only copy)."""
        if self._export_data is None:
            return None
        # Return a copy to prevent mutation
        return json.loads(json.dumps(self._export_data, default=str))
    
    def verify_matches_run(
        self,
        actual_evidence_ids: list,
        actual_ledger_count: int
    ) -> bool:
        """
        Verify export matches actual run data.
        
        Returns:
            True if export matches
        """
        if self._export_data is None:
            return False
        
        exported_ids = set(self._export_data.get("evidence_ids", []))
        actual_ids = set(actual_evidence_ids)
        
        if exported_ids != actual_ids:
            return False
        
        exported_ledger_count = len(self._export_data.get("run_ledger", []))
        if exported_ledger_count != actual_ledger_count:
            return False
        
        return True


def create_compliance_export(
    run_id: str,
    ledger_entries: list,
    evidence_ids: list,
    provenance_footer: str,
    kill_switch_state: dict,
    telemetry: Optional[dict] = None,
) -> ComplianceExport:
    """
    Create a compliance export for a run.
    
    Args:
        run_id: The run ID
        ledger_entries: List of ledger entries
        evidence_ids: List of evidence IDs used
        provenance_footer: The provenance footer
        kill_switch_state: Current kill-switch state
        telemetry: Optional telemetry data
        
    Returns:
        ComplianceExport object
    """
    export = ComplianceExport(run_id)
    export.generate(
        ledger_entries=ledger_entries,
        evidence_ids=evidence_ids,
        provenance_footer=provenance_footer,
        kill_switch_state=kill_switch_state,
        telemetry=telemetry,
    )
    return export
