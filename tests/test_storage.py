
import pytest
import os
import json
import threading
from pathlib import Path
from src.utils.storage import write_json_atomically

def test_write_atomically_basic(tmp_path):
    target = tmp_path / "test.json"
    data = {"foo": "bar"}
    
    write_json_atomically(target, data)
    
    assert target.exists()
    assert json.loads(target.read_text()) == data

def test_write_atomically_no_overwrite(tmp_path):
    target = tmp_path / "test.json"
    data = {"foo": "bar"}
    target.write_text("existing")
    
    with pytest.raises(FileExistsError):
        write_json_atomically(target, data)
        
    assert target.read_text() == "existing"

def test_concurrent_writes(tmp_path):
    # Try to write same file from multiple threads.
    # Only one should succeed.
    target = tmp_path / "race_test.json"
    results = []
    
    def writer(idx):
        try:
            write_json_atomically(target, {"writer": idx})
            results.append("success")
        except FileExistsError:
            results.append("failed")
    
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert results.count("success") == 1
    assert results.count("failed") == 9
