"""
Verification & Evals Pipeline (DTL-SKILL-EVAL v1).

Automated verification after report generation.
Reporter aborts if severity == "fail".
"""

from dataclasses import dataclass
from typing import List, Literal
import re


@dataclass
class EvalResult:
    """Evaluation result."""
    passed: bool
    reasons: List[str]
    severity: Literal["info", "warn", "fail"]


class EvalFailureError(Exception):
    """Raised when eval severity is 'fail'."""
    pass


# Minimum claim density (claims per 100 chars)
MIN_CLAIM_DENSITY = 0.5

# Citation pattern
CITATION_PATTERN = re.compile(r'\[EVID:([a-zA-Z0-9_]+)\]')


def eval_grounding(
    report: str,
    evidence_ids: List[str],
) -> EvalResult:
    """
    Evaluate grounding pass/fail.
    
    Checks that all citations reference valid evidence.
    """
    reasons = []
    
    citations = CITATION_PATTERN.findall(report)
    
    if not citations:
        return EvalResult(
            passed=False,
            reasons=["No citations found in report"],
            severity="fail",
        )
    
    invalid_citations = [c for c in citations if c not in evidence_ids]
    
    if invalid_citations:
        reasons.append(f"Invalid citations: {invalid_citations}")
        return EvalResult(
            passed=False,
            reasons=reasons,
            severity="fail",
        )
    
    return EvalResult(
        passed=True,
        reasons=["All citations valid"],
        severity="info",
    )


def eval_claim_density(
    report: str,
    min_density: float = MIN_CLAIM_DENSITY,
) -> EvalResult:
    """
    Evaluate claim density.
    
    Factual claims should be appropriately dense.
    """
    citations = CITATION_PATTERN.findall(report)
    
    if len(report) < 100:
        return EvalResult(
            passed=True,
            reasons=["Report too short for density check"],
            severity="info",
        )
    
    density = len(citations) / (len(report) / 100)
    
    if density < min_density:
        return EvalResult(
            passed=False,
            reasons=[f"Claim density {density:.2f} below minimum {min_density}"],
            severity="warn",
        )
    
    return EvalResult(
        passed=True,
        reasons=[f"Claim density {density:.2f} acceptable"],
        severity="info",
    )


def eval_evidence_reuse_safety(
    evidence_ids: List[str],
    query_hash: str,
    evidence_query_hashes: dict,  # evidence_id -> query_hash
) -> EvalResult:
    """
    Evaluate evidence reuse safety.
    
    All evidence must be scoped to current query.
    """
    invalid = []
    
    for eid in evidence_ids:
        eid_hash = evidence_query_hashes.get(eid)
        # Allow null hashes (global artifacts)
        if eid_hash is not None and eid_hash != query_hash:
            invalid.append(eid)
    
    if invalid:
        return EvalResult(
            passed=False,
            reasons=[f"Cross-query evidence: {invalid}"],
            severity="fail",
        )
    
    return EvalResult(
        passed=True,
        reasons=["All evidence properly scoped"],
        severity="info",
    )


def run_all_evals(
    report: str,
    evidence_ids: List[str],
    query_hash: str,
    evidence_query_hashes: dict,
) -> List[EvalResult]:
    """
    Run all evaluation checks.
    
    Returns:
        List of evaluation results
    """
    results = [
        eval_grounding(report, evidence_ids),
        eval_claim_density(report),
        eval_evidence_reuse_safety(evidence_ids, query_hash, evidence_query_hashes),
    ]
    
    return results


def check_eval_pass(results: List[EvalResult]) -> None:
    """
    Check if any eval failed with severity 'fail'.
    
    Raises:
        EvalFailureError: If any eval has severity 'fail'
    """
    for result in results:
        if result.severity == "fail" and not result.passed:
            raise EvalFailureError(
                f"# Evaluation Failed\n"
                f"Reasons: {'; '.join(result.reasons)}"
            )


def get_eval_summary(results: List[EvalResult]) -> dict:
    """Get summary of eval results."""
    return {
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "warnings": sum(1 for r in results if r.severity == "warn"),
        "failures": sum(1 for r in results if r.severity == "fail" and not r.passed),
    }
