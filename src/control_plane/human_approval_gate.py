
import json
import secrets
import hashlib
import os
import datetime
from pathlib import Path
from typing import Dict, Optional

class HumanApprovalGate:
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.ack_base_dir = self.workspace_root / "data" / "acks"
    
    def create_ack(self, packet_id: str, packet_hash: str) -> str:
        """
        Generates a secure ACK token for a specific packet and persists the binding.
        Returns the raw token (to be shown to user ONCE).
        """
        # 1. Generate secure random token
        token_bytes = secrets.token_bytes(32)
        token_hex = token_bytes.hex()
        
        # 2. Hash token for storage
        token_hash = hashlib.sha256(token_bytes).hexdigest()
        
        # 3. Create ACK Record
        ack_record = {
            "packet_id": packet_id,
            "packet_content_hash": packet_hash,
            "ack_token_hash": token_hash,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0"
        }
        
        # 4. Determine Path: data/acks/YYYY/MM/DD/ACK-<packet_id>.json
        now = datetime.datetime.utcnow()
        target_dir = self.ack_base_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Use random suffix or timestamp to allow re-acking? 
        # Actually requirement says "ACK-<packet_id>". 
        # If we re-ack, we might overwrite or fail. Append-only implies fail.
        # But if user lost token, they might need new one.
        # Let's use ACK-<packet_id>-<short_random>.json to allow multiple acks if needed,
        # OR just enforce one. Detailed plan said `ACK-<id>.json`.
        # I'll stick to ACK-<packet_id>.json and fail if exists (fail-closed).
        
        target_path = target_dir / f"ACK-{packet_id}.json"
        
        if target_path.exists():
             raise FileExistsError(f"ACK for {packet_id} already exists. Cannot re-issue.")
             
        with open(target_path, 'w') as f:
            json.dump(ack_record, f, indent=2)
            
        return token_hex

    def validate_ack(self, packet_id: str, packet_content_hash: str, token: str) -> bool:
        """
        Validates the ACK token.
        
        POLICY: Multi-use ACK (Option B).
        Tokens are not consumed or invalidated after use.
        They remain valid for the lifetime of the ACK file.
        This allows re-generating patch proposals if needed.
        """
        # 1. Find the ACK record
        # Path: data/acks/YYYY/MM/DD/ACK-<packet_id>.json
        # We assume we search for it.
        matches = list(self.ack_base_dir.rglob(f"ACK-{packet_id}.json"))
        if not matches:
            return False
            
        record_path = matches[0]
        try:
            with open(record_path, 'r') as f:
                record = json.load(f)
        except:
            return False
            
        # Check binding to packet_hash
        if record.get("packet_content_hash") != packet_content_hash:
            return False
            
        # 2. Verify Token
        # Hash the input token
        try:
            input_token_bytes = bytes.fromhex(token)
        except ValueError:
            return False
            
        input_hash = hashlib.sha256(input_token_bytes).hexdigest()
        
        if record.get("ack_token_hash") != input_hash:
            return False
            
        return True
