"""
RalphExecutor: Ecosystem adapter that delegates to actual Ralph.

Does NOT reimplement Ralph. Calls the real package via subprocess.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

from .base_executor import ExecutorInterface, ExecutorResult
from .ralph_runner import RalphRunner, RalphSpec
from .verifier import Verifier


@dataclass 
class RalphConfig:
    """Configuration loaded from config/ralph_config.json."""
    max_rounds: int = 10
    max_cost_usd: float = 5.0
    max_tokens: int = 100000
    log_dir: str = "data/ralph_logs"
    ralph_cli_dir: str = "ralph-cli"
    # Kill switches (toggleable - ecosystem extensions)
    kill_on_repeated_failures: bool = True
    kill_on_sandbox_violation: bool = True
    # Vanilla mode disables ecosystem extensions
    vanilla_ralph_mode: bool = False


class RalphExecutor(ExecutorInterface):
    """
    Adapter that delegates to actual Ralph via subprocess.
    
    Does NOT reimplement Ralph. Calls the real package.
    """
    
    def __init__(self, project_root: Path, config: Optional[RalphConfig] = None):
        self.project_root = Path(project_root)
        self.config = config or self._load_config()
        self.runner = RalphRunner(self.project_root / self.config.ralph_cli_dir)
        self.verifier = Verifier(self.project_root)
        self.log_dir = self.project_root / self.config.log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> RalphConfig:
        """Load config from JSON file."""
        config_path = self.project_root / "config" / "ralph_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f).get("ralph_executor", {})
                    return RalphConfig(**{
                        k: v for k, v in data.items() 
                        if k in RalphConfig.__dataclass_fields__
                    })
            except (json.JSONDecodeError, TypeError):
                pass
        return RalphConfig()
    
    def qualifies(self, task: dict) -> tuple[bool, str]:
        """
        Deterministic qualification. Task MUST have:
        1. test_commands (binary verification)
        2. allowed_paths (sandbox)
        3. reasonable scope
        """
        if not task.get("test_commands"):
            return False, "Missing test_commands (binary verification required)"
        
        if not task.get("allowed_paths"):
            return False, "Missing allowed_paths (sandbox required)"
        
        scope = task.get("scope", {})
        if scope.get("estimated_files", 0) > 5:
            return False, "Scope too large (>5 files) - needs decomposition"
        
        if scope.get("requires_architecture_change"):
            return False, "Architecture changes not suitable for Ralph"
        
        return True, "Qualifies for Ralph execution"
    
    def execute(
        self,
        task_id: str,
        prompt: str,
        test_commands: list[str],
        allowed_paths: list[str],
        file_checks: list[dict] = None,
        max_rounds: int = None,
        max_cost_usd: float = None,
        max_tokens: int = None,
    ) -> ExecutorResult:
        """
        Execute via actual Ralph.
        
        Args:
            task_id: Unique task identifier
            prompt: Task prompt
            test_commands: Commands that must exit 0
            allowed_paths: Sandbox paths
            file_checks: Optional file existence checks
            max_rounds: Override config max_rounds
            max_cost_usd: Override config max_cost
            max_tokens: Override config max_tokens
        """
        # Use config values or overrides
        rounds = max_rounds or self.config.max_rounds
        cost = max_cost_usd or self.config.max_cost_usd
        tokens = max_tokens or self.config.max_tokens
        
        # Build verifier CLI command
        verifier_cmd = self.verifier.to_cli_command(
            test_commands=test_commands,
            file_checks=file_checks or [],
        )
        
        # Build stop conditions (all three types per Ralph contract)
        stop_conditions = [
            {"type": "iterations", "value": rounds},
            {"type": "cost", "value": cost},
            {"type": "tokens", "value": tokens},
        ]
        
        # Build spec
        spec = RalphSpec(
            prompt=prompt,
            instructions=self._build_instructions(allowed_paths),
            project_root=str(self.project_root),
            allowed_paths=allowed_paths,
            stop_conditions=stop_conditions,
            verifier_command=verifier_cmd,
        )
        
        # Run actual Ralph
        result = self.runner.run(spec)
        
        # Calculate duration from logs if not provided
        duration_ms = result.duration_ms
        if duration_ms == 0 and result.logs:
            duration_ms = self._calculate_duration_from_logs(result.logs)
        
        # Write execution ledger
        self._write_ledger(task_id, spec, result)
        
        return ExecutorResult(
            task_id=task_id,
            success=result.success,
            iterations=result.iterations,
            completion_reason=result.completion_reason,
            output=result.reason,
            error=None if result.success else result.reason,
            total_cost_usd=self._extract_cost(result.total_usage),
            total_tokens=result.total_usage.get("totalTokens", 0),
            duration_ms=duration_ms,
            logs=result.logs,
            ralph_version=result.ralph_version,
        )
    
    def _build_instructions(self, allowed_paths: list[str]) -> str:
        """Build system instructions for Ralph."""
        return f"""You are executing a task in a sandboxed environment.

CRITICAL RULES:
1. Only modify files within these allowed paths: {allowed_paths}
2. All file operations outside allowed paths will be BLOCKED
3. Use the provided tools (read_file, write_file, apply_patch, run_tests, list_files)
4. Focus on making the verification tests pass

Working directory: {self.project_root}
"""
    
    def _calculate_duration_from_logs(self, logs: list[dict]) -> int:
        """Calculate total duration from log timestamps."""
        if len(logs) < 2:
            return 0
        
        try:
            first_ts = logs[0].get("ts", "")
            last_ts = logs[-1].get("ts", "")
            if first_ts and last_ts:
                first = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                last = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                return int((last - first).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass
        
        # Fallback: sum iteration durations
        total = sum(
            log.get("duration_ms", 0) 
            for log in logs 
            if log.get("event") == "iteration_end"
        )
        return total
    
    def _extract_cost(self, usage: dict) -> float:
        """Extract cost from usage dict."""
        if "totalCost" in usage:
            return usage["totalCost"]
        # Estimate based on tokens if cost not provided
        # Claude Sonnet: ~$3/M input, ~$15/M output
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        return (input_tokens * 3 + output_tokens * 15) / 1_000_000
    
    def _write_ledger(self, task_id: str, spec: RalphSpec, result) -> None:
        """Write execution ledger with all Ralph details."""
        ledger = {
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ralph_version": result.ralph_version,
            "spec": {
                "prompt": spec.prompt[:500],  # Truncate for ledger
                "allowed_paths": spec.allowed_paths,
                "stop_conditions": spec.stop_conditions,
                "verifier_command": spec.verifier_command,
            },
            "result": {
                "success": result.success,
                "iterations": result.iterations,
                "completion_reason": result.completion_reason,
                "reason": result.reason,
                "total_usage": result.total_usage,
                "duration_ms": result.duration_ms,
            },
            "logs": result.logs,
        }
        
        ledger_file = self.log_dir / f"{task_id}.json"
        with open(ledger_file, "w") as f:
            json.dump(ledger, f, indent=2)


class StandardExecutor(ExecutorInterface):
    """Fallback executor for non-Ralph tasks."""
    
    def execute(self, task_id: str, prompt: str, **kwargs) -> ExecutorResult:
        raise NotImplementedError(
            "StandardExecutor is a placeholder. Use DTLOrchestrator.run() directly."
        )
    
    def qualifies(self, task: dict) -> tuple[bool, str]:
        return True, "Standard executor accepts all tasks"
