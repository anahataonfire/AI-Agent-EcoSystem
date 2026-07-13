"""Base Executor interface for the AI Agent EcoSystem."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutorResult:
    """Result of an executor invocation."""
    task_id: str
    success: bool
    iterations: int
    completion_reason: str  # 'verified' | 'max_iterations' | 'aborted' | 'error'
    output: Optional[str] = None
    error: Optional[str] = None
    artifacts_changed: list[str] = field(default_factory=list)
    tests_run: list[dict] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    duration_ms: int = 0
    logs: list[dict] = field(default_factory=list)
    ralph_version: Optional[str] = None  # Runtime-detected


class ExecutorInterface(ABC):
    """Abstract base class for task executors."""
    
    @abstractmethod
    def execute(
        self,
        task_id: str,
        prompt: str,
        test_commands: list[str],
        allowed_paths: list[str],
        file_checks: list[dict] = None,
        max_rounds: int = 10,
        max_cost_usd: float = 5.0,
        max_tokens: int = 100000,
    ) -> ExecutorResult:
        """
        Execute a single task with binary pass/fail verification.
        
        Args:
            task_id: Unique identifier for this task
            prompt: The task prompt/instructions
            test_commands: Shell commands that must exit 0 for success
            allowed_paths: Sandbox paths for file operations
            file_checks: Optional [{path, exists: bool}] checks
            max_rounds: Maximum iterations
            max_cost_usd: Cost cap
            max_tokens: Token cap
            
        Returns:
            ExecutorResult with execution details
        """
        pass
    
    @abstractmethod
    def qualifies(self, task: dict) -> tuple[bool, str]:
        """
        Check if task qualifies for this executor.
        
        Returns:
            (qualifies, reason) tuple
        """
        pass
