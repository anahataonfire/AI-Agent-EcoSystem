"""
State Memory with Decay (DTL-SKILL-MEMORY v1).

Short-term state memory for retry avoidance and skill routing.
NEVER used for content generation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import json


@dataclass
class MemoryEntry:
    """A decaying memory entry."""
    query_hash: str
    skill_used: str
    outcome: str  # "success" or "failure"
    failure_reason: Optional[str] = None
    remaining_runs: int = 5  # Decays after 5 runs
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


# Default decay threshold
DEFAULT_DECAY_RUNS = 5


class StateMemory:
    """
    Short-term state memory with decay.
    
    Used ONLY for:
    - Retry avoidance
    - Skill routing
    
    NEVER used for content generation.
    """
    
    def __init__(self, storage_path: Optional[str] = None, decay_runs: int = DEFAULT_DECAY_RUNS):
        if storage_path is None:
            project_root = Path(__file__).parent.parent.parent
            storage_path = str(project_root / "data" / "state_memory.json")
        
        self.storage_path = Path(storage_path)
        self.decay_runs = decay_runs
        self._memory: Dict[str, MemoryEntry] = {}
        self._load()
    
    def _load(self) -> None:
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for key, values in data.items():
                        self._memory[key] = MemoryEntry(**values)
        except (json.JSONDecodeError, FileNotFoundError):
            self._memory = {}
    
    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, entry in self._memory.items():
            data[key] = {
                "query_hash": entry.query_hash,
                "skill_used": entry.skill_used,
                "outcome": entry.outcome,
                "failure_reason": entry.failure_reason,
                "remaining_runs": entry.remaining_runs,
                "created_at": entry.created_at,
            }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def remember(
        self,
        query_hash: str,
        skill_used: str,
        outcome: str,
        failure_reason: Optional[str] = None,
    ) -> None:
        """Store a memory entry."""
        key = f"{query_hash}:{skill_used}"
        self._memory[key] = MemoryEntry(
            query_hash=query_hash,
            skill_used=skill_used,
            outcome=outcome,
            failure_reason=failure_reason,
            remaining_runs=self.decay_runs,
        )
        self._save()
    
    def recall(self, query_hash: str, skill_name: Optional[str] = None) -> List[MemoryEntry]:
        """
        Recall memories for a query.
        
        Args:
            query_hash: The query to recall for
            skill_name: Optional filter by skill
            
        Returns:
            List of matching memories
        """
        results = []
        for key, entry in self._memory.items():
            if entry.query_hash == query_hash:
                if skill_name is None or entry.skill_used == skill_name:
                    results.append(entry)
        return results
    
    def should_avoid_skill(self, query_hash: str, skill_name: str) -> bool:
        """
        Check if a skill should be avoided for this query.
        
        Returns:
            True if skill previously failed for this query
        """
        memories = self.recall(query_hash, skill_name)
        for mem in memories:
            if mem.outcome == "failure" and mem.remaining_runs > 0:
                return True
        return False
    
    def get_preferred_skills(self, query_hash: str, available_skills: List[str]) -> List[str]:
        """
        Get skills ordered by preference for this query.
        
        Skills that succeeded before are preferred.
        Skills that failed are deprioritized.
        """
        succeeded = set()
        failed = set()
        
        for key, entry in self._memory.items():
            if entry.query_hash == query_hash and entry.remaining_runs > 0:
                if entry.outcome == "success":
                    succeeded.add(entry.skill_used)
                else:
                    failed.add(entry.skill_used)
        
        # Order: succeeded first, then neutral, then failed
        preferred = []
        neutral = []
        deprioritized = []
        
        for skill in available_skills:
            if skill in succeeded:
                preferred.append(skill)
            elif skill in failed:
                deprioritized.append(skill)
            else:
                neutral.append(skill)
        
        return preferred + neutral + deprioritized
    
    def apply_decay(self) -> int:
        """
        Apply decay to all memories.
        
        Returns:
            Number of memories removed
        """
        to_remove = []
        
        for key, entry in self._memory.items():
            entry.remaining_runs -= 1
            if entry.remaining_runs <= 0:
                to_remove.append(key)
        
        for key in to_remove:
            del self._memory[key]
        
        self._save()
        return len(to_remove)
    
    def clear_query(self, query_hash: str) -> int:
        """Clear all memories for a query."""
        to_remove = [k for k, v in self._memory.items() if v.query_hash == query_hash]
        for key in to_remove:
            del self._memory[key]
        self._save()
        return len(to_remove)
