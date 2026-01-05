"""
LLM Cost Tracker for telemetry enrichment.

Tracks token usage per run and calculates estimated costs in USD
based on model pricing. Integrates with telemetry for cost visibility.
"""

from dataclasses import dataclass
from typing import Dict, Optional


# Cost per 1M tokens (USD) - Update as pricing changes
# Source: https://ai.google.dev/pricing
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    # Gemini 2.0
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash-lite": {"input": 0.0375, "output": 0.15},
    
    # Gemini 1.5
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    
    # Fallback for unknown models
    "default": {"input": 0.10, "output": 0.40},
}


@dataclass
class RunCost:
    """Cost tracking for a single run."""
    input_tokens: int = 0
    output_tokens: int = 0
    model_id: str = "gemini-2.0-flash"
    call_count: int = 0
    
    @property
    def estimated_cost_usd(self) -> float:
        """Calculate estimated cost in USD."""
        costs = MODEL_COSTS.get(self.model_id, MODEL_COSTS["default"])
        input_cost = (self.input_tokens / 1_000_000) * costs["input"]
        output_cost = (self.output_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 6)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model_id": self.model_id,
            "call_count": self.call_count,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


class CostTracker:
    """
    Tracks LLM costs across runs.
    
    Usage:
        tracker = CostTracker()
        tracker.record("run-1", "gemini-2.0-flash", 1000, 500)
        cost = tracker.get_run_cost("run-1")
    """
    
    def __init__(self):
        self._runs: Dict[str, RunCost] = {}
    
    def record(
        self, 
        run_id: str, 
        model_id: str, 
        input_tokens: int, 
        output_tokens: int
    ):
        """
        Record token usage for a run.
        
        Args:
            run_id: Unique run identifier
            model_id: The model used (e.g., "gemini-2.0-flash")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if run_id not in self._runs:
            self._runs[run_id] = RunCost(model_id=model_id)
        
        run = self._runs[run_id]
        run.input_tokens += input_tokens
        run.output_tokens += output_tokens
        run.call_count += 1
        
        # Update model_id if different (use latest)
        if model_id != run.model_id:
            run.model_id = model_id
    
    def get_run_cost(self, run_id: str) -> float:
        """
        Get estimated cost for a run in USD.
        
        Args:
            run_id: The run identifier
            
        Returns:
            Estimated cost in USD, 0.0 if run not found
        """
        if run_id in self._runs:
            return self._runs[run_id].estimated_cost_usd
        return 0.0
    
    def get_run_stats(self, run_id: str) -> Optional[dict]:
        """
        Get full stats for a run.
        
        Args:
            run_id: The run identifier
            
        Returns:
            Dict with token counts, cost, etc. or None
        """
        if run_id in self._runs:
            return self._runs[run_id].to_dict()
        return None
    
    def get_telemetry_enrichment(self, run_id: str) -> dict:
        """
        Get cost data formatted for telemetry enrichment.
        
        Args:
            run_id: The run identifier
            
        Returns:
            Dict with cost fields to merge into telemetry
        """
        if run_id not in self._runs:
            return {}
        
        run = self._runs[run_id]
        return {
            "cost_usd": run.estimated_cost_usd,
            "llm_input_tokens": run.input_tokens,
            "llm_output_tokens": run.output_tokens,
            "llm_call_count": run.call_count,
        }
    
    def clear_run(self, run_id: str):
        """Remove a run from tracking (for cleanup)."""
        if run_id in self._runs:
            del self._runs[run_id]


# Singleton instance
_tracker = CostTracker()


def record_llm_usage(
    run_id: str, 
    model_id: str, 
    input_tokens: int, 
    output_tokens: int
):
    """
    Record LLM token usage for cost tracking.
    
    Args:
        run_id: Unique run identifier
        model_id: Model used (e.g., "gemini-2.0-flash")
        input_tokens: Input token count
        output_tokens: Output token count
    """
    _tracker.record(run_id, model_id, input_tokens, output_tokens)


def get_run_cost(run_id: str) -> float:
    """
    Get estimated cost for a run.
    
    Args:
        run_id: The run identifier
        
    Returns:
        Cost in USD
    """
    return _tracker.get_run_cost(run_id)


def get_run_stats(run_id: str) -> Optional[dict]:
    """
    Get full usage stats for a run.
    
    Args:
        run_id: The run identifier
        
    Returns:
        Dict with usage details or None
    """
    return _tracker.get_run_stats(run_id)


def enrich_telemetry(run_id: str, telemetry: dict) -> dict:
    """
    Enrich telemetry dict with cost data.
    
    Args:
        run_id: The run identifier
        telemetry: Existing telemetry dict
        
    Returns:
        Telemetry dict with cost fields added
    """
    enrichment = _tracker.get_telemetry_enrichment(run_id)
    return {**telemetry, **enrichment}
