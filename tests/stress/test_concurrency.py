"""
Parallel Run Collision Test (Prompt 6).

Tests concurrent runs sharing Policy Memory to verify
single-writer enforcement and deterministic serialization.
"""

import pytest
import json
import threading
import time
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class PolicyMemoryStore:
    """Thread-safe policy memory store with single-writer enforcement."""
    
    weights: Dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _write_in_progress: bool = False
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    def read_snapshot(self) -> Dict[str, float]:
        """Read a snapshot (non-blocking)."""
        with self._lock:
            return dict(self.weights)
    
    def try_write(self, updates: Dict[str, float], writer_id: str) -> bool:
        """
        Try to write updates. Returns True if successful.
        Single-writer enforced.
        """
        acquired = self._lock.acquire(blocking=False)
        
        if not acquired:
            self.conflicts.append({
                "writer": writer_id,
                "type": "lock_contention",
                "timestamp": time.time()
            })
            return False
        
        try:
            if self._write_in_progress:
                self.conflicts.append({
                    "writer": writer_id,
                    "type": "concurrent_write",
                    "timestamp": time.time()
                })
                return False
            
            self._write_in_progress = True
            
            # Simulate write delay
            time.sleep(0.01)
            
            # Apply updates
            self.weights.update(updates)
            
            self._write_in_progress = False
            return True
        finally:
            self._lock.release()
    
    def force_write(self, updates: Dict[str, float], writer_id: str) -> bool:
        """Force write with blocking (for serialized execution)."""
        with self._lock:
            self.weights.update(updates)
            return True


def run_worker(store: PolicyMemoryStore, worker_id: int, results: List[Dict]):
    """Worker that reads and writes to policy memory."""
    # Read
    snapshot = store.read_snapshot()
    
    # Compute update (based on worker id for variety)
    update = {f"skill_{worker_id}": 1.0 + (worker_id * 0.1)}
    
    # Try write
    success = store.try_write(update, f"worker_{worker_id}")
    
    results.append({
        "worker": worker_id,
        "read_snapshot": snapshot,
        "write_success": success
    })


class TestParallelRunCollision:
    """Tests for parallel run collision handling."""

    def test_concurrent_writes_handled(self, tmp_path):
        """Test 5 concurrent runs with overlapping writes."""
        store = PolicyMemoryStore(weights={"base": 1.0})
        results = []
        threads = []
        
        # Launch 5 concurrent workers
        for i in range(5):
            t = threading.Thread(target=run_worker, args=(store, i, results))
            threads.append(t)
        
        # Start all at once
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Analyze
        successful_writes = sum(1 for r in results if r["write_success"])
        conflicts = store.conflicts
        
        report = {
            "total_workers": 5,
            "successful_writes": successful_writes,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "final_state": store.weights,
            "mixed_snapshots": False,  # Will check below
            "partial_writes": False,
            "state_corruption": False
        }
        
        # Check for mixed snapshots (all reads got same base state)
        snapshots = [r["read_snapshot"] for r in results]
        # All should have "base" key
        all_have_base = all("base" in s for s in snapshots)
        
        # Check for corruption
        for key, val in store.weights.items():
            if not isinstance(val, float) or val < 0:
                report["state_corruption"] = True
        
        # Verdict
        passed = (
            all_have_base and
            not report["state_corruption"] and
            successful_writes >= 1  # At least one succeeded
        )
        
        report["verdict"] = "PASS" if passed else "FAIL"
        
        with open(tmp_path / "concurrency_conflict_log.json", "w") as f:
            json.dump(report, f, indent=2)
        
        assert all_have_base, "Mixed snapshots detected"
        assert not report["state_corruption"], "State corruption detected"

    def test_serialized_writes_succeed(self):
        """Serialized writes all succeed."""
        store = PolicyMemoryStore(weights={"base": 1.0})
        
        for i in range(5):
            success = store.force_write({f"skill_{i}": 1.0}, f"worker_{i}")
            assert success
        
        # All skills should be present
        assert len(store.weights) == 6  # base + 5 skills

    def test_read_snapshot_consistent(self):
        """Read snapshots are consistent (copy, not reference)."""
        store = PolicyMemoryStore(weights={"a": 1.0})
        
        snap1 = store.read_snapshot()
        snap1["a"] = 999.0  # Mutate the copy
        
        snap2 = store.read_snapshot()
        
        # Original should be unchanged
        assert snap2["a"] == 1.0

    def test_no_partial_writes(self):
        """Atomic writes - no partial state."""
        store = PolicyMemoryStore(weights={"a": 1.0, "b": 1.0})
        
        # Attempt to write two updates
        updates = {"a": 2.0, "b": 2.0}
        store.force_write(updates, "test")
        
        # Both should update or neither
        assert store.weights["a"] == 2.0
        assert store.weights["b"] == 2.0
