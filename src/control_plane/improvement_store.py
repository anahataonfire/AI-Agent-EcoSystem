
import json
import os
import datetime
from pathlib import Path
from typing import Dict, List, Optional
import jsonschema
from src.utils.storage import write_json_atomically

# Schema path relative to repo root
SCHEMA_PATH = Path("config/schemas/improvement_packet.json").absolute()

class ImprovementStore:
    def __init__(self, base_dir: str = "data/improvement_packets"):
        self.base_dir = Path(base_dir)
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict:
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"ImprovementPacket schema not found at {SCHEMA_PATH}")
        with open(SCHEMA_PATH, 'r') as f:
            return json.load(f)


    def write(self, packet_dict: Dict) -> Path:
        """
        Validates and writes an ImprovementPacket to the append-only store.
        Returns the absolute path of the written file.
        Raises ValueError on validation failure or if file exists.
        """
        def validate(d):
            try:
                jsonschema.validate(instance=d, schema=self.schema)
            except jsonschema.ValidationError as e:
                raise ValueError(f"ImprovementPacket validation failed: {str(e)}")

        # 2. Extract key fields
        packet_id = packet_dict["packet_id"]
        # packet_content_hash checks not strictly needed here for pathing
        
        try:
            created_dt = datetime.datetime.fromisoformat(packet_dict["created_at"])
        except ValueError:
             raise ValueError("Invalid created_at format in ImprovementPacket")
        
        # 3. Determine Path
        year = created_dt.strftime("%Y")
        month = created_dt.strftime("%m")
        day = created_dt.strftime("%d")
        
        target_dir = self.base_dir / year / month / day
        filename = f"{packet_id}.json"
        target_path = target_dir / filename

        # 4. Atomic Write
        write_json_atomically(target_path, packet_dict, schema_validator=validate)
            
        return target_path.absolute()

    def read(self, packet_id: str) -> Optional[Dict]:
        """
        Finds and reads an ImprovementPacket by ID.
        """
        matches = list(self.base_dir.rglob(f"{packet_id}.json"))
        if not matches:
            return None
        
        target_path = matches[0]
        with open(target_path, 'r') as f:
            return json.load(f)

    def list_recent(self, limit: int = 10) -> List[Dict]:
        """
        Lists recent ImprovementPackets, sorted by created_at desc.
        """
        all_files = list(self.base_dir.rglob("PACKET-*.json"))
        
        packets = []
        for p in all_files:
            try:
                with open(p, 'r') as f:
                    packets.append(json.load(f))
            except Exception:
                continue
        
        packets.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return packets[:limit]
