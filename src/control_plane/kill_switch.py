"""
Kill Switch Enforcer for DTL v2.0

Enforces kill switch policies before agent execution.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class KillSwitchState:
    """State of a single kill switch."""
    name: str
    enabled: bool
    description: str
    enforcement: str  # "hard" or "soft"
    blocks: list[str]


@dataclass
class EnforcementResult:
    """Result of kill switch enforcement."""
    can_proceed: bool
    active_switches: list[str]
    blocked_operations: list[str]
    warnings: list[str]


class KillSwitchEnforcer:
    """
    Enforces kill switch policies.
    
    Kill switches are checked BEFORE any agent runs (Step 3 in enforcement order).
    Hard switches block execution entirely.
    Soft switches issue warnings but allow continuation.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("config/kill_switches.json")
        self._switches: dict[str, KillSwitchState] = {}
        self._enforcement_order: list[str] = []
        self._load_config()
    
    def _load_config(self):
        """Load kill switch configuration."""
        if not self.config_path.exists():
            print(f"[WARN] Kill switch config not found: {self.config_path}")
            return
        
        with open(self.config_path, 'r') as f:
            data = json.load(f)
        
        self._enforcement_order = data.get("enforcement_order", [])
        
        for name, config in data.get("switches", {}).items():
            self._switches[name] = KillSwitchState(
                name=name,
                enabled=config.get("enabled", False),
                description=config.get("description", ""),
                enforcement=config.get("enforcement", "soft"),
                blocks=config.get("blocks", [])
            )
    
    def enforce(self, requested_operations: Optional[list[str]] = None) -> EnforcementResult:
        """
        Enforce all kill switches.
        
        Args:
            requested_operations: List of operations the run wants to perform.
                                  If any are blocked by an active switch, enforcement fails.
        
        Returns:
            EnforcementResult with proceed/block decision.
        """
        requested = set(requested_operations or [])
        active_switches = []
        blocked_operations = []
        warnings = []
        can_proceed = True
        
        # Check switches in enforcement order
        for switch_name in self._enforcement_order:
            switch = self._switches.get(switch_name)
            if not switch or not switch.enabled:
                continue
            
            active_switches.append(switch_name)
            
            # Check if any requested operations are blocked
            blocked_by_switch = requested.intersection(set(switch.blocks))
            if blocked_by_switch:
                blocked_operations.extend(blocked_by_switch)
                
                if switch.enforcement == "hard":
                    can_proceed = False
                else:
                    warnings.append(f"{switch_name}: soft-blocked {blocked_by_switch}")
        
        # DISABLE_WRITES is a special case - always blocks if enabled
        if "DISABLE_WRITES" in self._switches:
            write_switch = self._switches["DISABLE_WRITES"]
            if write_switch.enabled and write_switch.enforcement == "hard":
                can_proceed = False
                blocked_operations.append("commit_gate_pass")
        
        return EnforcementResult(
            can_proceed=can_proceed,
            active_switches=active_switches,
            blocked_operations=blocked_operations,
            warnings=warnings
        )
    
    def is_enabled(self, switch_name: str) -> bool:
        """Check if a specific switch is enabled."""
        switch = self._switches.get(switch_name)
        return switch.enabled if switch else False
    
    def get_active_switches(self) -> list[str]:
        """Get list of all enabled switches."""
        return [name for name, switch in self._switches.items() if switch.enabled]
    
    def is_operation_blocked(self, operation: str) -> tuple[bool, Optional[str]]:
        """
        Check if a specific operation is blocked.
        
        Returns:
            (is_blocked, blocking_switch_name)
        """
        for switch in self._switches.values():
            if switch.enabled and operation in switch.blocks:
                return True, switch.name
        return False, None
