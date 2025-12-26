"""
Runtime Fingerprint for DTL v2.0

Captures exact package versions and runtime environment for replay determinism.
"""

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_runtime_fingerprint() -> dict:
    """
    Capture runtime fingerprint for determinism and replay.
    
    Includes:
    - Python version
    - Key package versions (google-adk, jsonschema, etc.)
    - Platform info
    - Timestamp
    """
    fingerprint = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "packages": {}
    }
    
    # Key packages to track
    key_packages = [
        "google-adk",
        "google-genai", 
        "jsonschema",
        "pydantic",
        "google-cloud-aiplatform",
    ]
    
    try:
        from importlib.metadata import version, PackageNotFoundError
        for pkg in key_packages:
            try:
                fingerprint["packages"][pkg] = version(pkg)
            except PackageNotFoundError:
                fingerprint["packages"][pkg] = "NOT_INSTALLED"
    except ImportError:
        # Fallback for older Python
        fingerprint["packages"]["_error"] = "importlib.metadata not available"
    
    return fingerprint


def save_fingerprint_to_policy(policy: dict) -> dict:
    """
    Add runtime fingerprint to policy snapshot.
    """
    policy["runtime_fingerprint"] = get_runtime_fingerprint()
    return policy


def save_fingerprint_to_ledger(run_output: dict) -> dict:
    """
    Add runtime fingerprint to run ledger output.
    """
    run_output["runtime_fingerprint"] = get_runtime_fingerprint()
    return run_output


def verify_fingerprint_matches(expected: dict, actual: Optional[dict] = None) -> tuple[bool, list[str]]:
    """
    Verify that the current runtime matches an expected fingerprint.
    
    Returns (matches, mismatches) where mismatches is a list of differences.
    """
    if actual is None:
        actual = get_runtime_fingerprint()
    
    mismatches = []
    
    # Check key packages
    expected_pkgs = expected.get("packages", {})
    actual_pkgs = actual.get("packages", {})
    
    for pkg, expected_version in expected_pkgs.items():
        actual_version = actual_pkgs.get(pkg, "MISSING")
        if expected_version != actual_version and expected_version != "NOT_INSTALLED":
            mismatches.append(f"{pkg}: expected {expected_version}, got {actual_version}")
    
    # Check Python major.minor
    expected_py = expected.get("python_version", "").split()[0]  # e.g., "3.13.0"
    actual_py = actual.get("python_version", "").split()[0]
    if expected_py and actual_py:
        # Compare major.minor only
        exp_mm = ".".join(expected_py.split(".")[:2])
        act_mm = ".".join(actual_py.split(".")[:2])
        if exp_mm != act_mm:
            mismatches.append(f"python: expected {exp_mm}, got {act_mm}")
    
    return len(mismatches) == 0, mismatches
