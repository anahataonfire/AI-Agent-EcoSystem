"""
Skill Performance Scoring (DTL-SKILL-SCORE v1).

Performance scoring for skills, not runs.
Updated only after successful reporter_node.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import json


@dataclass
class SkillScore:
    """Performance score for a skill."""
    skill_name: str
    total_runs: int = 0
    successful_runs: int = 0
    aborted_runs: int = 0
    total_steps: int = 0
    total_cost_units: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs
    
    @property
    def abort_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.aborted_runs / self.total_runs
    
    @property
    def avg_steps(self) -> float:
        if self.successful_runs == 0:
            return 0.0
        return self.total_steps / self.successful_runs
    
    @property
    def avg_cost_units(self) -> float:
        if self.successful_runs == 0:
            return 0.0
        return self.total_cost_units / self.successful_runs


# Decay factor per run (scores decay slowly)
SCORE_DECAY_FACTOR = 0.95


class SkillScoreStore:
    """Persistent store for skill scores."""
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            project_root = Path(__file__).parent.parent.parent
            storage_path = str(project_root / "data" / "skill_scores.json")
        
        self.storage_path = Path(storage_path)
        self._scores: Dict[str, SkillScore] = {}
        self._load()
    
    def _load(self) -> None:
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for name, values in data.items():
                        self._scores[name] = SkillScore(
                            skill_name=name,
                            **values
                        )
        except (json.JSONDecodeError, FileNotFoundError):
            self._scores = {}
    
    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for name, score in self._scores.items():
            data[name] = {
                "total_runs": score.total_runs,
                "successful_runs": score.successful_runs,
                "aborted_runs": score.aborted_runs,
                "total_steps": score.total_steps,
                "total_cost_units": score.total_cost_units,
            }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_score(self, skill_name: str) -> SkillScore:
        """Get score for a skill, creating if needed."""
        if skill_name not in self._scores:
            self._scores[skill_name] = SkillScore(skill_name=skill_name)
        return self._scores[skill_name]
    
    def record_success(
        self,
        skill_name: str,
        steps: int,
        cost_units: int,
    ) -> SkillScore:
        """Record a successful run (only after reporter_node)."""
        score = self.get_score(skill_name)
        score.total_runs += 1
        score.successful_runs += 1
        score.total_steps += steps
        score.total_cost_units += cost_units
        self._save()
        return score
    
    def record_abort(self, skill_name: str) -> SkillScore:
        """Record an aborted run."""
        score = self.get_score(skill_name)
        score.total_runs += 1
        score.aborted_runs += 1
        self._save()
        return score
    
    def apply_decay(self) -> None:
        """Apply decay to all scores (called periodically)."""
        for score in self._scores.values():
            # Decay counts slightly to favor recent performance
            score.successful_runs = int(score.successful_runs * SCORE_DECAY_FACTOR)
            score.aborted_runs = int(score.aborted_runs * SCORE_DECAY_FACTOR)
        self._save()
    
    def get_priority_order(self) -> List[str]:
        """Get skills ordered by success rate (highest first)."""
        return sorted(
            self._scores.keys(),
            key=lambda x: self._scores[x].success_rate,
            reverse=True
        )
    
    def get_retry_fallback_order(self) -> List[str]:
        """Get skills ordered for retry fallback (lowest abort rate first)."""
        return sorted(
            self._scores.keys(),
            key=lambda x: self._scores[x].abort_rate
        )
