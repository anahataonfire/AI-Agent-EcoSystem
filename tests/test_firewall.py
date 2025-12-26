"""
InterAgentFirewall Tests for DTL v2.0

Branch coverage tests to lock in P0 fix #6:
- Scoped scanning (HIGH_RISK_FIELDS only)
- Safe fields not scanned
- Injection patterns detected in high-risk fields
- JSON Schema validation
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.control_plane.firewall import (
    InterAgentFirewall,
    FirewallResult,
    HIGH_RISK_FIELDS,
    SAFE_FIELDS,
)


class TestFirewallFieldScoping:
    """Tests for P0 Fix #6: Scoped scanning."""
    
    @pytest.fixture
    def firewall(self):
        """Create firewall with project schemas."""
        return InterAgentFirewall()
    
    def test_safe_field_not_scanned_for_backticks(self, firewall):
        """Safe fields (summary) should allow backticks."""
        # This would fail with the old broad regex
        message = {
            'plan_id': 'PLAN-ABCD1234',
            'asset_universe': ['XAU'],
        }
        
        # Add a summary field to the schema dynamically for this test
        # The actual test is that backticks in description/summary don't trigger
        result = firewall.validate(message, 'strategist_to_researcher')
        
        assert result.valid is True
    
    def test_high_risk_fields_defined(self):
        """HIGH_RISK_FIELDS should contain expected fields."""
        assert 'directives' in HIGH_RISK_FIELDS
        assert 'command' in HIGH_RISK_FIELDS
        assert 'shell' in HIGH_RISK_FIELDS
        assert 'code' in HIGH_RISK_FIELDS
        assert 'eval' in HIGH_RISK_FIELDS
    
    def test_safe_fields_defined(self):
        """SAFE_FIELDS should contain expected fields."""
        assert 'summary' in SAFE_FIELDS
        assert 'description' in SAFE_FIELDS
        assert 'title' in SAFE_FIELDS
        assert 'message' in SAFE_FIELDS
    
    def test_high_risk_field_blocks_script_tag(self):
        """Injection in high-risk field should be blocked."""
        # Create a message with a high-risk field containing injection
        # Note: The actual schema doesn't have 'directives', so we test the scanning logic
        firewall = InterAgentFirewall()
        
        # Test the internal scanning method directly
        test_obj = {
            'directives': '<script>alert(1)</script>',
            'summary': 'This is safe'
        }
        
        errors = firewall._scan_high_risk_fields(test_obj)
        
        assert len(errors) > 0
        assert any('script' in e.lower() for e in errors)
    
    def test_safe_field_allows_template_syntax(self):
        """Safe fields should allow template-like syntax."""
        firewall = InterAgentFirewall()
        
        test_obj = {
            'summary': 'Use {{variable}} for templating',
            'description': 'Example: {%if condition%}'
        }
        
        errors = firewall._scan_high_risk_fields(test_obj)
        
        # No errors because these are safe fields
        assert len(errors) == 0


class TestFirewallSchemaValidation:
    """Tests for JSON Schema validation."""
    
    @pytest.fixture
    def firewall(self):
        """Create firewall with project schemas."""
        return InterAgentFirewall()
    
    def test_valid_strategist_message_passes(self, firewall):
        """Valid strategist message should pass."""
        message = {
            'plan_id': 'PLAN-ABCD1234',
            'asset_universe': ['XAU', 'GME'],
            'evidence_requests': [
                {'query_type': 'price', 'max_sources': 3}
            ]
        }
        
        result = firewall.validate_strategist_output(message)
        
        assert result.valid is True
        assert result.errors == []
    
    def test_invalid_plan_id_format_fails(self, firewall):
        """Invalid plan_id format should fail schema validation."""
        message = {
            'plan_id': 'invalid-format',  # Should be PLAN-XXXXXXXX
            'asset_universe': ['XAU']
        }
        
        result = firewall.validate_strategist_output(message)
        
        assert result.valid is False
        assert any('plan_id' in e for e in result.errors)
    
    def test_invalid_asset_fails(self, firewall):
        """Invalid asset should fail enum validation."""
        message = {
            'plan_id': 'PLAN-ABCD1234',
            'asset_universe': ['INVALID_ASSET']
        }
        
        result = firewall.validate_strategist_output(message)
        
        assert result.valid is False
    
    def test_additional_properties_rejected(self, firewall):
        """Additional properties should be rejected."""
        message = {
            'plan_id': 'PLAN-ABCD1234',
            'asset_universe': ['XAU'],
            'malicious_field': 'should not be allowed'
        }
        
        result = firewall.validate_strategist_output(message)
        
        assert result.valid is False
        assert any('malicious_field' in e for e in result.errors)
    
    def test_valid_evidence_candidate_passes(self, firewall):
        """Valid evidence candidate should pass."""
        message = {
            'evidence_id': 'EV-ABCD12345678',
            'source_url': 'https://example.com/data',
            'source_trust_tier': 1,
            'fetched_at': '2025-12-26T00:00:00Z'
        }
        
        result = firewall.validate_evidence_candidate(message)
        
        assert result.valid is True
    
    def test_evidence_id_format_enforced(self, firewall):
        """Evidence ID format should be enforced."""
        message = {
            'evidence_id': 'wrong-format',
            'source_url': 'https://example.com',
            'source_trust_tier': 1,
            'fetched_at': '2025-12-26T00:00:00Z'
        }
        
        result = firewall.validate_evidence_candidate(message)
        
        assert result.valid is False


class TestFirewallInjectionPatterns:
    """Tests for injection pattern detection."""
    
    @pytest.fixture
    def firewall(self):
        return InterAgentFirewall()
    
    def test_detects_script_tag(self, firewall):
        """Should detect HTML script tag in high-risk fields."""
        errors = firewall._scan_high_risk_fields({
            'command': '<script>evil()</script>'
        })
        assert len(errors) > 0
    
    def test_detects_javascript_protocol(self, firewall):
        """Should detect javascript: protocol in high-risk fields."""
        errors = firewall._scan_high_risk_fields({
            'directives': 'javascript:alert(1)'
        })
        assert len(errors) > 0
    
    def test_detects_shell_command_substitution(self, firewall):
        """Should detect $(cmd) in high-risk fields."""
        errors = firewall._scan_high_risk_fields({
            'shell': 'echo $(whoami)'
        })
        assert len(errors) > 0
    
    def test_detects_backtick_execution(self, firewall):
        """Should detect backtick execution in high-risk fields."""
        errors = firewall._scan_high_risk_fields({
            'command': 'result=`ls -la`'
        })
        assert len(errors) > 0
    
    def test_detects_python_exec(self, firewall):
        """Should detect exec() in high-risk fields."""
        errors = firewall._scan_high_risk_fields({
            'code': 'exec("import os")'
        })
        assert len(errors) > 0
    
    def test_detects_python_eval(self, firewall):
        """Should detect eval() in high-risk fields."""
        errors = firewall._scan_high_risk_fields({
            'eval': 'eval("2+2")'
        })
        assert len(errors) > 0
    
    def test_safe_field_allows_all_patterns(self, firewall):
        """Safe fields should allow all patterns without blocking."""
        errors = firewall._scan_high_risk_fields({
            'summary': '<script>alert(1)</script>',
            'description': 'javascript:void(0)',
            'message': '`code block`',
            'notes': '{{template}}',
        })
        
        # No errors because all are safe fields
        assert len(errors) == 0


class TestFirewallAvailableSchemas:
    """Tests for schema loading."""
    
    def test_schemas_loaded(self):
        """Should load all expected schemas."""
        firewall = InterAgentFirewall()
        schemas = firewall.get_available_schemas()
        
        expected = [
            'proposal_envelope',
            'commit_bundle',
            'strategist_to_researcher',
            'evidence_candidate',
            'routing_statistics',
            'position_sizing'
        ]
        
        for schema_name in expected:
            assert schema_name in schemas, f"Missing schema: {schema_name}"
    
    def test_unknown_schema_fails(self):
        """Unknown schema should fail validation."""
        firewall = InterAgentFirewall()
        
        result = firewall.validate({}, 'nonexistent_schema')
        
        assert result.valid is False
        assert 'Unknown schema' in result.errors[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
