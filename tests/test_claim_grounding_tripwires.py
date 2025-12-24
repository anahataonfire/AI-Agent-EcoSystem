"""
Grounding Regression Tripwires.

Fast (<0.2s) source-inspection tests to prevent grounding logic drift.
Uses inspect.getsource() - no execution.
"""

import pytest
import inspect
import re


class TestGroundingRegressionTripwires:
    """Tripwires to catch structural drift in grounding logic."""

    def test_citation_regex_exists_in_workflow(self):
        """TRIPWIRE: Citation pattern must be defined in workflow."""
        from src.graph import workflow
        source = inspect.getsource(workflow)
        
        # Must define [EVID: pattern
        assert r'\[EVID:' in source or '[EVID:' in source, \
            "Citation pattern [EVID: must exist in workflow.py"

    def test_validate_claim_grounding_is_called_in_reporter(self):
        """TRIPWIRE: reporter_node must call validate_claim_grounding."""
        from src.graph.workflow import reporter_node
        source = inspect.getsource(reporter_node)
        
        assert 'validate_claim_grounding' in source, \
            "reporter_node must call validate_claim_grounding"

    def test_grounding_validation_before_identity_write(self):
        """TRIPWIRE: Grounding validation must occur BEFORE update_identity."""
        from src.graph.workflow import reporter_node
        source = inspect.getsource(reporter_node)
        
        # Find positions
        grounding_pos = source.find('validate_claim_grounding')
        identity_pos = source.find('update_identity')
        
        assert grounding_pos != -1, "validate_claim_grounding not found in reporter_node"
        assert identity_pos != -1, "update_identity not found in reporter_node"
        assert grounding_pos < identity_pos, \
            "validate_claim_grounding must be called BEFORE update_identity"

    def test_grounding_validation_before_evidence_save(self):
        """TRIPWIRE: Grounding validation must occur BEFORE evidence_store.save."""
        from src.graph.workflow import reporter_node
        source = inspect.getsource(reporter_node)
        
        grounding_pos = source.find('validate_claim_grounding')
        save_pos = source.find('evidence_store.save')
        
        assert grounding_pos != -1, "validate_claim_grounding not found"
        assert save_pos != -1, "evidence_store.save not found"
        assert grounding_pos < save_pos, \
            "validate_claim_grounding must be called BEFORE evidence_store.save"

    def test_grounding_error_exception_exists(self):
        """TRIPWIRE: GroundingError exception must be defined."""
        from src.graph.workflow import GroundingError
        
        assert issubclass(GroundingError, Exception), \
            "GroundingError must be an Exception subclass"

    def test_grounding_failure_returns_abort_message(self):
        """TRIPWIRE: Grounding failure must return abort message."""
        from src.graph.workflow import reporter_node
        source = inspect.getsource(reporter_node)
        
        assert 'Report Generation Failed' in source, \
            "reporter_node must return abort message on grounding failure"
        assert 'claims lack evidence grounding' in source, \
            "Abort message must mention grounding failure reason"

    def test_factual_indicators_pattern_exists(self):
        """TRIPWIRE: Factual indicator pattern must exist for paragraph detection."""
        from src.graph import workflow
        source = inspect.getsource(workflow)
        
        # Must define factual indicator words
        assert 'increased' in source and 'decreased' in source, \
            "Factual indicators must include 'increased' and 'decreased'"
        assert 'FACTUAL_INDICATORS' in source or 'factual' in source.lower(), \
            "Factual indicators pattern must be defined"
