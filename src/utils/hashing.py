
import json
import hashlib
from typing import Any, List, Dict
from datetime import datetime

def to_canonical_json(data: Any, exclude_keys: List[str] = None) -> bytes:
    """
    Serializes data to canonical JSON bytes.
    - keys sorted
    - no whitespace separators
    - ensure_ascii=False (UTF-8)
    - exclude_keys removed from top-level dict if present
    """
    if exclude_keys and isinstance(data, dict):
        data = {k: v for k, v in data.items() if k not in exclude_keys}
        
    return json.dumps(
        data,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False
    ).encode('utf-8')

def compute_sha256_hash(data: Any, exclude_keys: List[str] = None) -> str:
    """
    Computes SHA-256 hash of canonical JSON representation of data.
    Returns hex digest string.
    """
    json_bytes = to_canonical_json(data, exclude_keys)
    return hashlib.sha256(json_bytes).hexdigest()

def normalize_timestamp(dt_str: str) -> str:
    """
    Ensures timestamp is ISO8601 UTC.
    If naive, assumes UTC. 
    Returns string.
    """
    # This is a helper if needed, but standardizing generation is better.
    # We stick to strings in dicts for now.
    pass
