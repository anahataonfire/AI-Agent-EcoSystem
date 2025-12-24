"""
Self-Improvement Loop (DTL-SKILL-IMPROVE v1).

Closed-loop self-improvement using skill scores,
failure attribution, and eval results.

No architecture mutation. Deterministic changes only.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.core.skill_scoring import SkillScore
from src.core.failure_attribution import FailureAttribution
from src.core.evals import EvalResult


@dataclass
class ImprovementRecommendation:
    """A deterministic improvement recommendation."""
    recommendation_type: str
    target: str  # Skill name or system component
    action: str
    priority_adjustment: Optional[float] = None
    retry_tuning: Optional[dict] = None


class SelfImproveEngine:
    """
    Closed-loop self-improvement engine.
    
    Inputs:
    - Skill scores
    - Failure attributions
    - Eval results
    
    Outputs:
    - Priority adjustments
    - Retry tuning
    
    No architecture mutation. Deterministic changes only.
    """
    
    def __init__(self):
        self.recommendations: List[ImprovementRecommendation] = []
    
    def analyze_skill_performance(
        self,
        scores: Dict[str, SkillScore],
    ) -> List[ImprovementRecommendation]:
        """
        Analyze skill performance and recommend adjustments.
        """
        recs = []
        
        for skill_name, score in scores.items():
            # Deprioritize skills with low success rate
            if score.success_rate < 0.5 and score.total_runs >= 3:
                recs.append(ImprovementRecommendation(
                    recommendation_type="priority_adjustment",
                    target=skill_name,
                    action="deprioritize",
                    priority_adjustment=-0.2,
                ))
            
            # Boost skills with high success rate
            if score.success_rate > 0.9 and score.total_runs >= 5:
                recs.append(ImprovementRecommendation(
                    recommendation_type="priority_adjustment",
                    target=skill_name,
                    action="promote",
                    priority_adjustment=0.1,
                ))
            
            # Flag skills with high abort rate
            if score.abort_rate > 0.3 and score.total_runs >= 3:
                recs.append(ImprovementRecommendation(
                    recommendation_type="attention_required",
                    target=skill_name,
                    action="review_abort_causes",
                ))
        
        return recs
    
    def analyze_failures(
        self,
        attributions: List[FailureAttribution],
    ) -> List[ImprovementRecommendation]:
        """
        Analyze failure patterns and recommend retry tuning.
        """
        recs = []
        
        # Count by root cause
        cause_counts: Dict[str, int] = {}
        for attr in attributions:
            cause_counts[attr.root_cause] = cause_counts.get(attr.root_cause, 0) + 1
        
        # Tune retries based on patterns
        if cause_counts.get("tool", 0) > 5:
            recs.append(ImprovementRecommendation(
                recommendation_type="retry_tuning",
                target="tool_failures",
                action="increase_backoff",
                retry_tuning={"base_delay_ms": 1000},
            ))
        
        if cause_counts.get("data", 0) > 3:
            recs.append(ImprovementRecommendation(
                recommendation_type="attention_required",
                target="data_validation",
                action="review_input_sources",
            ))
        
        return recs
    
    def analyze_evals(
        self,
        results: List[EvalResult],
    ) -> List[ImprovementRecommendation]:
        """
        Analyze eval results and recommend improvements.
        """
        recs = []
        
        failure_reasons = []
        for result in results:
            if not result.passed:
                failure_reasons.extend(result.reasons)
        
        # Check for grounding issues
        if any("citation" in r.lower() for r in failure_reasons):
            recs.append(ImprovementRecommendation(
                recommendation_type="attention_required",
                target="grounding",
                action="improve_citation_generation",
            ))
        
        return recs
    
    def generate_recommendations(
        self,
        scores: Dict[str, SkillScore],
        attributions: List[FailureAttribution],
        eval_results: List[EvalResult],
    ) -> List[ImprovementRecommendation]:
        """
        Generate all improvement recommendations.
        
        Deterministic based on inputs.
        """
        recs = []
        recs.extend(self.analyze_skill_performance(scores))
        recs.extend(self.analyze_failures(attributions))
        recs.extend(self.analyze_evals(eval_results))
        
        self.recommendations = recs
        return recs
    
    def get_priority_adjustments(self) -> Dict[str, float]:
        """Get recommended priority adjustments."""
        adjustments = {}
        for rec in self.recommendations:
            if rec.recommendation_type == "priority_adjustment":
                adjustments[rec.target] = rec.priority_adjustment or 0
        return adjustments
    
    def get_retry_tuning(self) -> Dict[str, dict]:
        """Get recommended retry tuning."""
        tuning = {}
        for rec in self.recommendations:
            if rec.recommendation_type == "retry_tuning":
                tuning[rec.target] = rec.retry_tuning or {}
        return tuning
