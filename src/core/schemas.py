"""
Core Pydantic schemas for the LangGraph RSS-to-Grounded-Summary pipeline.

This module defines the contract models that ensure type safety and validation
across all agent interactions:
- ProposedAction: What an agent wants to do
- ToolResult: What happened when a tool was executed
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorClass(str, Enum):
    """Classification of tool execution errors for retry logic."""
    
    TRANSIENT = "transient"      # Temporary failure, worth retrying (network, rate limit)
    PERMANENT = "permanent"      # Will never succeed (bad input, missing resource)
    VALIDATION = "validation"    # Schema/format error in input or output
    TIMEOUT = "timeout"          # Operation exceeded time limit


class ProposedAction(BaseModel):
    """
    Contract for agent-proposed actions.
    
    This is the standardized format that agents use to propose tool calls.
    The plan_fingerprint enables the circuit breaker to detect infinite loops.
    """
    
    action_type: str = Field(
        ...,
        description="Type of action: 'tool_call', 'delegate', 'terminate'"
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool to invoke"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters to pass to the tool"
    )
    success_criteria: List[str] = Field(
        default_factory=list,
        description="Conditions that must be met for the action to be considered successful"
    )
    plan_fingerprint: str = Field(
        ...,
        description="Hash of the plan that generated this action, for loop detection"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "action_type": "tool_call",
                "tool_name": "fetch_rss",
                "params": {"url": "https://example.com/feed.xml"},
                "success_criteria": ["status_code == 200", "items_count > 0"],
                "plan_fingerprint": "abc123def456"
            }
        }


class ToolResult(BaseModel):
    """
    Standardized response from tool execution.
    
    Every tool must return this format to ensure consistent error handling
    and evidence tracking across the pipeline.
    """
    
    status: str = Field(
        ...,
        description="Execution outcome: 'success' or 'fail'"
    )
    error_class: Optional[ErrorClass] = Field(
        default=None,
        description="Error classification if status is 'fail'"
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of what happened"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="IDs of evidence artifacts created during execution"
    )
    payload_ref: Optional[str] = Field(
        default=None,
        description="Reference to the full payload in the evidence store"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "error_class": None,
                "summary": "Fetched 10 RSS items from feed",
                "evidence_ids": ["ev_001", "ev_002"],
                "payload_ref": "payload_abc123"
            }
        }

    def is_success(self) -> bool:
        """Check if the tool execution was successful."""
        return self.status == "success"

    def is_retryable(self) -> bool:
        """Check if the error is transient and worth retrying."""
        return self.error_class in (ErrorClass.TRANSIENT, ErrorClass.TIMEOUT)


class StructuredSummary(BaseModel):
    """
    Structured report format for CompleteTask actions.
    """
    executive_summary: str = Field(
        ...,
        description="High-level overview suitable for executive slides"
    )
    key_entities: List[str] = Field(
        default_factory=list,
        description="List of key organizations, people, or concepts mentioned"
    )
    sentiment_score: int = Field(
        ...,
        description="Overall sentiment score from 1 (negative) to 10 (positive)"
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="List of evidence IDs that were used to generate this report"
    )
    report_body_markdown: str = Field(
        ...,
        description="Full detailed report in Markdown format"
    )
