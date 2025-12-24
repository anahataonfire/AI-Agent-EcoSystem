"""
Plan Decomposition Validation (DTL-SKILL-PLANVAL v1).

Validates task decompositions before execution.
Integrated into thinker_node only.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set


class InvalidPlanError(Exception):
    """Raised when plan validation fails (DTL-PLAN-003)."""
    pass


@dataclass
class PlanStep:
    """A step in a task decomposition."""
    step_id: str
    description: str
    owner: str  # Agent responsible
    depends_on: List[str] = None  # Step IDs this depends on
    
    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []


@dataclass
class TaskPlan:
    """A validated task decomposition."""
    goal: str
    steps: List[PlanStep]
    
    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


# Valid agent owners
VALID_OWNERS = {"thinker", "sanitizer", "executor", "reporter"}


def validate_coverage(goal: str, steps: List[PlanStep]) -> bool:
    """
    Validate that steps cover the original goal.
    
    Simple heuristic: at least one step must exist.
    """
    if not steps:
        return False
    return True


def detect_circular_dependencies(steps: List[PlanStep]) -> Optional[str]:
    """
    Detect circular dependencies in plan.
    
    Returns:
        First circular dependency found, or None
    """
    step_map = {s.step_id: s for s in steps}
    
    def has_cycle(step_id: str, visited: Set[str], path: Set[str]) -> bool:
        if step_id in path:
            return True
        if step_id in visited:
            return False
        
        visited.add(step_id)
        path.add(step_id)
        
        step = step_map.get(step_id)
        if step and step.depends_on:
            for dep in step.depends_on:
                if has_cycle(dep, visited, path):
                    return True
        
        path.remove(step_id)
        return False
    
    visited: Set[str] = set()
    for step in steps:
        if has_cycle(step.step_id, visited, set()):
            return step.step_id
    
    return None


def validate_owners(steps: List[PlanStep]) -> Optional[str]:
    """
    Validate all steps have executable owners.
    
    Returns:
        First invalid owner, or None
    """
    for step in steps:
        if step.owner not in VALID_OWNERS:
            return step.owner
    return None


def validate_plan(goal: str, steps: List[PlanStep]) -> TaskPlan:
    """
    Validate a task decomposition.
    
    Checks:
    - Coverage of original goal
    - No circular steps
    - Each step has executable owner
    
    Raises:
        InvalidPlanError: With DTL-PLAN-003 if invalid
    """
    # Check coverage
    if not validate_coverage(goal, steps):
        raise InvalidPlanError(
            "# Execution Aborted\n"
            "Code: DTL-PLAN-003\n"
            "Reason: Plan has no steps - goal not covered"
        )
    
    # Check circular dependencies
    circular = detect_circular_dependencies(steps)
    if circular:
        raise InvalidPlanError(
            f"# Execution Aborted\n"
            f"Code: DTL-PLAN-003\n"
            f"Reason: Circular dependency detected at step: {circular}"
        )
    
    # Check owners
    invalid_owner = validate_owners(steps)
    if invalid_owner:
        raise InvalidPlanError(
            f"# Execution Aborted\n"
            f"Code: DTL-PLAN-003\n"
            f"Reason: Invalid step owner: {invalid_owner}"
        )
    
    return TaskPlan(goal=goal, steps=steps)


def build_execution_order(plan: TaskPlan) -> List[str]:
    """
    Build topological execution order for plan steps.
    
    Returns:
        List of step IDs in execution order
    """
    step_map = {s.step_id: s for s in plan.steps}
    in_degree = {s.step_id: len(s.depends_on) for s in plan.steps}
    
    # Find steps with no dependencies
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    order = []
    
    while queue:
        current = queue.pop(0)
        order.append(current)
        
        # Reduce in-degree for dependents
        for step in plan.steps:
            if current in step.depends_on:
                in_degree[step.step_id] -= 1
                if in_degree[step.step_id] == 0:
                    queue.append(step.step_id)
    
    return order
