"""
LangGraph state definitions for the RSS-to-Grounded-Summary pipeline.

This module defines the RunState that flows through the graph, including:
- Message accumulation with LangGraph's add_messages
- Evidence tracking
- Circuit breaker for loop prevention
"""

from typing import Annotated, Any, Dict, List, Optional
from enum import Enum

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ItemStatus(str, Enum):
    """Status of an item in the evidence lifecycle."""
    FETCHED = "fetched"
    SUMMARIZED = "summarized"
    FAILED = "failed"


class CircuitBreaker(BaseModel):
    """
    Tracks execution metrics to prevent infinite loops and runaway retries.
    
    The circuit breaker will trip when:
    - step_count exceeds max_steps (default: 50)
    - retry_count exceeds max_retries (default: 3)
    - Same plan_fingerprint appears consecutively (indicates loop)
    """
    
    step_count: int = Field(
        default=0,
        description="Total number of steps executed in this run"
    )
    retry_count: int = Field(
        default=0,
        description="Number of consecutive retries for current action"
    )
    plan_fingerprint: str = Field(
        default="",
        description="Hash of the last plan to detect loops"
    )
    max_steps: int = Field(
        default=50,
        description="Maximum allowed steps before circuit trips"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retries for a single action"
    )

    def should_trip(self) -> bool:
        """Check if the circuit breaker should trip."""
        return self.step_count >= self.max_steps or self.retry_count >= self.max_retries

    def increment_step(self) -> "CircuitBreaker":
        """Return a new CircuitBreaker with incremented step count."""
        return self.model_copy(update={"step_count": self.step_count + 1})

    def increment_retry(self) -> "CircuitBreaker":
        """Return a new CircuitBreaker with incremented retry count."""
        return self.model_copy(update={"retry_count": self.retry_count + 1})

    def reset_retries(self) -> "CircuitBreaker":
        """Return a new CircuitBreaker with reset retry count."""
        return self.model_copy(update={"retry_count": 0})


class RunState(BaseModel):
    """
    The main state object that flows through the LangGraph pipeline.
    
    This state accumulates messages, tracks evidence, and monitors execution
    via the circuit breaker. All agent nodes read from and write to this state.
    """
    
    # Message history with LangGraph's reducer for proper accumulation
    messages: Annotated[List[BaseMessage], add_messages] = Field(
        default_factory=list,
        description="Accumulated message history from all agents"
    )
    
    # Evidence tracking - maps evidence IDs to their metadata
    evidence_map: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Map of evidence_id -> metadata (type, source, timestamp, etc.)"
    )
    
    # NEW: Lifecycle Tracking
    item_lifecycle: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Tracks status and retries for each evidence item"
    )
    
    # NEW: Efficacy Telemetry
    telemetry: Dict[str, Any] = Field(
        default_factory=lambda: {
            "planned_steps": 0,
            "successful_steps": 0,
            "wasted_tokens": 0,
            "alignment_score": 0.0,
            # Security telemetry (Prompt V)
            "grounding_failures": 0,
            "evidence_rejections": 0,
            "reuse_denied_reason": None,
            "security_mode": "normal"  # normal | zero_trust | abort
        },
        description="Metrics for agent performance, cost, and security events"
    )
    
    # NEW: Context Buffer
    working_summary: str = Field(
        default="",
        description="Bounded summary of current insights to focus LLM"
    )
    
    # NEW: Deterministic Identity Context (DTL)
    identity_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured identity facts from Authoritative Identity Store (max 500 chars serialized)"
    )
    
    # Current execution plan from the planner agent
    current_plan: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The current plan being executed, including steps and goals"
    )
    
    # Circuit breaker for safety
    circuit_breaker: CircuitBreaker = Field(
        default_factory=CircuitBreaker,
        description="Tracks steps, retries, and detects loops"
    )

    final_report: Optional[str] = Field(
        default=None,
        description="Markdown report generated at the end of the run"
    )
    
    # Structured report data
    structured_report: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured summary data (executive summary, sentiment, etc.)"
    )

    # NEW: Approved action from sanitizer
    approved_action: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The action validated and approved by the sanitizer"
    )

    class Config:
        # Allow arbitrary types for LangChain message objects
        arbitrary_types_allowed = True
        
        json_schema_extra = {
            "example": {
                "messages": [],
                "evidence_map": {
                    "ev_001": {
                        "type": "rss_feed",
                        "source": "https://example.com/feed.xml",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                },
                "current_plan": {
                    "goal": "Summarize latest AI news",
                    "steps": ["fetch_rss", "extract_content", "summarize"]
                },
                "circuit_breaker": {
                    "step_count": 5,
                    "retry_count": 0,
                    "plan_fingerprint": "abc123"
                }
            }
        }

    def add_evidence(self, evidence_id: str, metadata: Dict[str, Any]) -> "RunState":
        """Add evidence to the map and return updated state."""
        new_map = {**self.evidence_map, evidence_id: metadata}
        return self.model_copy(update={"evidence_map": new_map})

    def get_evidence_ids(self) -> List[str]:
        """Get all evidence IDs in the current state."""
        return list(self.evidence_map.keys())
