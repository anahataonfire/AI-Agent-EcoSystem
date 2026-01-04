
import pytest
import json
from unittest.mock import MagicMock, patch
from src.agents.meta_analyst import MetaAnalystAgent

@pytest.fixture
def mock_workspace(tmp_path):
    (tmp_path / "data" / "improvement_packets").mkdir(parents=True)
    return tmp_path

def test_meta_analyst_capabilities(mock_workspace):
    """Verify MetaAnalyst claims only allowed capabilities."""
    agent = MetaAnalystAgent(str(mock_workspace))
    
    # Mock engine to return something to avoid FileNotFoundError or crash
    agent.run_score_engine._load_run_data = MagicMock(return_value={"timestamp": "2025-01-01T12:00:00Z"})
    agent.run_score_engine.compute_run_score = MagicMock(return_value={
        "run_id": "TEST-RUN0001",
        "scores": {"total_score": 80, "process_quality_score": 80, "safety_posture_score": 80},
        "flags": {"degraded_triggered": False}
    })
    
    envelope = agent.process(["TEST-RUN0001"])
    
    # Check Claims
    claims = envelope["capability_claims"]
    allowed = {"read_run_scores", "propose_improvements", "read_ledger", "read_commits", "read_evidence_metadata", "read_alerts"}
    
    for c in claims:
        assert c in allowed, f"MetaAnalyst claimed forbidden capability: {c}"
        
    assert "write_evidence" not in claims
    assert "apply_changes" not in claims

def test_meta_analyst_packet_generation(mock_workspace):
    agent = MetaAnalystAgent(str(mock_workspace))
    
    # Mock low score
    agent.run_score_engine._load_run_data = MagicMock(return_value={"timestamp": "2025-01-01T12:00:00Z"})
    agent.run_score_engine.compute_run_score = MagicMock(return_value={
        "run_id": "TEST-RUN0002",
        "scores": {"total_score": 50, "process_quality_score": 50, "safety_posture_score": 50},
        "flags": {"degraded_triggered": True}
    })
    
    envelope = agent.process(["TEST-RUN0002"])
    packet = envelope["payload"]
    
    # Check packet structure
    assert packet["packet_id"].startswith("PACKET-")
    assert packet["packet_content_hash"].startswith("sha256:")
    assert len(packet["findings"]) >= 2 # Low score + Degraded
    assert len(packet["recommendations"]) >= 1
    
    # Verify file write
    matches = list((mock_workspace / "data" / "improvement_packets").rglob("PACKET-*.json"))
    assert len(matches) == 1
