"""
LangGraph state definitions for the RSS-to-Grounded-Summary pipeline.

This module defines the RunState that flows through the graph, with:
- LAYERED ARCHITECTURE (P1 Fix):
  - ImmutableInputs: Query, identity, config snapshot (frozen at start)
  - ExecutionArtifacts: Tool results, evidence refs (write-once per step)
  - DerivedViews: Working summary, draft report (computed from artifacts)
- Message accumulation with LangGraph's add_messages
- Evidence tracking with lifecycle
- Circuit breaker for loop prevention
"""

from typing import Annotated, Any, Dict, FrozenSet, List, Optional
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
        default=100,
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


# ============================================================================
# LAYERED STATE ARCHITECTURE (P1 Fix)
# ============================================================================

class ImmutableInputs(BaseModel):
    """
    Frozen inputs set at run start. Should NEVER be modified during execution.
    
    This layer contains:
    - Original user query
    - Identity snapshot (facts known at start)
    - Config snapshot (kill switches, mode flags)
    """
    
    user_query: str = Field(
        default="",
        description="Original user query text (frozen)"
    )
    
    run_id: str = Field(
        default="",
        description="Unique identifier for this run"
    )
    
    identity_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Identity facts frozen at run start"
    )
    
    config_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Kill switches and config frozen at run start"
    )
    
    execution_mode: str = Field(
        default="development",
        description="Execution mode: 'production' or 'development'"
    )
    
    class Config:
        frozen = True  # Make immutable


class ExecutionArtifacts(BaseModel):
    """
    Artifacts produced during execution. Write-once per step.
    
    This layer contains:
    - Evidence map (ID → metadata)
    - Tool results
    - Item lifecycle tracking
    """
    
    evidence_map: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Map of evidence_id → metadata"
    )
    
    item_lifecycle: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Tracks status and retries for each evidence item"
    )
    
    last_tool_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Result from the most recent tool execution"
    )
    
    current_plan: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The current plan being executed"
    )
    
    approved_action: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The action validated by sanitizer"
    )


class DerivedViews(BaseModel):
    """
    Computed views derived from artifacts. Regenerable.
    
    This layer contains:
    - Working summary
    - Draft report
    - Telemetry metrics
    """
    
    working_summary: str = Field(
        default="",
        description="Bounded summary of current insights"
    )
    
    draft_report: Optional[str] = Field(
        default=None,
        description="Work-in-progress report markdown"
    )
    
    telemetry: Dict[str, Any] = Field(
        default_factory=lambda: {
            "planned_steps": 0,
            "successful_steps": 0,
            "wasted_tokens": 0,
            "alignment_score": 0.0,
            "grounding_failures": 0,
            "evidence_rejections": 0,
            "reuse_denied_reason": None,
            "security_mode": "normal",
        },
        description="Metrics for performance, cost, and security"
    )


# ============================================================================
# MAIN RUN STATE
# ============================================================================

class RunState(BaseModel):
    """
    The main state object that flows through the LangGraph pipeline.
    
    LAYERED ARCHITECTURE:
    - inputs: ImmutableInputs (frozen at start)
    - artifacts: ExecutionArtifacts (write-once per step)
    - views: DerivedViews (computed/regenerable)
    
    Plus message history and circuit breaker for LangGraph integration.
    """
    
    # ========== LAYERED STATE ==========
    
    inputs: ImmutableInputs = Field(
        default_factory=ImmutableInputs,
        description="Frozen inputs set at run start"
    )
    
    artifacts: ExecutionArtifacts = Field(
        default_factory=ExecutionArtifacts,
        description="Artifacts produced during execution"
    )
    
    views: DerivedViews = Field(
        default_factory=DerivedViews,
        description="Computed views derived from artifacts"
    )
    
    # ========== LANGGRAPH INTEGRATION ==========
    
    # Message history with LangGraph's reducer for proper accumulation
    messages: Annotated[List[BaseMessage], add_messages] = Field(
        default_factory=list,
        description="Accumulated message history from all agents"
    )
    
    # Circuit breaker for safety
    circuit_breaker: CircuitBreaker = Field(
        default_factory=CircuitBreaker,
        description="Tracks steps, retries, and detects loops"
    )
    
    # ========== OUTPUT ==========
    
    final_report: Optional[str] = Field(
        default=None,
        description="Markdown report generated at the end of the run"
    )
    
    structured_report: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured summary data (executive summary, sentiment, etc.)"
    )
    
    # ========== BACKWARD COMPATIBILITY ALIASES ==========
    # These properties provide backward compatibility with existing code
    
    @property
    def evidence_map(self) -> Dict[str, Dict[str, Any]]:
        """Backward compatibility: access via artifacts layer."""
        return self.artifacts.evidence_map
    
    @property
    def item_lifecycle(self) -> Dict[str, Dict[str, Any]]:
        """Backward compatibility: access via artifacts layer."""
        return self.artifacts.item_lifecycle
    
    @property
    def telemetry(self) -> Dict[str, Any]:
        """Backward compatibility: access via views layer."""
        return self.views.telemetry
    
    @property
    def working_summary(self) -> str:
        """Backward compatibility: access via views layer."""
        return self.views.working_summary
    
    @property
    def identity_context(self) -> Optional[Dict[str, Any]]:
        """Backward compatibility: access via inputs layer."""
        return self.inputs.identity_snapshot or None
    
    @property
    def current_plan(self) -> Optional[Dict[str, Any]]:
        """Backward compatibility: access via artifacts layer."""
        return self.artifacts.current_plan
    
    @property
    def approved_action(self) -> Optional[Dict[str, Any]]:
        """Backward compatibility: access via artifacts layer."""
        return self.artifacts.approved_action

    class Config:
        # Allow arbitrary types for LangChain message objects
        arbitrary_types_allowed = True
        
        json_schema_extra = {
            "example": {
                "inputs": {
                    "user_query": "Summarize latest AI news",
                    "run_id": "RUN-20260104_120000",
                    "execution_mode": "production"
                },
                "artifacts": {
                    "evidence_map": {
                        "ev_001": {
                            "type": "rss_item",
                            "source": "https://example.com/feed.xml"
                        }
                    }
                },
                "views": {
                    "telemetry": {"planned_steps": 3, "successful_steps": 2}
                },
                "circuit_breaker": {
                    "step_count": 5,
                    "retry_count": 0
                }
            }
        }

    def add_evidence(self, evidence_id: str, metadata: Dict[str, Any]) -> "RunState":
        """Add evidence to the map and return updated state."""
        new_map = {**self.artifacts.evidence_map, evidence_id: metadata}
        new_artifacts = self.artifacts.model_copy(update={"evidence_map": new_map})
        return self.model_copy(update={"artifacts": new_artifacts})

    def get_evidence_ids(self) -> List[str]:
        """Get all evidence IDs in the current state."""
        return list(self.artifacts.evidence_map.keys())
    
    def freeze_inputs(
        self, 
        user_query: str, 
        run_id: str,
        identity_snapshot: Dict[str, Any] = None,
        config_snapshot: Dict[str, Any] = None,
        execution_mode: str = "development"
    ) -> "RunState":
        """
        Freeze inputs at run start. Should only be called once.
        
        Args:
            user_query: The original user query
            run_id: Unique run identifier
            identity_snapshot: Identity facts to freeze
            config_snapshot: Config/kill switches to freeze
            execution_mode: "production" or "development"
        
        Returns:
            New RunState with frozen inputs
        """
        frozen = ImmutableInputs(
            user_query=user_query,
            run_id=run_id,
            identity_snapshot=identity_snapshot or {},
            config_snapshot=config_snapshot or {},
            execution_mode=execution_mode,
        )
        return self.model_copy(update={"inputs": frozen})
