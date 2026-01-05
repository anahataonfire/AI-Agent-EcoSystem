"""
Claim-Evidence Entailment Tracking (P1 Fix)

This module provides structured tracking of claim-to-evidence relationships:
- Each claim is linked to specific evidence spans
- Support grades indicate strength of entailment
- Enables auditing of grounding quality beyond format checks

Schema:
    claim_id: Unique identifier (hash of claim text)
    claim_text: The factual claim being made
    evidence_id: The evidence being cited
    evidence_span: Specific text span supporting the claim
    support_grade: "strong" | "moderate" | "weak" | "unsupported"
    run_id: Which run generated this mapping
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SupportGrade(str, Enum):
    """Strength of evidence support for a claim."""
    STRONG = "strong"       # Evidence directly states the claim
    MODERATE = "moderate"   # Evidence implies the claim
    WEAK = "weak"           # Evidence tangentially related
    UNSUPPORTED = "unsupported"  # No evidence found


@dataclass
class ClaimEntailment:
    """A claim-to-evidence mapping with support grading."""
    claim_id: str
    claim_text: str
    evidence_id: str
    evidence_span: str
    support_grade: SupportGrade
    run_id: str
    created_at: str
    confidence: float = 0.0  # 0-1 confidence score (for future ML grading)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["support_grade"] = self.support_grade.value
        return result


DB_PATH = Path(__file__).parent.parent.parent / "data" / "claim_entailment.db"


def _get_connection() -> sqlite3.Connection:
    """Get database connection with schema initialization."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS claim_entailments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            evidence_span TEXT NOT NULL,
            support_grade TEXT NOT NULL,
            run_id TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            created_at TEXT NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_claim_id ON claim_entailments(claim_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_id ON claim_entailments(evidence_id);
        CREATE INDEX IF NOT EXISTS idx_run_id ON claim_entailments(run_id);
        CREATE INDEX IF NOT EXISTS idx_support_grade ON claim_entailments(support_grade);
    """)
    conn.commit()
    return conn


def compute_claim_id(claim_text: str) -> str:
    """Compute a stable ID for a claim based on normalized text."""
    normalized = claim_text.strip().lower()
    return f"claim_{hashlib.sha256(normalized.encode()).hexdigest()[:12]}"


class EntailmentStore:
    """
    Store for claim-evidence entailment mappings.
    
    Enables:
    - Tracking which claims cite which evidence
    - Auditing support quality
    - Identifying weakly-grounded claims
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the entailment store."""
        self.db_path = Path(db_path) if db_path else DB_PATH
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS claim_entailments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                evidence_span TEXT NOT NULL,
                support_grade TEXT NOT NULL,
                run_id TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_claim_id ON claim_entailments(claim_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_id ON claim_entailments(evidence_id);
            CREATE INDEX IF NOT EXISTS idx_run_id ON claim_entailments(run_id);
            CREATE INDEX IF NOT EXISTS idx_support_grade ON claim_entailments(support_grade);
        """)
        conn.commit()
        return conn
    
    def record_entailment(
        self,
        claim_text: str,
        evidence_id: str,
        evidence_span: str,
        support_grade: SupportGrade,
        run_id: str,
        confidence: float = 0.0
    ) -> str:
        """
        Record a claim-evidence entailment.
        
        Args:
            claim_text: The factual claim being made
            evidence_id: ID of the evidence being cited
            evidence_span: Specific text from evidence supporting claim
            support_grade: Strength of support
            run_id: ID of the run generating this mapping
            confidence: Optional confidence score (0-1)
        
        Returns:
            claim_id of the recorded entailment
        """
        claim_id = compute_claim_id(claim_text)
        now = datetime.now(timezone.utc).isoformat()
        
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO claim_entailments 
                (claim_id, claim_text, evidence_id, evidence_span, 
                 support_grade, run_id, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                claim_text,
                evidence_id,
                evidence_span,
                support_grade.value,
                run_id,
                confidence,
                now
            ))
            conn.commit()
        finally:
            conn.close()
        
        return claim_id
    
    def get_entailments_for_run(self, run_id: str) -> List[ClaimEntailment]:
        """Get all entailments for a specific run."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM claim_entailments WHERE run_id = ?",
                (run_id,)
            )
            rows = cursor.fetchall()
            return [self._row_to_entailment(row) for row in rows]
        finally:
            conn.close()
    
    def get_entailments_for_evidence(self, evidence_id: str) -> List[ClaimEntailment]:
        """Get all claims citing a specific piece of evidence."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM claim_entailments WHERE evidence_id = ?",
                (evidence_id,)
            )
            rows = cursor.fetchall()
            return [self._row_to_entailment(row) for row in rows]
        finally:
            conn.close()
    
    def get_weak_entailments(self, run_id: str = None) -> List[ClaimEntailment]:
        """
        Get entailments with weak or unsupported grades.
        
        Args:
            run_id: Optional filter by run
        
        Returns:
            List of weakly-grounded claims for review
        """
        conn = self._get_conn()
        try:
            query = """
                SELECT * FROM claim_entailments 
                WHERE support_grade IN ('weak', 'unsupported')
            """
            params = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_entailment(row) for row in rows]
        finally:
            conn.close()
    
    def get_grounding_stats(self, run_id: str = None) -> Dict[str, Any]:
        """
        Get statistics on entailment quality.
        
        Args:
            run_id: Optional filter by run
        
        Returns:
            Dict with counts by support grade and quality score
        """
        conn = self._get_conn()
        try:
            query = "SELECT support_grade, COUNT(*) as count FROM claim_entailments"
            params = []
            if run_id:
                query += " WHERE run_id = ?"
                params.append(run_id)
            query += " GROUP BY support_grade"
            
            cursor = conn.execute(query, params)
            by_grade = {row["support_grade"]: row["count"] for row in cursor.fetchall()}
            
            # Calculate grounding quality score (0-100)
            total = sum(by_grade.values())
            if total == 0:
                quality_score = 0
            else:
                # Weight: strong=1.0, moderate=0.7, weak=0.3, unsupported=0
                weights = {"strong": 1.0, "moderate": 0.7, "weak": 0.3, "unsupported": 0.0}
                weighted_sum = sum(
                    by_grade.get(grade, 0) * weight 
                    for grade, weight in weights.items()
                )
                quality_score = int((weighted_sum / total) * 100)
            
            return {
                "total_claims": total,
                "by_grade": by_grade,
                "grounding_quality_score": quality_score,
            }
        finally:
            conn.close()
    
    def _row_to_entailment(self, row: sqlite3.Row) -> ClaimEntailment:
        """Convert a database row to ClaimEntailment."""
        return ClaimEntailment(
            claim_id=row["claim_id"],
            claim_text=row["claim_text"],
            evidence_id=row["evidence_id"],
            evidence_span=row["evidence_span"],
            support_grade=SupportGrade(row["support_grade"]),
            run_id=row["run_id"],
            confidence=row["confidence"],
            created_at=row["created_at"],
        )


# ============================================================================
# GRADING HELPER (Crude initial implementation)
# ============================================================================

def grade_entailment(claim_text: str, evidence_text: str) -> SupportGrade:
    """
    Grade how well evidence supports a claim (crude keyword matching).
    
    This is a placeholder for more sophisticated NLI-based grading.
    In production, use an entailment model like DeBERTa-NLI.
    
    Args:
        claim_text: The claim being made
        evidence_text: The evidence being cited
    
    Returns:
        SupportGrade indicating strength of support
    """
    claim_lower = claim_text.lower()
    evidence_lower = evidence_text.lower()
    
    # Extract key terms from claim (naive approach)
    claim_words = set(claim_lower.split())
    evidence_words = set(evidence_lower.split())
    
    # Remove common stopwords
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", 
                 "being", "have", "has", "had", "do", "does", "did", "will",
                 "would", "could", "should", "may", "might", "must", "shall",
                 "to", "of", "in", "for", "on", "with", "at", "by", "from",
                 "as", "into", "through", "during", "before", "after", "above",
                 "below", "between", "under", "again", "further", "then", "once",
                 "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
                 "not", "only", "same", "than", "too", "very", "just", "also"}
    
    claim_words -= stopwords
    evidence_words -= stopwords
    
    if not claim_words:
        return SupportGrade.UNSUPPORTED
    
    # Calculate overlap
    overlap = claim_words & evidence_words
    overlap_ratio = len(overlap) / len(claim_words)
    
    if overlap_ratio >= 0.7:
        return SupportGrade.STRONG
    elif overlap_ratio >= 0.4:
        return SupportGrade.MODERATE
    elif overlap_ratio >= 0.2:
        return SupportGrade.WEAK
    else:
        return SupportGrade.UNSUPPORTED
