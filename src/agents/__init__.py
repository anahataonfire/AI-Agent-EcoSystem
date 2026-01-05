# src/agents/__init__.py
"""
DTL Agents Package

Provides agent implementations for the DTL v2.0 multi-agent system.
Each agent has a corresponding .skill.md capability manifest.
"""

from .base import (
    BaseAgent, 
    ProposalEnvelope, 
    AgentManifest,
    ManifestParseError,
    ManifestValidationError,
    CapabilityDeniedError,
    generate_plan_id,
    AGENTS_DIR,
    PROJECT_ROOT,
    AGENT_ID_PATTERN,
)
from .reporter import ReporterAgent
from .diagnostician import DiagnosticianAgent

__all__ = [
    # Base
    'BaseAgent',
    'ProposalEnvelope',
    'AgentManifest',
    # Errors
    'ManifestParseError',
    'ManifestValidationError',
    'CapabilityDeniedError',
    # Utilities
    'generate_plan_id',
    'AGENTS_DIR',
    'PROJECT_ROOT',
    'AGENT_ID_PATTERN',
    # Agents
    'ReporterAgent',
    'DiagnosticianAgent',
]
