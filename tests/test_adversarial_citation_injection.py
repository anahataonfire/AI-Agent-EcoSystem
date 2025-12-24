"""
Adversarial Citation Injection Defense Tests.

Tests against LLM-generated fake citations, citation laundering,
and self-referential grounding attacks.

Runtime target: <0.2s per test
"""

import pytest
import re
from unittest.mock import patch, MagicMock


# Import the validation functions we're testing
# (These will be imported after patching in each test)


class TestSelfCitationBan:
    """Test 1: Self-referential citation detection."""

    def test_reject_self_citation(self):
        """Report must NOT cite report:{query_hash}."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.exists.return_value = True
            
            from src.graph.workflow import validate_no_self_citation, SelfCitationError
            
            query_hash = "abc123def456"
            bad_report = f"""# Report
            
            Based on prior analysis [EVID:report:{query_hash}], we conclude...
            """
            
            with pytest.raises(SelfCitationError) as exc_info:
                validate_no_self_citation(bad_report, query_hash)
            
            assert "Self-referential" in str(exc_info.value)

    def test_allow_non_self_citation(self):
        """Citations to other evidence should pass."""
        from src.graph.workflow import validate_no_self_citation
        
        query_hash = "abc123def456"
        good_report = """# Report
        
        The data shows [EVID:ev_real_001] growth.
        """
        
        # Should not raise
        validate_no_self_citation(good_report, query_hash)


class TestEvidenceTypeWhitelist:
    """Test 2: Evidence type enforcement."""

    def test_reject_invalid_evidence_type(self):
        """Evidence with non-whitelisted type must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence has invalid type "llm_generated"
            mock_instance.get_with_metadata.return_value = {
                "payload": {"content": "fake"},
                "metadata": {"type": "llm_generated"}
            }
            
            from src.graph.workflow import validate_evidence_type_whitelist, InvalidEvidenceTypeError
            
            with pytest.raises(InvalidEvidenceTypeError) as exc_info:
                validate_evidence_type_whitelist(["ev_fake123"])
            
            assert "not allowed" in str(exc_info.value)

    def test_accept_valid_evidence_types(self):
        """Whitelisted types (rss_item, api_result, document) should pass."""
        valid_types = ["rss_item", "api_result", "document"]
        
        for valid_type in valid_types:
            with patch("src.graph.workflow.EvidenceStore") as mock_store:
                mock_instance = mock_store.return_value
                mock_instance.get_with_metadata.return_value = {
                    "payload": {"content": "real data"},
                    "metadata": {"type": valid_type}
                }
                
                from src.graph.workflow import validate_evidence_type_whitelist
                
                # Should not raise
                validate_evidence_type_whitelist([f"ev_{valid_type}"])


class TestCitationCardinality:
    """Test 3: Citation spray detection."""

    def test_reject_citation_spray(self):
        """Paragraph with >5 citations must be rejected (hallucination spray)."""
        from src.graph.workflow import validate_citation_cardinality, CitationCardinalityError
        
        # Ensure paragraph is long enough (>20 chars) to trigger validation
        spray_report = """# Report

This paragraph contains way too many citations for a single claim [EVID:ev_001] [EVID:ev_002] [EVID:ev_003] [EVID:ev_004] [EVID:ev_005] [EVID:ev_006] [EVID:ev_007] which indicates potential hallucination spray attack.
        """
        
        with pytest.raises(CitationCardinalityError) as exc_info:
            validate_citation_cardinality(spray_report)
        
        assert "spray" in str(exc_info.value).lower()

    def test_accept_reasonable_citations(self):
        """Paragraph with 1-5 citations should pass."""
        from src.graph.workflow import validate_citation_cardinality
        
        good_report = """# Report
        
        The market rose 5% [EVID:ev_001] following earnings [EVID:ev_002].
        
        ### Execution Provenance
        - Mode: Normal
        """
        
        # Should not raise
        validate_citation_cardinality(good_report)


class TestEvidencePayloadValidation:
    """Test 4-5: Empty and duplicate payload detection."""

    def test_reject_empty_payload(self):
        """Evidence with empty payload must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.get_with_metadata.return_value = {
                "payload": {},
                "metadata": {"type": "rss_item"}
            }
            
            from src.graph.workflow import validate_evidence_payloads, InvalidEvidencePayloadError
            
            with pytest.raises(InvalidEvidencePayloadError) as exc_info:
                validate_evidence_payloads(["ev_empty"])
            
            assert "empty" in str(exc_info.value).lower()

    def test_reject_short_payload(self):
        """Evidence with payload < 50 chars must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.get_with_metadata.return_value = {
                "payload": {"t": "x"},  # Very short
                "metadata": {"type": "rss_item"}
            }
            
            from src.graph.workflow import validate_evidence_payloads, InvalidEvidencePayloadError
            
            with pytest.raises(InvalidEvidencePayloadError) as exc_info:
                validate_evidence_payloads(["ev_short"])
            
            assert "too short" in str(exc_info.value).lower()

    def test_reject_duplicate_payloads(self):
        """≥3 identical payloads indicate evidence laundering."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # All three have identical payload
            duplicate_payload = {
                "payload": {"title": "Same content repeated for laundering attack", "content": "Duplicate data"},
                "metadata": {"type": "rss_item"}
            }
            mock_instance.get_with_metadata.return_value = duplicate_payload
            
            from src.graph.workflow import validate_evidence_payloads, InvalidEvidencePayloadError
            
            with pytest.raises(InvalidEvidencePayloadError) as exc_info:
                validate_evidence_payloads(["ev_dup1", "ev_dup2", "ev_dup3"])
            
            assert "duplication" in str(exc_info.value).lower()

    def test_accept_legitimate_payloads(self):
        """Unique, sufficiently long payloads should pass."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            def mock_get(eid):
                return {
                    "payload": {
                        "title": f"Unique evidence item {eid}",
                        "content": f"Sufficiently long content for evidence {eid} that meets the 50 char minimum."
                    },
                    "metadata": {"type": "rss_item"}
                }
            
            mock_instance.get_with_metadata.side_effect = mock_get
            
            from src.graph.workflow import validate_evidence_payloads
            
            # Should not raise
            validate_evidence_payloads(["ev_001", "ev_002"])


class TestLegitimateGrounding:
    """Control test: legitimate grounding should pass all checks."""

    def test_accept_legitimate_grounding(self):
        """Well-formed report with valid citations should pass."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            mock_instance.exists.return_value = True
            mock_instance.get_with_metadata.return_value = {
                "payload": {
                    "title": "Real news article about markets",
                    "content": "Comprehensive analysis of market trends with sufficient detail."
                },
                "metadata": {
                    "type": "rss_item",
                    "lifecycle": "active",
                    "query_hash": "test_hash"
                }
            }
            
            from src.graph.workflow import (
                validate_no_self_citation,
                validate_evidence_type_whitelist,
                validate_citation_cardinality,
                validate_evidence_payloads
            )
            
            query_hash = "test_hash"
            good_report = """# Market Analysis

            The index rose 3.2% today [EVID:ev_real001].
            
            Analysts reported positive earnings [EVID:ev_real002].
            
            ### Execution Provenance
            - Mode: Normal
            """
            
            citations = ["ev_real001", "ev_real002"]
            
            # All validations should pass
            validate_no_self_citation(good_report, query_hash)
            validate_evidence_type_whitelist(citations)
            validate_citation_cardinality(good_report)
            validate_evidence_payloads(citations)
