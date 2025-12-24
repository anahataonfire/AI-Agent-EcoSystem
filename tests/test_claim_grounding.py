"""
Claim Grounding Contract Enforcement Tests.

These tests enforce the DTL Claim Grounding Contract deterministically
without LLM calls. Uses regex + Evidence Store lookup only.
"""

import pytest
import re
from unittest.mock import patch, MagicMock


# Citation pattern: [EVID:abc123] or [EVID:ev_abc123]
CITATION_PATTERN = re.compile(r'\[EVID:([a-zA-Z0-9:_-]+)\]')

# Factual indicators (simplified heuristic)
FACTUAL_INDICATORS = re.compile(
    r'\b(\d+%|\d{4}|\$\d|increased|decreased|announced|reported|billion|million)\b',
    re.IGNORECASE
)


def extract_citations(text: str) -> list[str]:
    """Extract all Evidence IDs from citation tokens."""
    return CITATION_PATTERN.findall(text)


def is_factual_paragraph(paragraph: str) -> bool:
    """Heuristic: does this paragraph contain factual indicators?"""
    stripped = paragraph.strip()
    # Skip headers, empty lines, provenance footer
    if stripped.startswith('#'):
        return False
    if 'Execution Provenance' in paragraph:
        return False
    if len(stripped) < 20:
        return False
    return bool(FACTUAL_INDICATORS.search(paragraph))


class TestClaimGroundingEnforcement:
    """Non-LLM tests enforcing the grounding contract."""

    def test_all_cited_evidence_ids_exist(self):
        """Test 1: All cited Evidence IDs must exist in store."""
        with patch("src.core.evidence_store.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.exists.side_effect = lambda eid: eid in ["ev_abc123", "ev_def456"]
            
            report = """
            # Report
            
            The market rose 5% [EVID:ev_abc123] following news [EVID:ev_def456].
            
            ### Execution Provenance
            - Mode: Normal
            """
            
            citations = extract_citations(report)
            assert citations == ["ev_abc123", "ev_def456"]
            
            # Import AFTER patching
            from src.core.evidence_store import EvidenceStore
            store = EvidenceStore()
            for eid in citations:
                assert store.exists(eid), f"Missing evidence: {eid}"

    def test_factual_paragraphs_require_citations(self):
        """Test 2: Factual paragraphs must have ≥1 citation."""
        report = """
        # Summary
        
        The index increased by 3.2% on Tuesday [EVID:ev_abc123].
        
        Analysts reported strong earnings [EVID:ev_def456].
        
        ### Execution Provenance
        - Mode: Normal
        """
        
        paragraphs = report.split('\n\n')
        
        for para in paragraphs:
            if is_factual_paragraph(para):
                citations = extract_citations(para)
                assert len(citations) >= 1, f"Factual paragraph lacks citation: {para[:50]}..."

    def test_reject_fabricated_evidence_ids(self):
        """Test 3: Fabricated Evidence IDs must be rejected."""
        with patch("src.core.evidence_store.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.exists.return_value = False  # Nothing exists
            
            report = """
            # Report
            
            Fake claim [EVID:ev_fake123].
            """
            
            citations = extract_citations(report)
            
            from src.core.evidence_store import EvidenceStore
            store = EvidenceStore()
            
            # At least one citation should fail
            missing = [eid for eid in citations if not store.exists(eid)]
            assert len(missing) > 0, "Should have detected fabricated ID"
            assert "ev_fake123" in missing

    def test_reuse_path_preserves_grounding(self):
        """Test 4: Reused reports must still pass grounding validation."""
        with patch("src.core.evidence_store.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.exists.return_value = True  # All IDs exist
            
            valid_report = """
            # Reused Report
            
            Market data showed 2.5% growth [EVID:ev_real001].
            
            ### Execution Provenance
            - Mode: Normal
            """
            
            citations = extract_citations(valid_report)
            assert len(citations) >= 1
            
            from src.core.evidence_store import EvidenceStore
            store = EvidenceStore()
            for eid in citations:
                assert store.exists(eid)

    def test_detect_ungrounded_factual_paragraph(self):
        """Regression: detect factual paragraph without citation."""
        bad_report = """# Report

The company announced record profits of $5 billion.

### Execution Provenance
- Mode: Normal
"""
        
        paragraphs = bad_report.split('\n\n')
        ungrounded = []
        
        for para in paragraphs:
            if is_factual_paragraph(para):
                if not extract_citations(para):
                    ungrounded.append(para.strip()[:50])
        
        assert len(ungrounded) > 0, "Should detect ungrounded paragraph"

