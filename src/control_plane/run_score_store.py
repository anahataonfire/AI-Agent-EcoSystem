
import json
import os
import datetime
from pathlib import Path
from typing import Dict, List, Optional
import jsonschema
from src.utils.storage import write_json_atomically

# Schema path relative to repo root
SCHEMA_PATH = Path("config/schemas/run_score.json").absolute()

class RunScoreStore:
    def __init__(self, base_dir: str = "data/run_scores"):
        self.base_dir = Path(base_dir)
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict:
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"RunScore schema not found at {SCHEMA_PATH}")
        with open(SCHEMA_PATH, 'r') as f:
            return json.load(f)


    def write(self, score_dict: Dict) -> Path:
        """
        Validates and writes a RunScore to the append-only store.
        Returns the absolute path of the written file.
        Raises ValueError on validation failure or if file exists.
        """
        # Validator wrapper
        def validate(d):
            try:
                jsonschema.validate(instance=d, schema=self.schema)
            except jsonschema.ValidationError as e:
                raise ValueError(f"RunScore validation failed: {str(e)}")

        # 2. Extract key fields
        run_score_id = score_dict["run_score_id"]
        # run_ts parsing for directory structure
        try:
            run_dt = datetime.datetime.fromisoformat(score_dict["run_ts"])
        except ValueError:
             raise ValueError("Invalid run_ts format in RunScore")
        
        # 3. Determine Path
        year = run_dt.strftime("%Y")
        month = run_dt.strftime("%m")
        day = run_dt.strftime("%d")
        
        target_dir = self.base_dir / year / month / day
        filename = f"{run_score_id}.json"
        target_path = target_dir / filename

        # 4. Atomic Write
        write_json_atomically(target_path, score_dict, schema_validator=validate)
            
        return target_path.absolute()

    def read(self, run_score_id: str) -> Optional[Dict]:
        """
        Finds and reads a RunScore by ID.
        Since we store by date, we might need to search or index. 
        For now, simplistic walk or assuming we don't have millions.
        Optimization: We could stick to recent range or require date.
        But requirement says 'read(run_score_id)'. 
        
        Let's search recursively in base_dir.
        """
        # Allow exact path lookup if known? No, ID based.
        # fast path: use `find` or `glob`
        matches = list(self.base_dir.rglob(f"{run_score_id}.json"))
        if not matches:
            return None
        
        # Should be unique
        target_path = matches[0]
        
        with open(target_path, 'r') as f:
            return json.load(f)

    def list_recent(self, limit: int = 10) -> List[Dict]:
        """
        Lists recent RunScores, sorted by computed_at desc.
        """
        all_files = list(self.base_dir.rglob("RUNSCORE-*.json"))
        
        # This could be slow if many files. 
        # For V2.0 MVP this is acceptable.
        scores = []
        for p in all_files:
            try:
                with open(p, 'r') as f:
                    scores.append(json.load(f))
            except Exception:
                continue # Skip corrupt or partial
        
        # Sort by computed_at
        scores.sort(key=lambda x: x.get("computed_at", ""), reverse=True)
        return scores[:limit]
