"""
Protected Paths Firewall - Hard Containment Layer B

This module enforces runtime protection for critical data files.
Any destructive operation (unlink, rmtree, write) on protected paths
will be blocked unless explicitly allowed via multi-key authorization.

Protected paths (relative to project root):
- data_core/**/*.db (authoritative stores)
- data/content/content.db (legacy location)
- data/evidence/*.db
- data/advisor_learning.db
- config/datamart_registry.json

LIMITATIONS (this is a SAFETY RAIL, not a security boundary):
- Cannot block subprocess.run(["rm", ...]) - use static analysis for that
- Cannot block open(..., "w") on protected paths - use CI check
- Stack inspection is heuristic, not cryptographic
- The real security is: filesystem lock + process separation

Usage:
    from src.control_plane.protected_paths import assert_safe_for_write, assert_safe_for_delete
    
    # Before any write operation
    assert_safe_for_write(path)
    
    # Before any delete operation  
    assert_safe_for_delete(path)
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional, List


# Environment variable for explicit override (multi-key launch sequence)
ENV_ALLOW_DESTRUCTIVE = "DTL_ALLOW_DESTRUCTIVE"
ENV_ALLOW_VALUE = "YES_I_KNOW_WHAT_IM_DOING"

# Protected path patterns (relative to project root)
PROTECTED_PATTERNS = [
    # Authoritative stores (future: data_core/)
    r"^data_core/.*\.db$",
    r"^data_core/.*\.json$",
    # Current locations
    r"^data/content/content\.db$",
    r"^data/content/.*\.db$",
    r"^data/evidence/.*\.db$",
    r"^data/advisor_learning\.db$",
    r"^data/ledger/.*",  # All ledger files (JSON or otherwise)
    r"^config/datamart_registry\.json$",
]

# Scripts that can NEVER touch protected paths, even with env override
FORBIDDEN_CALLER_PATTERNS = [
    r"/scripts/verify_.*\.py$",
    r"/verify_.*\.py$",
    r"/tests/.*\.py$",
    r"/test_.*\.py$",
]

# Allowlist for legitimate migration/admin tools (EXACT MATCH after normalization)
ALLOWED_CALLERS: List[str] = [
    "src/content/store.py",
    "src/content/datamart_bundler.py",
    "src/core/evidence_store.py",
    "api/main.py",
    "src/cli.py",
    "src/agents/advisor.py",
    "scripts/migrate_advisor_memory.py",  # Migration tool
]


class ProtectedPathViolation(Exception):
    """Raised when a protected path operation is blocked."""
    pass


def _get_project_root() -> Path:
    """Get project root directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").exists() and (parent / "data").exists():
            return parent
    return current.parent.parent.parent


PROJECT_ROOT = _get_project_root()


def _normalize_path(path) -> str:
    """Normalize path to repo-relative string for matching."""
    path = Path(path).resolve()
    
    try:
        rel = path.relative_to(PROJECT_ROOT)
        return str(rel)
    except ValueError:
        return str(path)


def _is_protected_path(path) -> bool:
    """Check if path matches any protected pattern."""
    normalized = _normalize_path(path)
    
    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, normalized):
            return True
    return False


def _get_caller_file() -> Optional[str]:
    """Get the file that initiated the operation (walk up stack)."""
    import inspect
    
    for frame_info in inspect.stack():
        filename = frame_info.filename
        # Skip this module and standard library
        if "protected_paths.py" in filename:
            continue
        if "site-packages" in filename or "lib/python" in filename:
            continue
        return filename
    return None


def _is_forbidden_caller() -> bool:
    """Check if caller is a test/verify script that can NEVER touch protected paths."""
    caller = _get_caller_file()
    if not caller:
        return False
    
    for pattern in FORBIDDEN_CALLER_PATTERNS:
        if re.search(pattern, caller):
            return True
    return False


def _is_allowed_caller() -> bool:
    """
    Check if caller is in the allowlist for override.
    Uses EXACT MATCH on repo-relative path (no substring matching).
    """
    caller = _get_caller_file()
    if not caller:
        return False
    
    try:
        caller_path = Path(caller).resolve()
        rel_caller = str(caller_path.relative_to(PROJECT_ROOT))
        
        # EXACT match only - no substring
        return rel_caller in ALLOWED_CALLERS
    except ValueError:
        return False


def _has_env_override() -> bool:
    """Check if environment override is set."""
    return os.environ.get(ENV_ALLOW_DESTRUCTIVE) == ENV_ALLOW_VALUE


def assert_safe_for_write(path, operation: str = "write") -> None:
    """
    Assert that it's safe to write to this path.
    
    Raises ProtectedPathViolation if:
    - Path is protected AND
    - Caller is forbidden (test/verify script) OR
    - Caller is not in allowlist OR
    - Environment override is not set
    """
    if not _is_protected_path(path):
        return  # Not protected, allow
    
    # Forbidden callers can NEVER touch protected paths
    if _is_forbidden_caller():
        caller = _get_caller_file()
        raise ProtectedPathViolation(
            f"BLOCKED: {operation} on protected path '{path}' from forbidden caller '{caller}'. "
            f"Test/verify scripts can NEVER modify protected production data."
        )
    
    # Non-allowlisted callers need env override
    if not _is_allowed_caller():
        if not _has_env_override():
            caller = _get_caller_file()
            raise ProtectedPathViolation(
                f"BLOCKED: {operation} on protected path '{path}' from '{caller}'. "
                f"Set {ENV_ALLOW_DESTRUCTIVE}={ENV_ALLOW_VALUE} to override."
            )
    
    # Allowed caller - permit


def assert_safe_for_delete(path) -> None:
    """
    Assert that it's safe to delete this path.
    
    Deletion has stricter rules than write:
    - ALWAYS requires env override, even for allowlisted callers
    """
    if not _is_protected_path(path):
        return  # Not protected, allow
    
    # Forbidden callers can NEVER delete protected paths
    if _is_forbidden_caller():
        caller = _get_caller_file()
        raise ProtectedPathViolation(
            f"BLOCKED: delete on protected path '{path}' from forbidden caller '{caller}'. "
            f"Test/verify scripts can NEVER delete protected production data."
        )
    
    # Deletion ALWAYS requires env override
    if not _has_env_override():
        caller = _get_caller_file()
        raise ProtectedPathViolation(
            f"BLOCKED: delete on protected path '{path}' from '{caller}'. "
            f"Deletion requires {ENV_ALLOW_DESTRUCTIVE}={ENV_ALLOW_VALUE}."
        )


def assert_not_production_path(path, allowlist_flag: bool = False) -> None:
    """Legacy alias for assert_safe_for_write."""
    assert_safe_for_write(path, operation="access")


# =============================================================================
# MONKEY-PATCHES: Guard all delete functions at import time
# =============================================================================

# Guard Path.unlink
_original_path_unlink = Path.unlink

def _guarded_path_unlink(self, missing_ok=False):
    """Guarded version of Path.unlink that checks protected paths."""
    assert_safe_for_delete(self)
    return _original_path_unlink(self, missing_ok=missing_ok)

Path.unlink = _guarded_path_unlink


# Guard os.remove
_original_os_remove = os.remove

def _guarded_os_remove(path):
    """Guarded version of os.remove that checks protected paths."""
    assert_safe_for_delete(path)
    return _original_os_remove(path)

os.remove = _guarded_os_remove


# Guard os.unlink
_original_os_unlink = os.unlink

def _guarded_os_unlink(path):
    """Guarded version of os.unlink that checks protected paths."""
    assert_safe_for_delete(path)
    return _original_os_unlink(path)

os.unlink = _guarded_os_unlink


# Guard shutil.rmtree
def install_shutil_guard():
    """Install guard on shutil.rmtree (call at module load)."""
    import shutil
    _original_rmtree = shutil.rmtree
    
    def _guarded_rmtree(path, *args, **kwargs):
        assert_safe_for_delete(path)
        return _original_rmtree(path, *args, **kwargs)
    
    shutil.rmtree = _guarded_rmtree

install_shutil_guard()


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("Protected Paths Firewall - Self Test")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"\nProtected patterns:")
    for p in PROTECTED_PATTERNS:
        print(f"  {p}")
    
    print(f"\nAllowed callers (exact match):")
    for c in ALLOWED_CALLERS:
        print(f"  {c}")
    
    test_paths = [
        "data/content/content.db",
        "data/test/content.db",
        "data/evidence/store.db",
        "data/ledger/2026/01/07/entry.json",
        "data_core/authoritative.db",
        "config/datamart_registry.json",
        "src/cli.py",
    ]
    
    print(f"\nPath protection status:")
    for p in test_paths:
        protected = _is_protected_path(p)
        print(f"  {p}: {'🔒 PROTECTED' if protected else '✓ open'}")

