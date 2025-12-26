"""
DTL Control Plane - Core Components

This package contains the core control plane components for DTL v2.0:
- CommitGate: Validates CommitBundles before persistence
- KillSwitchEnforcer: Enforces kill switch policies
- SystemState: Runtime state management
- InterAgentFirewall: Validates inter-agent messages
- EvidenceCandidateQueue: Ephemeral evidence buffer
- RoutingStatisticsStore: Numeric-only routing stats
"""

from .commit_gate import CommitGate, CommitBundle, RejectionPayload, CommitResult, PromoteStatus, PromoteResult
from .kill_switch import KillSwitchEnforcer
from .state import SystemState, StateManager
from .firewall import InterAgentFirewall, FirewallResult
from .evidence_queue import EvidenceCandidateQueue, EvidenceCandidate
from .routing_stats import RoutingStatisticsStore, RoutingStatEntry
from .fingerprint import get_runtime_fingerprint

__all__ = [
    # CommitGate
    'CommitGate',
    'CommitBundle', 
    'RejectionPayload',
    'CommitResult',
    'PromoteStatus',
    'PromoteResult',
    # Kill Switch
    'KillSwitchEnforcer',
    # State
    'SystemState',
    'StateManager',
    # Firewall
    'InterAgentFirewall',
    'FirewallResult',
    # Evidence Queue
    'EvidenceCandidateQueue',
    'EvidenceCandidate',
    # Routing Stats
    'RoutingStatisticsStore',
    'RoutingStatEntry',
    # Fingerprint
    'get_runtime_fingerprint',
]

