"""
DTL v2.0 Degraded Mode Controller

Manages system state transitions and operator alerts.
DEGRADED_MODE is an analysis-only state where:
- Writes to immutable stores are blocked
- Reports can still be generated
- Operator alert is sent
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class SystemState(Enum):
    NORMAL = "NORMAL"
    DEGRADED_MODE = "DEGRADED_MODE"
    HALTED = "HALTED"


class TriggerCondition(Enum):
    COMMIT_GATE_REJECTION = "COMMIT_GATE_REJECTION"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    FIREWALL_REJECTION = "FIREWALL_REJECTION"
    UNKNOWN = "UNKNOWN"


@dataclass
class DegradedModeEvent:
    """Record of a degraded mode trigger."""
    run_id: str
    timestamp: str
    trigger_condition: TriggerCondition
    details: str
    recovered: bool = False
    recovery_timestamp: Optional[str] = None


class DegradedModeController:
    """
    Controls DEGRADED_MODE transitions and recovery.
    
    CRITICAL: This is a safety mechanism. When in DEGRADED_MODE:
    - No writes to immutable stores
    - Analysis continues (for operator review)
    - Alert sent to operator
    """
    
    def __init__(self, config_path: Optional[Path] = None, alert_log_path: Optional[Path] = None):
        self.config_path = config_path or Path('config/degraded_mode_policy.json')
        self.alert_log_path = alert_log_path or Path('data/alerts/degraded_mode.log')
        self.current_state = SystemState.NORMAL
        self.active_event: Optional[DegradedModeEvent] = None
        self.policy: dict = {}
        
        self._load_policy()
    
    def _load_policy(self):
        """Load degraded mode policy."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self.policy = json.load(f)
    
    def check_condition(self, condition: TriggerCondition) -> str:
        """
        Check if a condition should trigger state change.
        
        Returns: 'ENTER_DEGRADED', 'HALT', or 'NONE'
        """
        conditions = self.policy.get('trigger_conditions', {}).get('conditions', [])
        
        for cond in conditions:
            if cond['id'] == condition.value:
                return cond.get('action', 'NONE')
        
        return 'NONE'
    
    def enter_degraded_mode(
        self, 
        run_id: str, 
        run_ts: str, 
        condition: TriggerCondition,
        details: str = ""
    ) -> SystemState:
        """
        Enter DEGRADED_MODE.
        
        Args:
            run_id: Current run ID
            run_ts: Run timestamp
            condition: What triggered the transition
            details: Additional context
        
        Returns:
            New system state
        """
        # Check policy action
        action = self.check_condition(condition)
        
        if action == 'HALT':
            self.current_state = SystemState.HALTED
        else:
            self.current_state = SystemState.DEGRADED_MODE
        
        # Record event
        self.active_event = DegradedModeEvent(
            run_id=run_id,
            timestamp=run_ts,
            trigger_condition=condition,
            details=details
        )
        
        # Send alert
        self._send_alert(run_id, run_ts, condition, details)
        
        return self.current_state
    
    def _send_alert(self, run_id: str, run_ts: str, condition: TriggerCondition, details: str):
        """Send operator alert."""
        alerts_config = self.policy.get('alerts', {})
        
        # Format message
        message_template = alerts_config.get(
            'message_template',
            "DTL {state}: {trigger_condition} at {timestamp}. Run ID: {run_id}"
        )
        
        message = message_template.format(
            state=self.current_state.value,
            trigger_condition=condition.value,
            timestamp=run_ts,
            run_id=run_id
        )
        
        # Log to file
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.alert_log_path, 'a') as f:
            log_entry = {
                'timestamp': run_ts,
                'state': self.current_state.value,
                'run_id': run_id,
                'condition': condition.value,
                'details': details,
                'message': message
            }
            f.write(json.dumps(log_entry) + '\n')
        
        # Console output
        if 'console' in alerts_config.get('channels', []):
            print(f"\n⚠️  ALERT: {message}\n")
    
    def can_write(self) -> bool:
        """Check if writes are allowed in current state."""
        if self.current_state == SystemState.NORMAL:
            return True
        
        degraded_behavior = self.policy.get('degraded_behavior', {})
        return not degraded_behavior.get('writes_blocked', True)
    
    def can_analyze(self) -> bool:
        """Check if analysis is allowed in current state."""
        if self.current_state == SystemState.HALTED:
            return False
        
        degraded_behavior = self.policy.get('degraded_behavior', {})
        return degraded_behavior.get('analysis_allowed', True)
    
    def recover(self, run_id: str, operator_ack: bool = False) -> bool:
        """
        Attempt to recover from DEGRADED_MODE.
        
        Args:
            run_id: Run ID requesting recovery
            operator_ack: Whether operator has acknowledged
        
        Returns:
            True if recovery successful
        """
        recovery_config = self.policy.get('recovery', {})
        
        # Check if auto-recovery is allowed
        if recovery_config.get('auto_recovery', False):
            self.current_state = SystemState.NORMAL
            if self.active_event:
                self.active_event.recovered = True
                self.active_event.recovery_timestamp = datetime.now(timezone.utc).isoformat()
            return True
        
        # Require operator acknowledgment
        if not operator_ack:
            return False
        
        self.current_state = SystemState.NORMAL
        if self.active_event:
            self.active_event.recovered = True
            self.active_event.recovery_timestamp = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def get_status(self) -> dict:
        """Get current status."""
        return {
            'state': self.current_state.value,
            'can_write': self.can_write(),
            'can_analyze': self.can_analyze(),
            'active_event': self.active_event.__dict__ if self.active_event else None
        }
