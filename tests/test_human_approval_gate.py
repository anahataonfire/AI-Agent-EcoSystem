
import pytest
import json
from src.control_plane.human_approval_gate import HumanApprovalGate

@pytest.fixture
def mock_workspace(tmp_path):
    (tmp_path / "data" / "acks").mkdir(parents=True)
    return tmp_path

def test_ack_creation_and_validation(mock_workspace):
    gate = HumanApprovalGate(str(mock_workspace))
    packet_id = "PACKET-TEST001"
    packet_hash = "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    
    # Create ACK
    token = gate.create_ack(packet_id, packet_hash)
    assert len(token) > 0
    
    # Validate Correct
    assert gate.validate_ack(packet_id, packet_hash, token) is True
    
    # Validate Incorrect Token
    assert gate.validate_ack(packet_id, packet_hash, "wrongtoken") is False
    
    # Validate Incorrect Packet Hash
    assert gate.validate_ack(packet_id, "sha256:wronghash", token) is False

def test_ack_persistence(mock_workspace):
    gate = HumanApprovalGate(str(mock_workspace))
    packet_id = "PACKET-TEST002"
    packet_hash = "sha256:abc"
    
    token = gate.create_ack(packet_id, packet_hash)
    
    # New instance
    gate2 = HumanApprovalGate(str(mock_workspace))
    assert gate2.validate_ack(packet_id, packet_hash, token) is True

def test_ack_overwrite_protection(mock_workspace):
    gate = HumanApprovalGate(str(mock_workspace))
    packet_id = "PACKET-TEST003"
    packet_hash = "sha256:abc"
    
    gate.create_ack(packet_id, packet_hash)
    
    with pytest.raises(FileExistsError):
        gate.create_ack(packet_id, packet_hash)
