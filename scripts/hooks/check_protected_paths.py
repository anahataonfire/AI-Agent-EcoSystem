#!/usr/bin/env python3
"""
Pre-commit hook: Block destructive operations on protected paths.

Layer C of Hard Containment - Static analysis to catch violations before they run.

Checks:
- scripts/, tests/, verify_*.py files
- For: unlink(, rmtree(, rm -rf, DROP TABLE, DELETE FROM
- Referencing: data/content/content.db, data/**/*.db

Install:
    cp scripts/hooks/check_protected_paths.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Or use with pre-commit framework:
    # .pre-commit-config.yaml
    - repo: local
      hooks:
        - id: protected-paths
          name: Check protected paths
          entry: python scripts/hooks/check_protected_paths.py
          language: python
          files: ^(scripts/|tests/|verify_)
"""

import re
import sys
from pathlib import Path


# Patterns that indicate destructive operations
DESTRUCTIVE_PATTERNS = [
    r"\.unlink\s*\(",
    r"\.rmtree\s*\(",
    r"shutil\.rmtree\s*\(",
    r"os\.remove\s*\(",
    r"os\.unlink\s*\(",
    r"rm\s+-rf",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"TRUNCATE\s+TABLE",
    # Subprocess calls to rm
    r"subprocess\.(run|call|Popen)\s*\(\s*\[.*['\"]rm['\"]",
    r"subprocess\.(run|call|Popen)\s*\(\s*['\"]rm\s",
    r"os\.system\s*\(['\"].*rm\s",
]

# Protected path references
PROTECTED_PATH_PATTERNS = [
    r"data/content/content\.db",
    r"data/content/.*\.db",
    r"data/evidence/.*\.db",
    r'["\']data/.*\.db["\']',
    r'Path\(["\']data/',
]

# Files to check (forbidden callers)
FORBIDDEN_FILE_PATTERNS = [
    r"^scripts/verify_.*\.py$",
    r"^verify_.*\.py$",
    r"^scripts/.*\.py$",
    r"^tests/.*\.py$",
]


def is_forbidden_file(filepath: str) -> bool:
    """Check if file is in forbidden category."""
    for pattern in FORBIDDEN_FILE_PATTERNS:
        if re.search(pattern, filepath):
            return True
    return False


def has_destructive_op(content: str) -> list:
    """Find destructive operations in content."""
    found = []
    for pattern in DESTRUCTIVE_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for m in matches:
            found.append((pattern, m.group(), m.start()))
    return found


def has_protected_path_ref(content: str) -> list:
    """Find references to protected paths."""
    found = []
    for pattern in PROTECTED_PATH_PATTERNS:
        matches = re.finditer(pattern, content)
        for m in matches:
            found.append((pattern, m.group(), m.start()))
    return found


def get_line_number(content: str, pos: int) -> int:
    """Get line number for position in content."""
    return content[:pos].count('\n') + 1


def check_file(filepath: Path) -> list:
    """Check a single file for violations."""
    violations = []
    
    try:
        content = filepath.read_text()
    except Exception as e:
        return [(str(filepath), 0, f"Could not read file: {e}")]
    
    destructive_ops = has_destructive_op(content)
    protected_refs = has_protected_path_ref(content)
    
    if destructive_ops and protected_refs:
        # Both present = violation
        for op_pattern, op_match, op_pos in destructive_ops:
            line = get_line_number(content, op_pos)
            violations.append((
                str(filepath),
                line,
                f"Destructive operation '{op_match}' found with protected path reference"
            ))
    
    return violations


def main():
    """Run pre-commit check on staged files."""
    import subprocess
    
    # Get project root
    project_root = Path(__file__).resolve().parent.parent.parent
    
    # Get list of files to check
    # If run as pre-commit hook, check staged files
    # Otherwise, check all matching files
    
    if len(sys.argv) > 1:
        # Files passed as arguments (pre-commit framework mode)
        files = [Path(f) for f in sys.argv[1:]]
    else:
        # Scan all relevant files
        files = []
        for pattern in ["scripts/*.py", "tests/*.py", "verify_*.py"]:
            files.extend(project_root.glob(pattern))
    
    all_violations = []
    
    for filepath in files:
        rel_path = str(filepath.relative_to(project_root) if filepath.is_absolute() else filepath)
        
        if not is_forbidden_file(rel_path):
            continue
        
        violations = check_file(filepath)
        all_violations.extend(violations)
    
    if all_violations:
        print("=" * 60)
        print("PROTECTED PATHS VIOLATION DETECTED")
        print("=" * 60)
        print()
        print("The following files contain destructive operations")
        print("targeting protected production paths:")
        print()
        
        for filepath, line, message in all_violations:
            print(f"  {filepath}:{line}")
            print(f"    {message}")
            print()
        
        print("This is blocked to prevent accidental data loss.")
        print()
        print("Solutions:")
        print("  1. Use data/test/ for test databases")
        print("  2. Use tempfile.TemporaryDirectory()")
        print("  3. Remove destructive operations from test/verify scripts")
        print()
        print("=" * 60)
        
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
