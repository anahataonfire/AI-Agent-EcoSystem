"""
Externalized Verification: deterministic checks only.

NO semantic/substring matching. All checks must be binary pass/fail.

Can be run as CLI for Ralph's verifierCommand:
    python -m src.executors.verifier --test-commands "pytest tests/" --file-checks '{"path":"foo.py","exists":true}'
    
Outputs JSON: {"complete": bool, "reason": string}
"""
import subprocess
import json
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class VerifyResult:
    """Result of verification - matches Ralph's verifyCompletion contract."""
    complete: bool
    reason: str
    
    def to_json(self) -> str:
        return json.dumps({"complete": self.complete, "reason": self.reason})


class Verifier:
    """Deterministic verifier using test commands and file checks."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
    
    def verify(
        self,
        test_commands: list[str] = None,
        file_checks: list[dict] = None,
    ) -> VerifyResult:
        """
        Run verification checks. ALL checks must pass.
        
        Args:
            test_commands: Shell commands that must exit 0
            file_checks: [{"path": "...", "exists": True/False}, ...]
            
        Returns:
            VerifyResult with complete and reason
        """
        failures = []
        passes = []
        
        # Run test commands
        for cmd in (test_commands or []):
            try:
                result = subprocess.run(
                    cmd, shell=True, cwd=self.project_root,
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    stderr = result.stderr.strip()[:300] or "no output"
                    failures.append(f"Test failed [{cmd}]: {stderr}")
                else:
                    passes.append(f"Test passed: {cmd}")
            except subprocess.TimeoutExpired:
                failures.append(f"Test timeout [{cmd}]: exceeded 120s")
            except Exception as e:
                failures.append(f"Test error [{cmd}]: {e}")
        
        # Run file checks
        for check in (file_checks or []):
            path = self.project_root / check["path"]
            exists = path.exists()
            expected = check.get("exists", True)
            
            if expected != exists:
                state = "exists" if exists else "missing"
                expected_state = "exist" if expected else "not exist"
                failures.append(f"File check failed: {check['path']} should {expected_state} but is {state}")
            else:
                passes.append(f"File check passed: {check['path']}")
        
        if failures:
            return VerifyResult(
                complete=False, 
                reason="\n".join(failures)
            )
        
        summary = f"All {len(passes)} checks passed"
        return VerifyResult(complete=True, reason=summary)
    
    def to_cli_command(
        self, 
        test_commands: list[str] = None, 
        file_checks: list[dict] = None
    ) -> str:
        """
        Generate CLI command for Ralph's verifierCommand.
        
        This runs THIS module as a CLI and outputs JSON.
        """
        args = ["python", "-m", "src.executors.verifier"]
        
        for cmd in (test_commands or []):
            args.append(f"--test-command={cmd}")
        
        for check in (file_checks or []):
            args.append(f"--file-check={json.dumps(check)}")
        
        args.append(f"--project-root={self.project_root}")
        
        return " ".join(f'"{a}"' if " " in a else a for a in args)


def main():
    """CLI entrypoint. Outputs JSON for Ralph verifier consumption."""
    parser = argparse.ArgumentParser(description="Deterministic verifier")
    parser.add_argument("--test-command", action="append", default=[], 
                       help="Test command (repeatable)")
    parser.add_argument("--file-check", action="append", default=[],
                       help="File check as JSON (repeatable)")
    parser.add_argument("--project-root", default=".",
                       help="Project root directory")
    
    args = parser.parse_args()
    
    # Parse file checks
    file_checks = []
    for fc in args.file_check:
        try:
            file_checks.append(json.loads(fc))
        except json.JSONDecodeError:
            print(json.dumps({
                "complete": False,
                "reason": f"Invalid file check JSON: {fc}"
            }))
            sys.exit(1)
    
    verifier = Verifier(Path(args.project_root))
    result = verifier.verify(
        test_commands=args.test_command,
        file_checks=file_checks,
    )
    
    # Always output JSON for Ralph
    print(result.to_json())
    sys.exit(0 if result.complete else 1)


if __name__ == "__main__":
    main()
