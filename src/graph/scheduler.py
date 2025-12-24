"""
Deterministic Multi-Agent Turn Scheduler (Prompt AD).

Replaces implicit LLM turn-taking with a deterministic scheduler
to prevent emergent loops and agent dominance.
"""

from typing import Dict, List, Optional, Tuple


class TurnLimitExceededError(Exception):
    """Raised when an agent exceeds its turn limit."""
    pass


class SelfInvocationError(Exception):
    """Raised when an agent attempts to invoke itself."""
    pass


# ============================================================================
# SCHEDULER CONFIGURATION
# ============================================================================

# Maximum turns per agent in a single run
MAX_AGENT_TURNS = 2

# Fixed agent execution order
AGENT_ORDER = ["thinker", "sanitizer", "executor", "reporter"]


class TurnScheduler:
    """
    Deterministic turn scheduler for multi-agent pipeline.
    
    Enforces:
    - Fixed agent order
    - Maximum turns per agent
    - No self-invocation
    """
    
    def __init__(self, max_turns: int = MAX_AGENT_TURNS):
        self.max_turns = max_turns
        self.turn_counts: Dict[str, int] = {agent: 0 for agent in AGENT_ORDER}
        self.current_agent: Optional[str] = None
        self.execution_history: List[str] = []
    
    def get_next_agent(self) -> Optional[str]:
        """
        Get the next agent in the execution order.
        
        Returns:
            Agent name, or None if all agents exhausted
        """
        for agent in AGENT_ORDER:
            if self.turn_counts[agent] < self.max_turns:
                return agent
        return None
    
    def start_turn(self, agent_name: str) -> None:
        """
        Record that an agent is starting its turn.
        
        Args:
            agent_name: Name of the agent
            
        Raises:
            TurnLimitExceededError: If agent has exceeded turn limit
            SelfInvocationError: If agent is trying to invoke itself
        """
        if agent_name not in AGENT_ORDER:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        # Check for self-invocation
        if self.current_agent == agent_name:
            raise SelfInvocationError(
                f"Agent {agent_name} attempted self-invocation"
            )
        
        # Check turn limit
        if self.turn_counts[agent_name] >= self.max_turns:
            raise TurnLimitExceededError(
                f"Agent turn limit exceeded: {agent_name} has used {self.turn_counts[agent_name]}/{self.max_turns} turns"
            )
        
        self.current_agent = agent_name
        self.turn_counts[agent_name] += 1
        self.execution_history.append(agent_name)
    
    def end_turn(self) -> None:
        """Record that the current agent has finished its turn."""
        self.current_agent = None
    
    def get_turn_count(self, agent_name: str) -> int:
        """Get the number of turns an agent has used."""
        return self.turn_counts.get(agent_name, 0)
    
    def get_remaining_turns(self, agent_name: str) -> int:
        """Get the number of turns an agent has remaining."""
        return self.max_turns - self.get_turn_count(agent_name)
    
    def is_agent_exhausted(self, agent_name: str) -> bool:
        """Check if an agent has exhausted its turns."""
        return self.get_turn_count(agent_name) >= self.max_turns
    
    def is_pipeline_exhausted(self) -> bool:
        """Check if all agents have exhausted their turns."""
        return all(
            self.is_agent_exhausted(agent)
            for agent in AGENT_ORDER
        )
    
    def get_execution_order(self) -> List[str]:
        """Get the fixed agent execution order."""
        return AGENT_ORDER.copy()
    
    def get_execution_history(self) -> List[str]:
        """Get the history of agent executions."""
        return self.execution_history.copy()
    
    def reset(self) -> None:
        """Reset the scheduler for a new run."""
        self.turn_counts = {agent: 0 for agent in AGENT_ORDER}
        self.current_agent = None
        self.execution_history = []


def validate_no_starvation(scheduler: TurnScheduler) -> bool:
    """
    Validate that no agent was starved (never got to execute).
    
    Returns:
        True if all agents got at least one turn
    """
    return all(
        scheduler.get_turn_count(agent) > 0
        for agent in AGENT_ORDER
    )


def check_turn_allowed(agent_name: str, scheduler: TurnScheduler) -> Tuple[bool, str]:
    """
    Check if an agent is allowed to take a turn.
    
    Returns:
        Tuple of (is_allowed, reason)
    """
    if agent_name not in AGENT_ORDER:
        return (False, f"Unknown agent: {agent_name}")
    
    if scheduler.current_agent == agent_name:
        return (False, "Self-invocation not allowed")
    
    if scheduler.is_agent_exhausted(agent_name):
        return (False, f"Turn limit exceeded: {scheduler.max_turns}")
    
    return (True, "")
