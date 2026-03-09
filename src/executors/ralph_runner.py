"""
Ralph Runner: subprocess wrapper to Node.js Ralph package.

This runs the ACTUAL Ralph, not a reimplementation.
Version is detected at runtime from package-lock.json.
"""
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class RalphSpec:
    """Input spec for Ralph execution."""
    prompt: str
    instructions: str
    project_root: str
    allowed_paths: list[str]
    verifier_command: str
    model: str = "claude-sonnet-4-20250514"
    stop_conditions: list[dict] = None
    
    def to_json(self) -> str:
        return json.dumps({
            "prompt": self.prompt,
            "instructions": self.instructions,
            "model": self.model,
            "projectRoot": self.project_root,
            "allowedPaths": self.allowed_paths,
            "stopConditions": self.stop_conditions or [{"type": "iterations", "value": 10}],
            "verifierCommand": self.verifier_command,
        })


@dataclass
class RalphResult:
    """Output from Ralph execution."""
    success: bool
    iterations: int
    completion_reason: str  # 'verified' | 'max-iterations' | 'aborted' | 'error'
    reason: Optional[str]
    total_usage: dict
    duration_ms: int
    logs: list[dict]
    raw_output: str
    ralph_version: Optional[str] = None
    provenance: Optional[dict] = None  # Full provenance from Ralph CLI


class RalphRunner:
    """Runs actual Ralph via Node subprocess."""
    
    def __init__(self, ralph_cli_dir: Path):
        self.ralph_cli_dir = Path(ralph_cli_dir)
        self._ralph_version: Optional[str] = None
    
    def ensure_installed(self) -> None:
        """Ensure Ralph CLI dependencies are installed."""
        if not (self.ralph_cli_dir / "node_modules").exists():
            subprocess.run(
                ["npm", "install"],
                cwd=self.ralph_cli_dir,
                check=True,
                capture_output=True,
            )
    
    def get_ralph_version(self) -> str:
        """
        Get pinned Ralph version at runtime.
        Reads from package-lock.json or npm ls.
        """
        if self._ralph_version:
            return self._ralph_version
        
        # Try package-lock.json first
        lock_file = self.ralph_cli_dir / "package-lock.json"
        if lock_file.exists():
            try:
                with open(lock_file) as f:
                    lock = json.load(f)
                    deps = lock.get("packages", {}).get("node_modules/ralph-loop-agent", {})
                    version = deps.get("version")
                    if version:
                        self._ralph_version = f"ralph-loop-agent@{version}"
                        return self._ralph_version
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Fallback to npm ls
        try:
            result = subprocess.run(
                ["npm", "ls", "ralph-loop-agent", "--json"],
                cwd=self.ralph_cli_dir,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            deps = data.get("dependencies", {}).get("ralph-loop-agent", {})
            version = deps.get("version", "unknown")
            self._ralph_version = f"ralph-loop-agent@{version}"
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            self._ralph_version = "ralph-loop-agent@unknown"
        
        return self._ralph_version
    
    def run(self, spec: RalphSpec, timeout: int = 600) -> RalphResult:
        """
        Execute Ralph with given spec.
        
        Args:
            spec: Task specification
            timeout: Max seconds to wait
            
        Returns:
            RalphResult with execution details
        """
        self.ensure_installed()
        
        try:
            proc = subprocess.run(
                ["node", "run-ralph.js"],
                cwd=self.ralph_cli_dir,
                input=spec.to_json(),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return RalphResult(
                success=False,
                iterations=0,
                completion_reason="error",
                reason=f"Execution timeout ({timeout}s)",
                total_usage={},
                duration_ms=timeout * 1000,
                logs=[],
                raw_output="",
                ralph_version=self.get_ralph_version(),
            )
        
        try:
            data = json.loads(proc.stdout)
            provenance = data.get("provenance", {})
            ralph_version = f"{provenance.get('package', 'ralph-loop-agent')}@{provenance.get('version', 'unknown')}"
            
            return RalphResult(
                success=data.get("success", False),
                iterations=data.get("iterations", 0),
                completion_reason=data.get("completionReason", "error"),
                reason=data.get("reason"),
                total_usage=data.get("totalUsage", {}),
                duration_ms=data.get("durationMs", 0),
                logs=data.get("logs", []),
                raw_output=proc.stdout,
                ralph_version=ralph_version,
                provenance=provenance,
            )
        except json.JSONDecodeError:
            return RalphResult(
                success=False,
                iterations=0,
                completion_reason="error",
                reason=f"Failed to parse output: {proc.stderr[:500]}",
                total_usage={},
                duration_ms=0,
                logs=[],
                raw_output=proc.stdout,
                ralph_version=self.get_ralph_version(),
                provenance=None,
            )
