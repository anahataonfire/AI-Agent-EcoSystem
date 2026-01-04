
import pytest
import json
import os
from unittest.mock import MagicMock, patch
from src.cli import cmd_apply
from src.utils.hashing import compute_sha256_hash

@pytest.fixture
def mock_apply_env(tmp_path):
    # Setup directories
    (tmp_path / "data" / "improvement_packets").mkdir(parents=True)
    (tmp_path / "data" / "acks").mkdir(parents=True)
    (tmp_path / "data" / "patch_proposals").mkdir(parents=True)
    return tmp_path

def test_apply_strict_hash_validation(mock_apply_env):
    """
    Test that cmd_apply fails validation if the recomputed hash of the packet on disk
    does not match the 'provided_hash' (which implies the ACK).
    """
    with patch("src.cli.PROJECT_ROOT", mock_apply_env), \
         patch("sys.exit") as mock_exit:
        
        # 1. Create a packet on disk
        packet = {"packet_id": "PACKET-TEST", "packet_content_hash": "sha256:orig", "data": "original"}
        # Compute real hash for "data":"original"
        real_hash = compute_sha256_hash({"data":"original"})
        packet_path = mock_apply_env / "data" / "improvement_packets" / "PACKET-TEST.json"
        
        # Note: ImprovementStore usually handles paths, here we just mock the file existence
        # We need to mock ImprovementStore.read strictly speaking, or just trust the file system mocked
        # The CLI re-instantiates ImprovementStore. logic:
        # store.read searches rglob.
        
        # Let's mock ImprovementStore in CLI to avoid complex file layout
        with patch("src.cli.ImprovementStore") as MockStoreCls, \
             patch("src.cli.HumanApprovalGate") as MockGateCls:
             
             mock_store = MockStoreCls.return_value
             mock_store.read.return_value = packet
             
             mock_gate = MockGateCls.return_value
             
             # Case A: Provided hash matches real hash -> Validates ACK
             args = MagicMock()
             args.packet_id = "PACKET-TEST"
             args.packet_hash = f"sha256:{real_hash}"
             args.ack_token = "deadbeef" * 8 # Valid hex
             
             mock_gate.validate_ack.return_value = True
             
             cmd_apply(args)
             assert mock_gate.validate_ack.called
             
             # Case B: Provided hash does NOT match real hash (Tampered file or wrong ACK)
             # Let's say we tamper the packet returned by store
             packet_tampered = {"packet_id": "PACKET-TEST", "packet_content_hash": "sha256:orig", "data": "TAMPERED"}
             mock_store.read.return_value = packet_tampered
             
             # The CLI will recompute hash of packet_tampered. It will NOT match args.packet_hash (which is for original)
             cmd_apply(args)
             
             # Should have exited
             assert mock_exit.call_count >= 1

def test_patch_proposal_header(mock_apply_env):
    with patch("src.cli.PROJECT_ROOT", mock_apply_env), \
         patch("sys.exit") as mock_exit, \
         patch("src.cli.ImprovementStore") as MockStoreCls, \
         patch("src.cli.HumanApprovalGate") as MockGateCls:
         
         mock_store = MockStoreCls.return_value
         real_hash = compute_sha256_hash({"data":"good"})
         mock_store.read.return_value = {"packet_id": "PACKET-HEAD", "packet_content_hash": f"sha256:{real_hash}", "data": "good"}
         
         mock_gate = MockGateCls.return_value
         mock_gate.validate_ack.return_value = True
         
         args = MagicMock()
         args.packet_id = "PACKET-HEAD"
         args.packet_hash = f"sha256:{real_hash}"
         args.ack_token = "deadbeef" * 8 # Valid hex
         
         cmd_apply(args)
         
         # Check generated file
         # Find file
         files = list((mock_apply_env / "data" / "patch_proposals").rglob("*.md"))
         assert len(files) == 1
         content = files[0].read_text()
         
         assert "---" in content
         assert "packet_id: PACKET-HEAD" in content
         assert f"packet_content_hash: sha256:{real_hash}" in content
         assert "ack_token_hash_prefix: " in content # sha of deadbeef...
         assert "generated_by: dtl_cli" in content
