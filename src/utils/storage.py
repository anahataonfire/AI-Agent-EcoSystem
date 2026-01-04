
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any

def write_json_atomically(path: Path, data: Dict[str, Any], schema_validator=None):
    """
    Writes JSON data to path atomically:
    1. Write to temp file in same directory.
    2. fsync.
    3. Rename to target path.
    4. Fail if target exists (idempotent check should be done by caller, but we enforce no-overwrite).
    
    Args:
        path: Target Path object.
        data: Dict to write.
        schema_validator: Optional callable(data) that raises exception if invalid.
    """
    if path.exists():
        raise FileExistsError(f"Target {path} already exists. Overwrite denied.")
        
    if schema_validator:
        schema_validator(data)
        
    # Ensure parent exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp
    # We use delete=False then rename.
    # We put temp file in same dir to ensure atomic rename (same filesystem).
    
    fd, temp_path = tempfile.mkstemp(dir=path.parent, text=True)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            
        # Atomic Rename
        # os.rename is atomic on POSIX.
        # However, we want to fail if destination exists.
        # os.rename replaces if dest exists on some systems/configs, purely atomic.
        # os.link + os.unlink is strictly atomic 'create if not exists' style on POSIX?
        # Actually os.rename(src, dst) replaces dst if it exists.
        # To ensure we don't overwrite, we verified path.exists() above.
        # But there's a race condition.
        # Use os.link(temp, target) then unlink temp?
        # Standard "exclusive creation" is open(x), but we are writing whole file.
        # For this system, checking .exists() before is likely sufficient given single-writer assumptions per agent run,
        # but to be truly robust against parallel runs:
        
        # We can use `os.link` to create a hard link. If target exists, link fails (EEXIST).
        # Then unlink temp.
        # This works on same filesystem. 
        
        try:
            os.link(temp_path, str(path))
        except FileExistsError:
            # Race condition hit
            raise FileExistsError(f"Target {path} created concurrently. Overwrite denied.")
        except OSError:
            # Fallback for systems that don't support hardlinks well or cross-device (shouldn't happen with dir=parent)
            # Check exists one last time
            if path.exists():
                raise FileExistsError(f"Target {path} created concurrently.")
            os.rename(temp_path, path)
            
    finally:
        # Cleanup temp if it still exists (link succeeded, we unlink temp; link failed, we unlink temp)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
