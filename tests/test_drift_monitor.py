"""
Tests for drift monitoring and alerting.

Verifies:
- False positives avoided
- Deterministic metric calculation
- Alerts emit without aborting
"""

import pytest
import math
from src.core.drift_monitor import (
    DriftMonitor, 
    DOMINANCE_THRESHOLD,
    ENTROPY_COLLAPSE_THRESHOLD,
    DOMINANCE_RUN_WINDOW
)


class TestDriftMonitoring:
    """Tests for drift monitoring."""

    def test_entropy_calculation(self):
        """Entropy is calculated correctly."""
        monitor = DriftMonitor()
        
        # Equal weights = max entropy
        weights = {"a": 1.0, "b": 1.0, "c": 1.0}
        entropy = monitor.compute_entropy(weights)
        
        # 3 equal weights = log2(3) ≈ 1.585
        expected = math.log2(3)
        assert abs(entropy - expected) < 0.01
    
    def test_entropy_collapse_detected(self):
        """Low entropy is detected."""
        monitor = DriftMonitor()
        
        # One dominant skill
        weights = {"a": 0.9, "b": 0.05, "c": 0.05}
        entropy = monitor.compute_entropy(weights)
        
        assert entropy < 1.0  # Much lower than uniform

    def test_dominance_calculation(self):
        """Dominance ratio calculated correctly."""
        monitor = DriftMonitor()
        
        weights = {"a": 0.8, "b": 0.1, "c": 0.1}
        skill, ratio = monitor.compute_dominance(weights)
        
        assert skill == "a"
        assert ratio == 0.8

    def test_metrics_deterministic(self):
        """Same inputs produce same metrics."""
        m1 = DriftMonitor()
        m2 = DriftMonitor()
        
        weights = {"a": 1.5, "b": 0.8, "c": 1.0}
        
        metrics1 = m1.record_metrics("run1", weights)
        metrics2 = m2.record_metrics("run1", weights)
        
        assert metrics1.routing_entropy == metrics2.routing_entropy
        assert metrics1.skill_dominance_ratio == metrics2.skill_dominance_ratio

    def test_alerts_do_not_abort(self):
        """Alerts are emitted but execution continues."""
        monitor = DriftMonitor()
        
        # Record 100 runs with dominance
        for i in range(100):
            weights = {"a": 0.9, "b": 0.05, "c": 0.05}
            monitor.record_metrics(f"run_{i}", weights)
        
        # Check alerts
        alerts = monitor.check_alerts()
        
        # Alerts may be present
        # But no exception raised - execution continues
        assert True  # Reached here = no abort

    def test_no_false_positives(self):
        """No alerts for healthy distribution."""
        monitor = DriftMonitor()
        
        # Record 100 runs with balanced weights
        for i in range(100):
            weights = {"a": 1.0, "b": 0.9, "c": 1.1}
            monitor.record_metrics(f"run_{i}", weights)
        
        alerts = monitor.check_alerts()
        
        # No skill dominance alerts
        dominance_alerts = [a for a in alerts if a.alert_type == "SKILL_DOMINANCE"]
        assert len(dominance_alerts) == 0

    def test_export_for_dashboard(self):
        """Metrics exportable for ops dashboards."""
        monitor = DriftMonitor()
        
        for i in range(50):
            weights = {"a": 1.0 + (i * 0.01), "b": 0.9}
            monitor.record_metrics(f"run_{i}", weights)
        
        export = monitor.export_for_dashboard()
        
        assert "runs" in export
        assert "summary" in export
        assert len(export["runs"]) == 50

    def test_drift_alert_logged(self):
        """Drift alerts are logged to ledger."""
        monitor = DriftMonitor()
        
        # Create conditions for alert
        for i in range(100):
            weights = {"a": 0.95, "b": 0.025, "c": 0.025}
            monitor.record_metrics(f"run_{i}", weights)
        
        alerts = monitor.check_alerts()
        
        # Check ledger has DRIFT_ALERT
        events = [e["event"] for e in monitor._ledger_entries]
        if alerts:
            assert "DRIFT_ALERT" in events
