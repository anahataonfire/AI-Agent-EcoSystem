
import pytest
import json
from src.utils.hashing import compute_sha256_hash, to_canonical_json

def test_canonical_json_ordering():
    """Test that key order does not affect hash."""
    obj1 = {"a": 1, "b": 2, "c": [3, 4]}
    obj2 = {"b": 2, "c": [3, 4], "a": 1}
    
    hash1 = compute_sha256_hash(obj1)
    hash2 = compute_sha256_hash(obj2)
    
    assert hash1 == hash2

def test_canonical_json_whitespace():
    """Test that whitespace is normalized (minified)."""
    # to_canonical_json returns bytes
    # We construct raw json with spaces
    # But compute_sha256_hash uses to_canonical_json internally which minifies.
    # So we prefer to verify that the byte output of to_canonical_json is compact.
    
    obj = {"a": 1}
    canonical = to_canonical_json(obj)
    assert b" " not in canonical
    assert canonical == b'{"a":1}'

def test_hashing_semantic_change():
    """Test that any semantic change works."""
    obj1 = {"a": 1}
    obj2 = {"a": 2} # Value change
    obj3 = {"a": 1, "b": 2} # Key addition
    
    h1 = compute_sha256_hash(obj1)
    h2 = compute_sha256_hash(obj2)
    h3 = compute_sha256_hash(obj3)
    
    assert h1 != h2
    assert h1 != h3
    assert h2 != h3

def test_exclude_keys():
    """Test key exclusion."""
    obj1 = {"id": "1", "content": "foo"}
    obj2 = {"id": "2", "content": "foo"}
    
    # Hash content only
    h1 = compute_sha256_hash(obj1, exclude_keys=["id"])
    h2 = compute_sha256_hash(obj2, exclude_keys=["id"])
    
    assert h1 == h2
