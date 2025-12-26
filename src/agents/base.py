"""
Agent Base Classes for DTL v2.0

Provides the base interface for all agents in the DTL system.
Each agent must:
1. Have a SKILL.md capability manifest
2. Wrap outputs in ProposalEnvelope with capability_claims
3. Pass through InterAgentFirewall for validation

Determinism Rules:
- Agents NEVER call datetime.now() - timestamp comes from runner
- All identifiers derived from run_id + run_ts for replay consistency
"""

import json
import hashlib
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Any


# Project root for manifest resolution (single source of truth)
# P0 Fix #3: Use AGENTS_DIR (manifests co-located with code)
PROJECT_ROOT = Path(os.environ.get('DTL_PROJECT_ROOT', Path(__file__).parent.parent.parent))
AGENTS_DIR = PROJECT_ROOT / 'src' / 'agents'

# Schema regex for agent_id validation (must match proposal_envelope.json)
AGENT_ID_PATTERN = re.compile(r'^[a-z]+-v[0-9]+\.[0-9]+$')


class ManifestParseError(Exception):
    """Raised when SKILL.md parsing fails."""
    pass


class ManifestValidationError(Exception):
    """Raised when manifest validation fails."""
    pass


class CapabilityDeniedError(Exception):
    """Raised when an agent claims a capability it doesn't have."""
    pass


@dataclass
class ProposalEnvelope:
    """
    Wrapper for all agent outputs.
    
    Enables replay and prevents cross-run leakage.
    content_hash covers the FULL envelope (not just payload).
    
    P1 Fix #4: timestamp is passed in, not generated with datetime.now().
    """
    agent_id: str
    schema_version: str
    run_id: str
    timestamp: str  # Must be passed from runner for determinism
    content_hash: str
    payload: dict
    capability_claims: list[str]  # Required, no default
    
    def compute_hash(self) -> str:
        """
        Compute hash over FULL canonical envelope (excluding content_hash itself).
        
        Hash covers agent_id, run_id, schema_version, timestamp, payload, capability_claims.
        """
        canonical = {
            'agent_id': self.agent_id,
            'schema_version': self.schema_version,
            'run_id': self.run_id,
            'timestamp': self.timestamp,
            'payload': self.payload,
            'capability_claims': sorted(self.capability_claims)
        }
        canonical_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        return f"sha256:{hashlib.sha256(canonical_str.encode()).hexdigest()}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProposalEnvelope':
        return cls(**data)
    
    @classmethod
    def create(
        cls, 
        agent_id: str, 
        run_id: str, 
        timestamp: str,  # P1 Fix #4: Required, from runner
        payload: dict,
        capability_claims: list[str]  # Required
    ) -> 'ProposalEnvelope':
        """Factory method to create envelope with computed hash."""
        envelope = cls(
            agent_id=agent_id,
            schema_version='2.0.0',
            run_id=run_id,
            timestamp=timestamp,
            content_hash='placeholder',
            payload=payload,
            capability_claims=capability_claims
        )
        envelope.content_hash = envelope.compute_hash()
        return envelope


@dataclass
class AgentCapability:
    """A single capability from SKILL.md."""
    name: str
    allowed: bool
    description: Optional[str] = None


class AgentManifest:
    """
    Parsed representation of a SKILL.md file.
    
    Strict parsing with fail-closed behavior.
    P1 Fix #5: agent_id validated with schema regex.
    """
    
    def __init__(self, skill_path: Path, fail_closed: bool = True):
        self.skill_path = skill_path
        self.agent_id: str = ""
        self.role: str = ""
        self.allowed: list[str] = []
        self.denied: list[str] = []
        self.valid: bool = False
        self.parse_errors: list[str] = []
        
        if not skill_path.exists():
            if fail_closed:
                raise ManifestParseError(f"Manifest not found: {skill_path}")
            self.parse_errors.append(f"File not found: {skill_path}")
            return
        
        self._parse(fail_closed)
        self._validate(fail_closed)
    
    def _parse(self, fail_closed: bool):
        """Parse SKILL.md to extract capabilities with strict validation."""
        content = self.skill_path.read_text()
        
        # Extract agent ID - REQUIRED
        agent_id_found = False
        for line in content.split('\n'):
            if '**Agent ID**' in line:
                if '`' in line:
                    parts = line.split('`')
                    if len(parts) >= 2:
                        self.agent_id = parts[1]
                        agent_id_found = True
            elif '**Role**' in line:
                if ':' in line:
                    self.role = line.split(':')[-1].strip()
        
        if not agent_id_found:
            error = f"Missing **Agent ID** in {self.skill_path}"
            self.parse_errors.append(error)
            if fail_closed:
                raise ManifestParseError(error)
        
        # Extract allowed/denied capabilities
        in_allowed = False
        in_denied = False
        
        for line in content.split('\n'):
            if '### ALLOWED' in line:
                in_allowed = True
                in_denied = False
            elif '### DENIED' in line:
                in_allowed = False
                in_denied = True
            elif line.startswith('## ') or line.startswith('# '):
                in_allowed = False
                in_denied = False
            elif line.startswith('- `') and '`' in line[3:]:
                cap_name = line.split('`')[1]
                if in_allowed:
                    self.allowed.append(cap_name)
                elif in_denied:
                    self.denied.append(cap_name)
        
        # Require at least one allowed capability
        if not self.allowed:
            error = f"No ALLOWED capabilities in {self.skill_path}"
            self.parse_errors.append(error)
            if fail_closed:
                raise ManifestParseError(error)
    
    def _validate(self, fail_closed: bool):
        """Validate manifest structure."""
        # Check allowed/denied are disjoint
        overlap = set(self.allowed) & set(self.denied)
        if overlap:
            error = f"Capabilities in both ALLOWED and DENIED: {overlap}"
            self.parse_errors.append(error)
            if fail_closed:
                raise ManifestValidationError(error)
        
        # P1 Fix #5: Validate agent_id with schema regex
        if not AGENT_ID_PATTERN.match(self.agent_id):
            error = f"Invalid agent_id format: '{self.agent_id}', must match ^[a-z]+-v[0-9]+.[0-9]+$"
            self.parse_errors.append(error)
            if fail_closed:
                raise ManifestValidationError(error)
        
        self.valid = len(self.parse_errors) == 0
    
    def is_allowed(self, capability: str) -> bool:
        """Check if a capability is allowed."""
        return capability in self.allowed
    
    def is_denied(self, capability: str) -> bool:
        """Check if a capability is explicitly denied."""
        return capability in self.denied
    
    def validate_claims(self, claims: list[str]) -> tuple[bool, list[str]]:
        """
        Validate a list of capability claims.
        
        Returns (valid, unauthorized_claims).
        Check claims against both allowed list and denied list.
        """
        unauthorized = []
        for claim in claims:
            if claim not in self.allowed:
                unauthorized.append(claim)
            if claim in self.denied:
                unauthorized.append(f"{claim} (explicitly denied)")
        
        return len(unauthorized) == 0, list(set(unauthorized))


class BaseAgent(ABC):
    """
    Base class for all DTL agents.
    
    Subclasses must implement:
    - process(): Main agent logic returning (payload, capability_claims)
    - SKILL_FILE: Name of capability manifest (resolved from AGENTS_DIR)
    
    Determinism: Agents receive run_ts from runner and never call datetime.now().
    """
    
    SKILL_FILE: str = ""  # Subclass must override
    
    def __init__(self, run_id: str, run_ts: str, firewall=None, runner_capabilities: Optional[list[str]] = None):
        """
        Initialize agent.
        
        Args:
            run_id: Unique run identifier
            run_ts: ISO8601 timestamp from runner (for determinism)
            firewall: Optional InterAgentFirewall for validation
            runner_capabilities: Optional additional capabilities granted by runner (P1 Fix #6)
        """
        self.run_id = run_id
        self.run_ts = run_ts  # P0 Fix #2 / P1 Fix #4: Timestamp from runner
        self.firewall = firewall
        self.runner_capabilities = runner_capabilities or []  # P1 Fix #6
        self.manifest: Optional[AgentManifest] = None
        self._load_manifest()
    
    def _load_manifest(self):
        """
        Load capability manifest from SKILL.md.
        
        Uses AGENTS_DIR from project root.
        Fail closed if manifest missing/invalid.
        """
        if not self.SKILL_FILE:
            raise ManifestParseError(f"{self.__class__.__name__} has no SKILL_FILE defined")
        
        skill_path = AGENTS_DIR / self.SKILL_FILE
        self.manifest = AgentManifest(skill_path, fail_closed=True)
    
    @property
    def agent_id(self) -> str:
        """Get agent ID from manifest."""
        if self.manifest and self.manifest.valid:
            return self.manifest.agent_id
        raise ManifestValidationError("Agent has no valid manifest")
    
    def check_capability(self, capability: str) -> bool:
        """Check if this agent has a capability (from manifest or runner)."""
        if capability in self.runner_capabilities:
            return True  # P1 Fix #6: Runner-granted capabilities
        if not self.manifest:
            return False
        return self.manifest.is_allowed(capability)
    
    def validate_claims(self, claims: list[str]) -> None:
        """
        Validate capability claims against manifest and runner grants.
        
        Raises CapabilityDeniedError if claims are unauthorized.
        """
        if not self.manifest:
            raise ManifestValidationError("No manifest loaded")
        
        # Check claims against manifest + runner grants
        unauthorized = []
        for claim in claims:
            if claim in self.runner_capabilities:
                continue  # P1 Fix #6: Runner-granted capability
            if claim not in self.manifest.allowed:
                unauthorized.append(claim)
            if claim in self.manifest.denied:
                unauthorized.append(f"{claim} (explicitly denied)")
        
        if unauthorized:
            raise CapabilityDeniedError(
                f"Agent {self.agent_id} cannot claim capabilities: {list(set(unauthorized))}"
            )
    
    def wrap_output(
        self, 
        payload: dict, 
        capability_claims: list[str]
    ) -> ProposalEnvelope:
        """
        Wrap output in ProposalEnvelope.
        
        Validates capability_claims before creating envelope.
        Validates envelope through firewall if configured.
        """
        # Validate claims against manifest
        self.validate_claims(capability_claims)
        
        envelope = ProposalEnvelope.create(
            agent_id=self.agent_id,
            run_id=self.run_id,
            timestamp=self.run_ts,  # P1 Fix #4: Use run_ts from runner
            payload=payload,
            capability_claims=capability_claims
        )
        
        # Validate through firewall
        if self.firewall:
            result = self.firewall.validate(envelope.to_dict(), "proposal_envelope")
            if not result.valid:
                raise ValueError(f"Firewall rejected envelope: {result.errors}")
        
        return envelope
    
    @abstractmethod
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Main agent processing logic.
        
        Must return a ProposalEnvelope with the agent's output.
        Subclasses should call wrap_output() with appropriate capability_claims.
        """
        pass


def generate_plan_id(run_id: str, agent_id: str, run_ts: str) -> str:
    """
    Generate a deterministic plan_id conforming to ^PLAN-[A-Z0-9]{8}$.
    
    P0 Fix #2: Uses run_ts (not datetime.now()) for determinism.
    Replay of same run_id + run_ts yields identical plan_id.
    
    Args:
        run_id: The run identifier
        agent_id: The agent identifier
        run_ts: ISO8601 timestamp from runner (e.g., "2025-12-26T20:30:49+00:00")
    """
    # Bucket by hour from run_ts (first 13 chars: YYYY-MM-DDTHH)
    bucket = run_ts[:13] if len(run_ts) >= 13 else run_ts
    seed = f"{run_id}:{bucket}:{agent_id}"
    hash_bytes = hashlib.sha256(seed.encode()).digest()
    
    # Convert to base32-like uppercase alphanumeric (0-9, A-V)
    import base64
    b32 = base64.b32encode(hash_bytes[:5]).decode()[:8].upper()
    
    return f"PLAN-{b32}"
