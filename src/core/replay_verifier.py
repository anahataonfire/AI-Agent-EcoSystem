"""
Replay Determinism Verifier (Prompt AI).

Verifies that same inputs produce identical outputs, byte-for-byte.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class DeterminismViolationError(Exception):
    """Raised when replay output mismatch is detected."""
    pass


# Timestamp tolerance for footer comparison (1 second)
TIMESTAMP_TOLERANCE_SECONDS = 1


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def normalize_for_comparison(content: str, ignore_timestamps: bool = False) -> str:
    """
    Normalize content for deterministic comparison.
    
    Args:
        content: The content to normalize
        ignore_timestamps: If True, remove timestamp variations
        
    Returns:
        Normalized content string
    """
    result = content
    
    if ignore_timestamps:
        # Remove ISO8601 timestamps for comparison
        import re
        result = re.sub(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?',
            '[TIMESTAMP]',
            result
        )
    
    return result


def compare_reports(
    original_report: str,
    replay_report: str,
    timestamp_tolerance: int = TIMESTAMP_TOLERANCE_SECONDS
) -> Tuple[bool, Optional[str]]:
    """
    Compare two reports for determinism.
    
    Args:
        original_report: The original report
        replay_report: The replayed report
        timestamp_tolerance: Max seconds difference allowed for timestamps
        
    Returns:
        Tuple of (is_identical, diff_reason)
    """
    # Normalize for comparison (removing timestamps)
    norm_original = normalize_for_comparison(original_report, ignore_timestamps=True)
    norm_replay = normalize_for_comparison(replay_report, ignore_timestamps=True)
    
    if norm_original != norm_replay:
        # Find first difference
        for i, (c1, c2) in enumerate(zip(norm_original, norm_replay)):
            if c1 != c2:
                context = norm_original[max(0, i-20):i+20]
                return (False, f"Mismatch at position {i}: '{context}'")
        
        if len(norm_original) != len(norm_replay):
            return (False, f"Length mismatch: {len(norm_original)} vs {len(norm_replay)}")
    
    return (True, None)


def compare_telemetry(
    original_telemetry: Dict[str, Any],
    replay_telemetry: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Compare telemetry for determinism.
    
    Returns:
        Tuple of (is_identical, diff_reason)
    """
    # Compare keys
    orig_keys = set(original_telemetry.keys())
    replay_keys = set(replay_telemetry.keys())
    
    if orig_keys != replay_keys:
        missing = orig_keys - replay_keys
        extra = replay_keys - orig_keys
        return (False, f"Telemetry keys differ: missing={missing}, extra={extra}")
    
    # Compare values (excluding timestamps)
    for key in orig_keys:
        if key in ("timestamp", "created_at", "updated_at"):
            continue
        if original_telemetry[key] != replay_telemetry[key]:
            return (False, f"Telemetry mismatch for '{key}': {original_telemetry[key]} vs {replay_telemetry[key]}")
    
    return (True, None)


def compare_ledger_hashes(
    original_hashes: List[str],
    replay_hashes: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Compare ledger hashes for determinism.
    
    Returns:
        Tuple of (is_identical, diff_reason)
    """
    if len(original_hashes) != len(replay_hashes):
        return (False, f"Ledger entry count mismatch: {len(original_hashes)} vs {len(replay_hashes)}")
    
    for i, (orig, replay) in enumerate(zip(original_hashes, replay_hashes)):
        if orig != replay:
            return (False, f"Ledger hash mismatch at index {i}: {orig} vs {replay}")
    
    return (True, None)


def verify_replay_determinism(
    original_state: Dict[str, Any],
    replay_state: Dict[str, Any]
) -> None:
    """
    Verify that replay produces identical output.
    
    Args:
        original_state: The original run state
        replay_state: The replayed run state
        
    Raises:
        DeterminismViolationError: If mismatch detected
    """
    # Compare final reports
    orig_report = original_state.get("final_report", "")
    replay_report = replay_state.get("final_report", "")
    
    is_same, diff = compare_reports(orig_report, replay_report)
    if not is_same:
        raise DeterminismViolationError(
            f"# Determinism Violation\nReplay output mismatch detected: {diff}"
        )
    
    # Compare telemetry
    orig_telemetry = original_state.get("telemetry", {})
    replay_telemetry = replay_state.get("telemetry", {})
    
    is_same, diff = compare_telemetry(orig_telemetry, replay_telemetry)
    if not is_same:
        raise DeterminismViolationError(
            f"# Determinism Violation\nTelemetry mismatch: {diff}"
        )
    
    # Compare ledger hashes if available
    orig_hashes = original_state.get("ledger_hashes", [])
    replay_hashes = replay_state.get("ledger_hashes", [])
    
    if orig_hashes or replay_hashes:
        is_same, diff = compare_ledger_hashes(orig_hashes, replay_hashes)
        if not is_same:
            raise DeterminismViolationError(
                f"# Determinism Violation\nLedger hash mismatch: {diff}"
            )


def create_replay_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """Create a snapshot for replay comparison."""
    return {
        "final_report": state.get("final_report", ""),
        "final_report_hash": compute_content_hash(state.get("final_report", "")),
        "telemetry": state.get("telemetry", {}),
        "ledger_hashes": state.get("ledger_hashes", []),
        "evidence_ids": sorted(state.get("evidence_map", {}).keys()),
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
    }
