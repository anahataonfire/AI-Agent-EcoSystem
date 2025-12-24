"""
Plan Validation Tests (DTL-SKILL-PLANVAL v1).
"""

import pytest


class TestGoalCoverage:
    """Tests for goal coverage validation."""

    def test_empty_plan_fails(self):
        """Plan with no steps must fail."""
        from src.core.plan_validation import validate_plan, InvalidPlanError
        
        with pytest.raises(InvalidPlanError) as exc_info:
            validate_plan("Do something", [])
        
        assert "DTL-PLAN-003" in str(exc_info.value)


class TestCircularDependencies:
    """Tests for circular dependency detection."""

    def test_circular_dependency_detected(self):
        """Circular dependencies must be detected."""
        from src.core.plan_validation import validate_plan, PlanStep, InvalidPlanError
        
        steps = [
            PlanStep("s1", "Step 1", "executor", depends_on=["s2"]),
            PlanStep("s2", "Step 2", "executor", depends_on=["s1"]),
        ]
        
        with pytest.raises(InvalidPlanError) as exc_info:
            validate_plan("Goal", steps)
        
        assert "circular" in str(exc_info.value).lower()

    def test_no_circular_passes(self):
        """Linear dependencies should pass."""
        from src.core.plan_validation import validate_plan, PlanStep
        
        steps = [
            PlanStep("s1", "Step 1", "thinker", depends_on=[]),
            PlanStep("s2", "Step 2", "executor", depends_on=["s1"]),
            PlanStep("s3", "Step 3", "reporter", depends_on=["s2"]),
        ]
        
        plan = validate_plan("Goal", steps)
        assert len(plan.steps) == 3


class TestOwnerValidation:
    """Tests for owner validation."""

    def test_invalid_owner_fails(self):
        """Invalid owner must be rejected."""
        from src.core.plan_validation import validate_plan, PlanStep, InvalidPlanError
        
        steps = [
            PlanStep("s1", "Step 1", "invalid_agent", depends_on=[]),
        ]
        
        with pytest.raises(InvalidPlanError) as exc_info:
            validate_plan("Goal", steps)
        
        assert "invalid_agent" in str(exc_info.value).lower()

    def test_valid_owners_pass(self):
        """Valid owners should pass."""
        from src.core.plan_validation import validate_plan, PlanStep
        
        steps = [
            PlanStep("s1", "Think", "thinker"),
            PlanStep("s2", "Execute", "executor"),
            PlanStep("s3", "Report", "reporter"),
        ]
        
        plan = validate_plan("Goal", steps)
        assert len(plan.steps) == 3


class TestExecutionOrder:
    """Tests for execution order building."""

    def test_topological_order(self):
        """Execution order should respect dependencies."""
        from src.core.plan_validation import validate_plan, PlanStep, build_execution_order
        
        steps = [
            PlanStep("s3", "Last", "reporter", depends_on=["s2"]),
            PlanStep("s1", "First", "thinker", depends_on=[]),
            PlanStep("s2", "Second", "executor", depends_on=["s1"]),
        ]
        
        plan = validate_plan("Goal", steps)
        order = build_execution_order(plan)
        
        assert order.index("s1") < order.index("s2")
        assert order.index("s2") < order.index("s3")
