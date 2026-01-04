
import pytest
import json
import os
from unittest.mock import MagicMock, patch
from src.control_plane.run_score import RunScoreEngine
from src.control_plane.run_score_store import RunScoreStore

@pytest.fixture
def mock_workspace(tmp_path):
    # Setup standard data dirs
    (tmp_path / "data" / "run_scores").mkdir(parents=True)
    (tmp_path / "data" / "run_ledger.jsonl").touch()
    (tmp_path / "data" / "evidence_store.json").write_text("{}")
    (tmp_path / "data" / "dtl_runs").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path

def test_run_score_deterministic_id(mock_workspace):
    engine = RunScoreEngine(str(mock_workspace))
    run_id = "RUN-20250101_120000"
    ts = "2025-01-01T12:00:00Z"
    
    # Run 1
    score1 = engine.compute_run_score(run_id, ts)
    
    # Run 2 (same inputs)
    # Note: store will raise error if we try to write same ID again.
    # We should mock store.write to just verify ID generation stability
    engine.store.write = MagicMock()
    
    score2 = engine.compute_run_score(run_id, ts)
    
    assert score1["run_score_id"] == score2["run_score_id"]
    assert score1["run_score_id"].startswith("RUNSCORE-")

def test_run_score_calculation_basics(mock_workspace):
    engine = RunScoreEngine(str(mock_workspace))
    run_id = "TEST-RUN0001"
    ts = "2025-01-01T12:00:00Z"
    
    # Mock data return values
    engine._load_run_data = MagicMock(return_value={"evidence_refs": ["ev1", "ev2"]})
    engine._load_evidence_store = MagicMock(return_value={
        "ev1": {"trust_tier": "high", "expires": "2030-01-01T00:00:00Z"},
        "ev2": {"trust_tier": "low", "expires": "2020-01-01T00:00:00Z"} # Expired
    })
    engine._count_ledger_event = MagicMock(return_value=0) # No rejections
    engine._load_degraded_events = MagicMock(return_value=[]) # No degraded
    
    score = engine.compute_run_score(run_id, ts)
    
    # Verify Evidence Metrics
    assert score["evidence_metrics"]["evidence_count"] == 2
    assert score["evidence_metrics"]["evidence_fresh_count"] == 1
    assert score["evidence_metrics"]["evidence_expired_count"] == 1
    
    # Verify Safety Posture
    # Base 100 - 5 * 1 stale = 95
    assert score["scores"]["safety_posture_score"] == 95

def test_store_overwrite_protection(mock_workspace):
    store = RunScoreStore(str(mock_workspace / "data" / "run_scores"))
    
    doc = {
        "run_score_id": "RUNSCORE-TEST0001",
        "run_id": "TEST-RUN0001",
        "run_ts": "2025-01-01T12:00:00Z",
        "scores": {"outcome_proxy_score": 0, "process_quality_score": 0, "safety_posture_score": 0, "total_score": 0},
        "flags": {"degraded_triggered": False, "firewall_rejections": 0, "commit_gate_rejections": 0, "evidence_stale_count": 0},
        "evidence_metrics": {"evidence_count": 0, "evidence_fresh_count": 0, "evidence_expired_count": 0, "avg_trust_tier": 0},
        "realitycheck_metrics": {"available": False, "alignment_score": 0, "notes": ""},
        "computed_at": "2025-01-01T12:00:00Z",
        "version": "1.0.0"
    }
    
    store.write(doc)
    
    with pytest.raises(Exception): # FileExistsError usually
        store.write(doc)
