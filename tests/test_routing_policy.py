"""
Unit tests for RoutingPolicy module.

Tests deterministic routing, gating rules, auto-topic creation,
and fail-closed behavior.
"""

import pytest
from datetime import datetime, timezone

from src.control_plane.routing_policy import (
    RoutingPolicy,
    RouteDestination,
    SystemAction,
    UncertaintyFlag,
    RoutingDecision,
    DEFAULT_POLICY_CONFIG,
)


class TestRoutingPolicyBasics:
    """Basic routing policy functionality tests."""
    
    def test_default_policy_loads(self):
        """Policy initializes with default config."""
        policy = RoutingPolicy()
        assert policy.version == "1.0.0"
        assert len(policy.config.get("policies", [])) > 0
    
    def test_library_only_fallback(self):
        """Unknown content routes to LIBRARY_ONLY."""
        policy = RoutingPolicy()
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0001",
            relevance_score=0.3,
            categories=["uncategorized"],
            action_items=[],
            confidence_score=0.7,
        )
        
        assert decision.route_destination == RouteDestination.LIBRARY_ONLY
        assert decision.policy_name == "default_library"
    
    def test_low_confidence_forces_library_only(self):
        """Confidence < 0.6 forces LIBRARY_ONLY + NOTIFY."""
        policy = RoutingPolicy()
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0002",
            relevance_score=0.9,  # High relevance
            categories=["agents", "llm"],
            action_items=[{"type": "enhancement", "description": "Test", "priority": 1}],
            confidence_score=0.5,  # Below threshold
        )
        
        assert decision.route_destination == RouteDestination.LIBRARY_ONLY
        assert SystemAction.NOTIFY in decision.system_actions
        assert UncertaintyFlag.LOW_EVIDENCE in decision.uncertainty_flags


class TestDatamartRouting:
    """Tests for NOTEBOOKLM_DATAMART routing."""
    
    def test_datamart_with_topic_match(self):
        """High-relevance content with matching topic routes to datamart."""
        policy = RoutingPolicy(
            registry={
                "topics": {
                    "agentic-patterns": {
                        "categories": ["agents", "architecture"],
                        "status": "active"
                    }
                }
            }
        )
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0003",
            relevance_score=0.85,
            categories=["agents"],
            action_items=[],
            confidence_score=0.80,
        )
        
        assert decision.route_destination == RouteDestination.NOTEBOOKLM_DATAMART
        assert decision.topic_id == "agentic-patterns"
        assert not decision.auto_created_topic
    
    def test_auto_topic_creation_passes_gate(self):
        """Auto-topic created when gate passes (confidence≥0.85, novelty≥4)."""
        policy = RoutingPolicy()
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0004",
            relevance_score=0.90,
            categories=["agents"],
            action_items=[],
            confidence_score=0.88,
            novelty_score=5,
        )
        
        assert decision.route_destination == RouteDestination.NOTEBOOKLM_DATAMART
        assert decision.auto_created_topic is True
        assert decision.topic_id is not None
        assert "agents" in decision.topic_id
    
    def test_auto_topic_fails_low_novelty(self):
        """Auto-topic blocked when novelty < 4."""
        policy = RoutingPolicy()
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0005",
            relevance_score=0.90,
            categories=["agents"],
            action_items=[],
            confidence_score=0.88,
            novelty_score=2,  # Below threshold
        )
        
        # Should fall through to another route or LIBRARY_ONLY
        assert decision.auto_created_topic is False
    
    def test_archived_topic_not_matched(self):
        """Archived topics are not matched for routing."""
        policy = RoutingPolicy(
            registry={
                "topics": {
                    "old-topic": {
                        "categories": ["agents"],
                        "status": "archived"
                    }
                }
            }
        )
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0006",
            relevance_score=0.85,
            categories=["agents"],
            action_items=[],
            confidence_score=0.80,
        )
        
        # Should not match archived topic
        assert decision.topic_id != "old-topic"


class TestPlannerRouting:
    """Tests for PLANNER_TASK routing."""
    
    def test_planner_with_action_items(self):
        """Content with 2+ high-priority action items routes to planner."""
        policy = RoutingPolicy()
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0007",
            relevance_score=0.70,
            categories=["tooling"],
            action_items=[
                {"type": "enhancement", "description": "Add feature", "priority": 1},
                {"type": "enhancement", "description": "Fix bug", "priority": 2},
            ],
            confidence_score=0.80,
        )
        
        assert decision.route_destination == RouteDestination.PLANNER_TASK
    
    def test_planner_daily_limit(self):
        """Daily limit prevents planner overload."""
        policy = RoutingPolicy()
        policy._daily_planner_count = 10  # Already at limit
        
        decision = policy.evaluate(
            content_id="CONTENT-TEST0008",
            relevance_score=0.70,
            categories=["tooling"],
            action_items=[
                {"type": "enhancement", "description": "Add feature", "priority": 1},
                {"type": "enhancement", "description": "Fix bug", "priority": 2},
            ],
            confidence_score=0.80,
        )
        
        # Should fall back to LIBRARY_ONLY due to daily limit
        assert decision.route_destination == RouteDestination.LIBRARY_ONLY
        assert SystemAction.NOTIFY in decision.system_actions


class TestDeterminism:
    """Tests for routing determinism."""
    
    def test_same_input_same_decision_hash(self):
        """Same inputs produce same decision hash."""
        policy = RoutingPolicy()
        
        inputs = {
            "content_id": "CONTENT-DETER001",
            "relevance_score": 0.75,
            "categories": ["agents", "llm"],
            "action_items": [],
            "confidence_score": 0.8,
        }
        
        decision1 = policy.evaluate(**inputs)
        decision2 = policy.evaluate(**inputs)
        
        assert decision1.decision_hash == decision2.decision_hash
        assert decision1.route_destination == decision2.route_destination
    
    def test_decision_hash_deterministic(self):
        """Decision hash is deterministic based on content."""
        decision = RoutingDecision(
            content_id="CONTENT-HASH001",
            route_destination=RouteDestination.LIBRARY_ONLY,
            system_actions=[SystemAction.STORE],
            policy_name="test",
            policy_version="1.0.0",
            confidence_score=0.8,
        )
        
        # Hash should be consistent
        hash1 = decision.decision_hash
        hash2 = decision._compute_hash()
        assert hash1 == hash2


class TestDeepAnalysisGate:
    """Tests for should_deep_analyze() gating."""
    
    def test_deep_analysis_requires_relevance(self):
        """Deep analysis requires relevance >= 0.65."""
        policy = RoutingPolicy()
        
        assert not policy.should_deep_analyze(
            relevance_score=0.5,
            categories=["agents"],
            action_items_count=2,
            content_length=1000,
        )
    
    def test_deep_analysis_requires_content_length(self):
        """Deep analysis requires content length >= 500."""
        policy = RoutingPolicy()
        
        assert not policy.should_deep_analyze(
            relevance_score=0.8,
            categories=["agents"],
            action_items_count=0,
            content_length=100,
        )
    
    def test_deep_analysis_with_category_match(self):
        """Deep analysis triggers with matching category."""
        policy = RoutingPolicy()
        
        assert policy.should_deep_analyze(
            relevance_score=0.7,
            categories=["agents"],
            action_items_count=0,
            content_length=1000,
        )
    
    def test_deep_analysis_with_manual_tag(self):
        """Deep analysis triggers with 'deep' manual tag."""
        policy = RoutingPolicy()
        
        assert policy.should_deep_analyze(
            relevance_score=0.7,
            categories=["uncategorized"],
            action_items_count=0,
            content_length=1000,
            manual_tags=["deep"],
        )

def test_topic_id_determinism():
    """Verify that topic ID generation is deterministic and resilient to variants."""
    policy = RoutingPolicy()
    
    # 1. Same input -> Same ID
    id1 = policy._generate_topic_id("Agentic Systems", ["agents", "ai"], "google.com")
    id2 = policy._generate_topic_id("Agentic Systems", ["agents", "ai"], "google.com")
    assert id1 == id2
    
    # 2. Case insensitivity / Normalization
    id3 = policy._generate_topic_id("agentic systems", ["Agents", "AI"], "google.com")
    assert id1 == id3
    
    # 3. Slug extraction consistency
    # "Agentic Systems" -> "agentic-systems"
    assert id1.startswith("agentic-systems-")
    
    # 4. Different domain -> Different ID (hash component changes)
    id4 = policy._generate_topic_id("Agentic Systems", ["agents", "ai"], "openai.com")
    assert id1 != id4
    assert id4.startswith("agentic-systems-") # Slug same, hash diff
    
    # 5. Different categories -> Different ID
    id5 = policy._generate_topic_id("Agentic Systems", ["agents", "python"], "google.com")
    assert id1 != id5


