"""
Inter-Agent Firewall for DTL v2.0

Validates all messages passed between agents using JSON Schema.
Enforces typed text rules and prevents injection attacks.

SCOPED SCANNING: Only scans high-risk fields for injection patterns.
Low-risk fields (summary, description) are allowed freely (schema handles length).
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any
import jsonschema


@dataclass
class FirewallResult:
    """Result of firewall validation."""
    valid: bool
    schema_name: str
    errors: list[str]
    sanitized_payload: Optional[dict] = None


# Fields that require injection scanning (high-risk, agent-facing directives)
HIGH_RISK_FIELDS = {
    "directives",
    "directive",
    "tool_args",
    "tool_arguments",
    "shell",
    "command",
    "code",
    "script",
    "execute",
    "eval",
    "query",  # Could be SQL/shell injection
}

# Fields that are SAFE (human-facing, length-bounded by schema)
SAFE_FIELDS = {
    "summary",
    "description",
    "title",
    "name",
    "label",
    "message",
    "details",
    "notes",
}

# Patterns to reject in HIGH-RISK fields only
DANGEROUS_PATTERNS = [
    (re.compile(r'<script', re.IGNORECASE), "HTML script tag"),
    (re.compile(r'javascript:', re.IGNORECASE), "JavaScript protocol"),
    (re.compile(r'\$\([^)]+\)', re.IGNORECASE), "Shell command substitution"),
    (re.compile(r';\s*(rm|sudo|chmod|curl|wget)\s', re.IGNORECASE), "Shell command chain"),
    (re.compile(r'`[^`]+`'), "Backtick execution"),
    (re.compile(r'\{\{[^}]+\}\}'), "Template injection"),
    (re.compile(r'\{%[^%]+%\}'), "Jinja template injection"),
    (re.compile(r'exec\s*\('), "Python exec"),
    (re.compile(r'eval\s*\('), "Python eval"),
]


class InterAgentFirewall:
    """
    Validates all inter-agent messages.
    
    All agent-to-agent communication MUST pass through this firewall.
    Messages are validated against JSON Schema and scanned for injection patterns.
    
    SCOPED SCANNING:
    - HIGH_RISK_FIELDS: Scanned for dangerous patterns
    - SAFE_FIELDS: Not scanned (length handled by schema)
    - Unknown fields in additionalProperties=false schemas: Rejected by schema
    """
    
    def __init__(self, schemas_path: Optional[str] = None):
        self.schemas_path = Path(schemas_path) if schemas_path else Path("config/schemas")
        self._schemas: dict[str, dict] = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all JSON schemas from the schemas directory."""
        if not self.schemas_path.exists():
            print(f"[WARN] Schemas path not found: {self.schemas_path}")
            return
        
        for schema_file in self.schemas_path.glob("*.json"):
            try:
                with open(schema_file, 'r') as f:
                    schema = json.load(f)
                schema_name = schema_file.stem
                self._schemas[schema_name] = schema
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARN] Failed to load schema {schema_file}: {e}")
    
    def validate(self, message: dict, schema_name: str) -> FirewallResult:
        """
        Validate a message against its schema.
        
        Args:
            message: The message dict to validate
            schema_name: Name of the schema (without .json extension)
        
        Returns:
            FirewallResult with validation status and any errors
        """
        errors = []
        
        # Check schema exists
        if schema_name not in self._schemas:
            return FirewallResult(
                valid=False,
                schema_name=schema_name,
                errors=[f"Unknown schema: {schema_name}"]
            )
        
        schema = self._schemas[schema_name]
        
        # JSON Schema validation (handles types, lengths, enum, additionalProperties)
        try:
            jsonschema.validate(message, schema)
        except jsonschema.ValidationError as e:
            json_pointer = "/" + "/".join(str(p) for p in e.path) if e.path else "/"
            errors.append(f"Schema violation at {json_pointer}: {e.message}")
        
        # Scan ONLY high-risk fields for dangerous patterns
        injection_errors = self._scan_high_risk_fields(message)
        errors.extend(injection_errors)
        
        if errors:
            return FirewallResult(
                valid=False,
                schema_name=schema_name,
                errors=errors
            )
        
        return FirewallResult(
            valid=True,
            schema_name=schema_name,
            errors=[],
            sanitized_payload=message
        )
    
    def _scan_high_risk_fields(self, obj: Any, path: str = "", field_name: str = "") -> list[str]:
        """
        Scan ONLY high-risk fields for injection patterns.
        
        Safe fields (summary, description, etc.) are NOT scanned.
        This prevents false positives while maintaining security for command/directive fields.
        """
        errors = []
        
        if isinstance(obj, str):
            # Only scan if we're in a high-risk field
            if field_name.lower() in HIGH_RISK_FIELDS:
                for pattern, description in DANGEROUS_PATTERNS:
                    if pattern.search(obj):
                        errors.append(f"Injection pattern ({description}) at {path}")
        
        elif isinstance(obj, dict):
            for key, value in obj.items():
                field_path = f"{path}.{key}" if path else key
                # Pass the field name for risk assessment
                errors.extend(self._scan_high_risk_fields(value, field_path, key))
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                # Inherit field name from parent for list items
                errors.extend(self._scan_high_risk_fields(item, f"{path}[{i}]", field_name))
        
        return errors
    
    def get_available_schemas(self) -> list[str]:
        """Return list of loaded schema names."""
        return list(self._schemas.keys())
    
    def validate_envelope(self, envelope: dict) -> FirewallResult:
        """Convenience method to validate a ProposalEnvelope."""
        return self.validate(envelope, "proposal_envelope")
    
    def validate_strategist_output(self, message: dict) -> FirewallResult:
        """Validate Strategist → Researcher message."""
        return self.validate(message, "strategist_to_researcher")
    
    def validate_evidence_candidate(self, message: dict) -> FirewallResult:
        """Validate Researcher → Reporter evidence candidate."""
        return self.validate(message, "evidence_candidate")

