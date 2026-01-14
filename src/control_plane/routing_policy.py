"""
RoutingPolicy for DTL v2.1.0

Deterministic routing of content to destinations based on JSON policy rules.
Supports: LIBRARY_ONLY, PLANNER_TASK, MONITORING, KNOWLEDGE_UPDATE, NOTEBOOKLM_DATAMART

Key design:
- All routing decisions are deterministic (no LLM in routing logic)
- Fail-closed: unknown or low-confidence content → LIBRARY_ONLY
- Auto-topic creation gated by strict thresholds
- All decisions logged to RunLedger for auditability
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any


class RouteDestination(Enum):
    """Closed-set routing destinations."""
    LIBRARY_ONLY = "LIBRARY_ONLY"
    PLANNER_TASK = "PLANNER_TASK"
    MONITORING = "MONITORING"
    KNOWLEDGE_UPDATE = "KNOWLEDGE_UPDATE"
    NOTEBOOKLM_DATAMART = "NOTEBOOKLM_DATAMART"


class SystemAction(Enum):
    """
    Closed-set system actions for routing decisions.
    
    Note: SYNC is intentionally excluded - it is an infrastructure
    operation, not a routing decision. Sync is triggered by CLI only.
    """
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
class RoutingDecision:
    """Result of routing policy evaluation."""
    content_id: str
    route_destination: RouteDestination
    system_actions: list[SystemAction]
    policy_name: str
    policy_version: str
    confidence_score: float
    uncertainty_flags: list[UncertaintyFlag] = field(default_factory=list)
    topic_id: Optional[str] = None
    auto_created_topic: bool = False
    decision_ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision_hash: str = ""
    
    def __post_init__(self):
        if not self.decision_hash:
            self.decision_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute deterministic hash of the decision."""
        payload = (
            f"{self.content_id}:"
            f"{self.route_destination.value}:"
            f"{','.join(a.value for a in sorted(self.system_actions, key=lambda x: x.value))}:"
            f"{self.policy_name}:{self.policy_version}:"
            f"{self.topic_id or ''}"
        )
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
    
    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "route_destination": self.route_destination.value,
            "system_actions": [a.value for a in self.system_actions],
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "confidence_score": self.confidence_score,
            "uncertainty_flags": [f.value for f in self.uncertainty_flags],
            "topic_id": self.topic_id,
            "auto_created_topic": self.auto_created_topic,
            "decision_ts": self.decision_ts,
            "decision_hash": self.decision_hash,
        }


# Default policy configuration
DEFAULT_POLICY_CONFIG = {
    "version": "1.0.0",
    "fail_closed_default": "LIBRARY_ONLY",
    
    # Auto-topic creation gate (strict)
    "auto_topic_gate": {
        "confidence_gte": 0.85,
        "novelty_score_gte": 4,
        "categories_allowlist": [
            "agents", "llm", "architecture", "security", 
            "trading", "langgraph", "rag"
        ]
    },
    
    # Deep analysis gate
    "deep_analysis_gate": {
        "relevance_score_gte": 0.65,
        "content_length_gte": 500,
        "categories_any": [
            "agents", "llm", "security", "trading", 
            "architecture", "research"
        ],
        "or_action_items_gte": 1,
        "or_manual_tag": "deep"
    },
    
    # Route-specific policies (evaluated in order)
    "policies": [
        {
            "name": "datamart_high_confidence",
            "priority": 1,
            "match": {
                "relevance_score_gte": 0.80,
                "confidence_score_gte": 0.75,
                "categories_any": ["agents", "llm", "architecture"],
                "topic_match_exists": True
            },
            "route": "NOTEBOOKLM_DATAMART",
            "actions": ["STORE", "ANALYZE", "BUNDLE"]
        },
        {
            "name": "datamart_auto_topic",
            "priority": 2,
            "match": {
                "relevance_score_gte": 0.85,
                "confidence_score_gte": 0.85,
                "novelty_score_gte": 4,
                "categories_any": ["agents", "llm", "architecture", "security", "trading", "langgraph", "rag"],
                "topic_match_exists": False
            },
            "route": "NOTEBOOKLM_DATAMART",
            "actions": ["STORE", "ANALYZE", "BUNDLE", "NOTIFY"],
            "auto_create_topic": True
        },
        {
            "name": "planner_actionable",
            "priority": 3,
            "match": {
                "action_items_count_gte": 2,
                "relevance_score_gte": 0.60,
                "highest_priority_lte": 2
            },
            "route": "PLANNER_TASK",
            "actions": ["STORE", "ANALYZE"],
            "max_daily": 10
        },
        {
            "name": "monitoring_trading",
            "priority": 4,
            "match": {
                "categories_any": ["trading"],
                "relevance_score_gte": 0.50,
                "has_temporal_component": True
            },
            "route": "MONITORING",
            "actions": ["STORE"],
            "monitoring_interval_hours": 24
        },
        {
            "name": "knowledge_update",
            "priority": 5,
            "match": {
                "relevance_score_gte": 0.85,
                "confidence_score_gte": 0.80,
                "categories_any": ["agents", "architecture", "security"]
            },
            "route": "KNOWLEDGE_UPDATE",
            "actions": ["STORE", "ANALYZE"]
        },
        {
            "name": "default_library",
            "priority": 99,
            "match": {},
            "route": "LIBRARY_ONLY",
            "actions": ["STORE"]
        }
    ]
}


class RoutingPolicy:
    """
    Deterministic routing policy evaluator.
    
    Evaluates content against JSON policy rules and returns
    a RoutingDecision with destination and actions.
    """
    
    CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "routing_policy.json"
    REGISTRY_PATH = Path(__file__).parent.parent.parent / "config" / "datamart_registry.json"
    
    def __init__(
        self, 
        config: Optional[dict] = None,
        registry: Optional[dict] = None,
    ):
        self.config = config or self._load_config()
        self.registry = registry or self._load_registry()
        self.version = self.config.get("version", "1.0.0")
        # Planner cap tracking - keyed by UTC day for determinism
        self._planner_counts_by_day: dict[str, int] = {}
        # New Topic cap tracking - keyed by UTC day
        self._new_topics_by_day: dict[str, int] = {}
        self.MAX_NEW_TOPICS_DAILY = 2
    
    def _load_config(self) -> dict:
        """Load routing policy from config file or use defaults."""
        if self.CONFIG_PATH.exists():
            with open(self.CONFIG_PATH) as f:
                return json.load(f)
        return DEFAULT_POLICY_CONFIG.copy()
    
    def _load_registry(self) -> dict:
        """Load datamart registry."""
        if self.REGISTRY_PATH.exists():
            with open(self.REGISTRY_PATH) as f:
                return json.load(f)
        return {"topics": {}}
    
    def evaluate(
        self,
        content_id: str,
        relevance_score: float,
        categories: list[str],
        action_items: list[dict],
        confidence_score: float = 0.5,
        novelty_score: int = 0,
        content_length: int = 0,
        manual_tags: list[str] = None,
        has_temporal_component: bool = False,
    ) -> RoutingDecision:
        """
        Evaluate content against routing policies.
        
        Args:
            content_id: Content entry ID
            relevance_score: 0.0-1.0 relevance to codebase
            categories: List of category IDs
            action_items: List of action item dicts
            confidence_score: 0.0-1.0 analysis confidence
            novelty_score: 0-10 novelty rating
            content_length: Character count of content
            manual_tags: User-provided tags
            has_temporal_component: Content is time-sensitive
        
        Returns:
            RoutingDecision with destination and actions
        """
        manual_tags = manual_tags or []
        
        # UTC day key for deterministic planner cap
        utc_day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Build context for matching
        ctx = {
            "relevance_score": relevance_score,
            "categories": categories,
            "action_items_count": len(action_items),
            "highest_priority": min((a.get("priority", 5) for a in action_items), default=5),
            "confidence_score": confidence_score,
            "novelty_score": novelty_score,
            "content_length": content_length,
            "manual_tags": manual_tags,
            "has_temporal_component": has_temporal_component,
            "topic_match": self._find_topic_match(categories),
        }
        
        # Fail-closed: low confidence
        if confidence_score < 0.6:
            return self._fail_closed(
                content_id=content_id,
                confidence_score=confidence_score,
                reason=UncertaintyFlag.LOW_EVIDENCE
            )
        
        # Evaluate policies in priority order
        policies = sorted(
            self.config.get("policies", []),
            key=lambda p: p.get("priority", 99)
        )
        
        for policy in policies:
            if self._matches(policy.get("match", {}), ctx):
                return self._build_decision(content_id, policy, ctx)
        
        # Fallback to fail-closed default
        return self._fail_closed(content_id, confidence_score)
    
    def _matches(self, match_rules: dict, ctx: dict) -> bool:
        """Check if context matches all rules in a policy."""
        if not match_rules:
            return True  # Empty match = catch-all
        
        for key, value in match_rules.items():
            if key.endswith("_gte"):
                field = key[:-4]
                if ctx.get(field, 0) < value:
                    return False
            elif key.endswith("_lte"):
                field = key[:-4]
                if ctx.get(field, float("inf")) > value:
                    return False
            elif key == "categories_any":
                if not any(c in value for c in ctx.get("categories", [])):
                    return False
            elif key == "topic_match_exists":
                has_match = ctx.get("topic_match") is not None
                if has_match != value:
                    return False
            elif key == "has_temporal_component":
                if ctx.get("has_temporal_component") != value:
                    return False
            elif key == "or_manual_tag":
                # OR condition: passes if tag present
                if value in ctx.get("manual_tags", []):
                    return True
            elif key == "or_action_items_gte":
                # OR condition: passes if action items meet threshold
                if ctx.get("action_items_count", 0) >= value:
                    return True
        
        return True
    
    def _find_topic_match(self, categories: list[str]) -> Optional[str]:
        """Find matching topic ID from registry based on categories."""
        topics = self.registry.get("topics", {})
        
        for topic_id, topic_config in topics.items():
            topic_categories = topic_config.get("categories", [])
            if any(c in topic_categories for c in categories):
                if topic_config.get("status", "active") == "active":
                    return topic_id
        
        return None
    
    def _build_decision(
        self, 
        content_id: str, 
        policy: dict, 
        ctx: dict
    ) -> RoutingDecision:
        """Build RoutingDecision from matched policy."""
        route = RouteDestination(policy["route"])
        actions = [SystemAction(a) for a in policy.get("actions", ["STORE"])]
        
        # Check daily limit for PLANNER_TASK (deterministic by UTC day)
        if route == RouteDestination.PLANNER_TASK:
            utc_day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            max_per_utc_day = policy.get("max_per_utc_day", 10)
            current_count = self._planner_counts_by_day.get(utc_day_key, 0)
            
            if current_count >= max_per_utc_day:
                return self._fail_closed(
                    content_id=content_id,
                    confidence_score=ctx["confidence_score"],
                    reason=UncertaintyFlag.AMBIGUOUS_CONTENT,
                    add_notify=True
                )
            self._planner_counts_by_day[utc_day_key] = current_count + 1
        
        # Handle auto-topic creation
        topic_id = ctx.get("topic_match")
        auto_created = False
        
        if route == RouteDestination.NOTEBOOKLM_DATAMART:
            if policy.get("auto_create_topic") and not topic_id:
                # Verify auto-topic gate
                gate = self.config.get("auto_topic_gate", {})
                if self._passes_auto_topic_gate(ctx, gate):
                    # Check Max New Topics Cap
                    utc_day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    current_new_topics = self._new_topics_by_day.get(utc_day_key, 0)
                    
                    if current_new_topics >= self.MAX_NEW_TOPICS_DAILY:
                        # Cap hit -> Fall back to LIBRARY_ONLY + NOTIFY
                        return self._fail_closed(
                            content_id=content_id,
                            confidence_score=ctx["confidence_score"],
                            reason=UncertaintyFlag.TOPIC_MISMATCH, # Or new flag? Reuse mismatch.
                            add_notify=True
                        )
                    
                    # Update cap counter
                    self._new_topics_by_day[utc_day_key] = current_new_topics + 1
                    
                    topic_id = self._generate_topic_id(ctx["categories"], ctx.get("url", ""))
                    auto_created = True
                    if SystemAction.NOTIFY not in actions:
                        actions.append(SystemAction.NOTIFY)
                else:
                    # Fall back to LIBRARY_ONLY + NOTIFY
                    return self._fail_closed(
                        content_id=content_id,
                        confidence_score=ctx["confidence_score"],
                        reason=UncertaintyFlag.TOPIC_MISMATCH,
                        add_notify=True
                    )
            elif not topic_id:
                # No topic match and no auto-create
                return self._fail_closed(
                    content_id=content_id,
                    confidence_score=ctx["confidence_score"],
                    reason=UncertaintyFlag.TOPIC_MISMATCH,
                    add_notify=True
                )
        
        return RoutingDecision(
            content_id=content_id,
            route_destination=route,
            system_actions=actions,
            policy_name=policy["name"],
            policy_version=self.version,
            confidence_score=ctx["confidence_score"],
            topic_id=topic_id,
            auto_created_topic=auto_created,
        )
    
    def _passes_auto_topic_gate(self, ctx: dict, gate: dict) -> bool:
        """Check if context passes auto-topic creation gate."""
        if ctx.get("confidence_score", 0) < gate.get("confidence_gte", 0.85):
            return False
        if ctx.get("novelty_score", 0) < gate.get("novelty_score_gte", 4):
            return False
        
        allowlist = gate.get("categories_allowlist", [])
        if allowlist:
            if not any(c in allowlist for c in ctx.get("categories", [])):
                return False
        
        return True
    
    def _generate_topic_id(
        self, 
        categories: list[str],
        url: str = "",
        top_keywords: list[str] = None,
    ) -> str:
        """
        Generate deterministic topic ID from stable features.
        
        topic_id = {slug}-{short_hash}
        slug = normalized primary category
        short_hash = hash(domain + sorted_categories + sorted_keywords)[:6]
        
        This ensures:
        - Same inputs → same topic_id (deterministic)
        - No near-duplicates from name variants
        - Reproducible across runs
        """
        top_keywords = top_keywords or []
        
        # Extract slug from first allowlisted category
        allowlist = self.config.get("auto_topic_gate", {}).get("categories_allowlist", [])
        slug = "general"
        for cat in categories:
            if cat in allowlist:
                slug = cat.lower().replace("_", "-")
                break
        
        # Extract domain from URL for hash stability
        domain = ""
        if url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
            except Exception:
                pass
        
        # Build deterministic hash from stable features
        hash_input = "|".join([
            domain,
            ",".join(sorted(categories)),
            ",".join(sorted(top_keywords[:5])),  # Limit keywords
        ])
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:6]
        
        return f"{slug}-{short_hash}"
    
    def _fail_closed(
        self,
        content_id: str,
        confidence_score: float,
        reason: UncertaintyFlag = None,
        add_notify: bool = False,
    ) -> RoutingDecision:
        """Return fail-closed LIBRARY_ONLY decision."""
        actions = [SystemAction.STORE]
        if add_notify or confidence_score < 0.6:
            actions.append(SystemAction.NOTIFY)
        
        flags = []
        if reason:
            flags.append(reason)
        if confidence_score < 0.6:
            flags.append(UncertaintyFlag.LOW_EVIDENCE)
        
        return RoutingDecision(
            content_id=content_id,
            route_destination=RouteDestination.LIBRARY_ONLY,
            system_actions=actions,
            policy_name="fail_closed",
            policy_version=self.version,
            confidence_score=confidence_score,
            uncertainty_flags=flags,
        )
    
    def should_deep_analyze(
        self,
        relevance_score: float,
        categories: list[str],
        action_items_count: int,
        content_length: int,
        manual_tags: list[str] = None,
    ) -> bool:
        """
        Check if content should trigger deep analysis.
        
        Deterministic gate based on config rules.
        """
        manual_tags = manual_tags or []
        gate = self.config.get("deep_analysis_gate", {})
        
        # Must pass all hard requirements
        if relevance_score < gate.get("relevance_score_gte", 0.65):
            return False
        if content_length < gate.get("content_length_gte", 500):
            return False
        
        # Must pass at least one of the OR conditions
        or_conditions = []
        
        # Category match
        cat_any = gate.get("categories_any", [])
        if cat_any and any(c in cat_any for c in categories):
            or_conditions.append(True)
        
        # Action items threshold
        if action_items_count >= gate.get("or_action_items_gte", 1):
            or_conditions.append(True)
        
        # Manual tag
        if gate.get("or_manual_tag") in manual_tags:
            or_conditions.append(True)
        
        return any(or_conditions)


def save_default_config():
    """Save default routing policy config to file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "routing_policy.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        json.dump(DEFAULT_POLICY_CONFIG, f, indent=2)
    
    return config_path
