"""
Content data models for the Smart Curator system.

Defines schemas for content entries, action items, queue records,
and deep analysis results with routing.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import hashlib
import secrets


class ContentStatus(Enum):
    """Status of a content entry in the system."""
    PENDING = "pending"      # In queue, not yet processed
    UNREAD = "unread"        # Processed but not reviewed by user
    READ = "read"            # User has reviewed
    IMPLEMENTED = "implemented"  # Action items completed
    ARCHIVED = "archived"    # No longer active


class ActionType(Enum):
    """Type of action item identified from content."""
    ENHANCEMENT = "enhancement"  # Potential improvement to codebase
    CORRECTION = "correction"    # Bug fix or error correction
    RESEARCH = "research"        # Needs further investigation
    DOCUMENTATION = "documentation"  # Docs improvement
    IDEA = "idea"               # General idea for future


class RouteDestination(Enum):
    """Closed-set routing destinations for content."""
    LIBRARY_ONLY = "LIBRARY_ONLY"
    PLANNER_TASK = "PLANNER_TASK"
    MONITORING = "MONITORING"
    KNOWLEDGE_UPDATE = "KNOWLEDGE_UPDATE"
    NOTEBOOKLM_DATAMART = "NOTEBOOKLM_DATAMART"


class SystemAction(Enum):
    """Closed-set system actions."""
    STORE = "STORE"
    ANALYZE = "ANALYZE"
    BUNDLE = "BUNDLE"
    NOTIFY = "NOTIFY"
    DEFER = "DEFER"
    SKIP = "SKIP"


class UncertaintyFlag(Enum):
    """Flags indicating uncertainty in analysis."""
    AMBIGUOUS_CONTENT = "AMBIGUOUS_CONTENT"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    LOW_EVIDENCE = "LOW_EVIDENCE"
    TEMPORAL_UNCERTAINTY = "TEMPORAL_UNCERTAINTY"
    TOPIC_MISMATCH = "TOPIC_MISMATCH"
    NOVELTY_HIGH = "NOVELTY_HIGH"


@dataclass
class ActionItem:
    """An action item extracted from content analysis."""
    action_type: ActionType
    description: str
    related_files: list[str] = field(default_factory=list)
    priority: int = 3  # 1=high, 5=low
    
    def to_dict(self) -> dict:
        return {
            "type": self.action_type.value,
            "description": self.description,
            "related_files": self.related_files,
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActionItem":
        return cls(
            action_type=ActionType(data["type"]),
            description=data["description"],
            related_files=data.get("related_files", []),
            priority=data.get("priority", 3),
        )


@dataclass
class GroundedClaim:
    """A factual claim with required evidence pointer."""
    claim: str
    evidence_id: str  # Must match pattern: ev_[a-f0-9]{10}
    confidence: float = 0.8
    
    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "evidence_id": self.evidence_id,
            "confidence": self.confidence,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GroundedClaim":
        return cls(
            claim=data["claim"],
            evidence_id=data["evidence_id"],
            confidence=data.get("confidence", 0.8),
        )


@dataclass
class DatamartAssignment:
    """Assignment details for NOTEBOOKLM_DATAMART route."""
    topic_id: str
    topic_name: Optional[str] = None
    relevance_to_topic: float = 0.8
    suggested_tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "relevance_to_topic": self.relevance_to_topic,
            "suggested_tags": self.suggested_tags,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DatamartAssignment":
        return cls(
            topic_id=data["topic_id"],
            topic_name=data.get("topic_name"),
            relevance_to_topic=data.get("relevance_to_topic", 0.8),
            suggested_tags=data.get("suggested_tags", []),
        )


@dataclass
class TaskDetails:
    """Details for PLANNER_TASK route."""
    description: str
    priority: int = 3
    
    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "priority": self.priority,
        }


@dataclass
class MonitoringDetails:
    """Details for MONITORING route."""
    check_interval_hours: int = 24
    expiry_date: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "check_interval_hours": self.check_interval_hours,
            "expiry_date": self.expiry_date,
        }


def generate_analysis_id() -> str:
    """Generate a unique analysis ID."""
    return f"ANALYSIS-{secrets.token_hex(4).upper()}"


@dataclass
class DeepAnalysisResult:
    """
    Result of deep content analysis with routing decision.
    
    All routing is via closed-set enums, no free-text commands.
    All claims must have evidence pointers.
    """
    analysis_id: str
    content_id: str
    url: str
    analysis_ts: str
    confidence_score: float  # 0.0-1.0; below 0.6 forces LIBRARY_ONLY
    route_destination: RouteDestination
    system_actions: list[SystemAction]
    grounded_claims: list[GroundedClaim]
    evidence_refs: list[str]  # All evidence IDs referenced
    uncertainty_flags: list[UncertaintyFlag] = field(default_factory=list)
    datamart_assignment: Optional[DatamartAssignment] = None
    task_details: Optional[TaskDetails] = None
    monitoring_details: Optional[MonitoringDetails] = None
    novelty_score: int = 0  # 0-10
    policy_name: Optional[str] = None
    policy_version: Optional[str] = None
    run_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {
            "analysis_id": self.analysis_id,
            "content_id": self.content_id,
            "url": self.url,
            "analysis_ts": self.analysis_ts,
            "confidence_score": self.confidence_score,
            "route_destination": self.route_destination.value,
            "system_actions": [a.value for a in self.system_actions],
            "grounded_claims": [c.to_dict() for c in self.grounded_claims],
            "evidence_refs": self.evidence_refs,
            "uncertainty_flags": [f.value for f in self.uncertainty_flags],
            "novelty_score": self.novelty_score,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "run_id": self.run_id,
        }
        
        if self.datamart_assignment:
            result["datamart_assignment"] = self.datamart_assignment.to_dict()
        if self.task_details:
            result["task_details"] = self.task_details.to_dict()
        if self.monitoring_details:
            result["monitoring_details"] = self.monitoring_details.to_dict()
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "DeepAnalysisResult":
        return cls(
            analysis_id=data["analysis_id"],
            content_id=data["content_id"],
            url=data["url"],
            analysis_ts=data["analysis_ts"],
            confidence_score=data["confidence_score"],
            route_destination=RouteDestination(data["route_destination"]),
            system_actions=[SystemAction(a) for a in data["system_actions"]],
            grounded_claims=[GroundedClaim.from_dict(c) for c in data.get("grounded_claims", [])],
            evidence_refs=data.get("evidence_refs", []),
            uncertainty_flags=[UncertaintyFlag(f) for f in data.get("uncertainty_flags", [])],
            datamart_assignment=DatamartAssignment.from_dict(data["datamart_assignment"]) if data.get("datamart_assignment") else None,
            task_details=TaskDetails(**data["task_details"]) if data.get("task_details") else None,
            monitoring_details=MonitoringDetails(**data["monitoring_details"]) if data.get("monitoring_details") else None,
            novelty_score=data.get("novelty_score", 0),
            policy_name=data.get("policy_name"),
            policy_version=data.get("policy_version"),
            run_id=data.get("run_id"),
        )
    
    def validate(self) -> list[str]:
        """
        Validate the analysis result.
        
        Returns list of validation errors (empty if valid).
        """
        errors = []
        
        # Check confidence gating
        if self.confidence_score < 0.6 and self.route_destination != RouteDestination.LIBRARY_ONLY:
            errors.append("Low confidence (<0.6) must route to LIBRARY_ONLY")
        
        # Check evidence refs exist for all claims
        for claim in self.grounded_claims:
            if claim.evidence_id not in self.evidence_refs:
                errors.append(f"Claim evidence_id {claim.evidence_id} not in evidence_refs")
        
        # Check conditional fields
        if self.route_destination == RouteDestination.NOTEBOOKLM_DATAMART:
            if not self.datamart_assignment:
                errors.append("NOTEBOOKLM_DATAMART requires datamart_assignment")
        
        if self.route_destination == RouteDestination.PLANNER_TASK:
            if not self.task_details:
                errors.append("PLANNER_TASK requires task_details")
        
        return errors


def generate_content_id() -> str:
    """Generate a unique content ID."""
    return f"CONTENT-{secrets.token_hex(4).upper()}"


@dataclass
class ContentEntry:
    """A processed content entry in the store."""
    id: str
    url: str
    title: str
    summary: str
    categories: list[str]
    relevance_score: float  # 0.0 to 1.0
    action_items: list[ActionItem]
    status: ContentStatus
    ingested_at: str
    source_hash: str
    raw_content: Optional[str] = None  # Full text, optional
    deep_analysis: Optional[DeepAnalysisResult] = None  # Deep analysis result
    
    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "categories": self.categories,
            "relevance_score": self.relevance_score,
            "action_items": [a.to_dict() for a in self.action_items],
            "status": self.status.value,
            "ingested_at": self.ingested_at,
            "source_hash": self.source_hash,
            "raw_content": self.raw_content,
        }
        
        if self.deep_analysis:
            result["deep_analysis"] = self.deep_analysis.to_dict()
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContentEntry":
        return cls(
            id=data["id"],
            url=data["url"],
            title=data["title"],
            summary=data["summary"],
            categories=data["categories"],
            relevance_score=data["relevance_score"],
            action_items=[ActionItem.from_dict(a) for a in data.get("action_items", [])],
            status=ContentStatus(data["status"]),
            ingested_at=data["ingested_at"],
            source_hash=data["source_hash"],
            raw_content=data.get("raw_content"),
            deep_analysis=DeepAnalysisResult.from_dict(data["deep_analysis"]) if data.get("deep_analysis") else None,
        )


@dataclass
class QueueRecord:
    """A record in the ingestion queue (from iOS/inbox file)."""
    url: str
    tags: list[str] = field(default_factory=list)
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed: bool = False
    
    @classmethod
    def parse_line(cls, line: str) -> Optional["QueueRecord"]:
        """Parse a queue line: 'url | tag1,tag2' or just 'url'."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        
        if "|" in line:
            url_part, tags_part = line.split("|", 1)
            url = url_part.strip()
            tags = [t.strip() for t in tags_part.split(",") if t.strip()]
        else:
            url = line
            tags = []
        
        if not url.startswith(("http://", "https://")):
            return None
            
        return cls(url=url, tags=tags)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

