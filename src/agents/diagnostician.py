"""
Diagnostician Agent Implementation for DTL v2.0

System health monitoring and self-improvement analysis agent.
Implements the interface from diagnostician.skill.md.

Note: This replaces RealityCheck with explicit read-only permissions.
"""

from pathlib import Path
from typing import Optional
import json
from .base import BaseAgent, ProposalEnvelope


class DiagnosticianAgent(BaseAgent):
    """
    Diagnostician agent for system health monitoring.
    
    Capabilities (from diagnostician.skill.md):
    - read_run_ledger
    - read_system_state
    - read_routing_stats
    - read_evidence_store
    - generate_diagnostics
    - propose_improvements (advisory only)
    """
    
    SKILL_FILE = "diagnostician.skill.md"
    
    def __init__(self, run_id: str, run_ts: str, run_ledger_path: Optional[str] = None, routing_stats=None, firewall=None, runner_capabilities=None):
        # P1 Fix #6: Runner decides if routing_stats capability is granted
        caps = runner_capabilities or []
        if routing_stats and 'read_routing_stats' not in caps:
            caps = caps + ['read_routing_stats']
        
        super().__init__(run_id, run_ts, firewall=firewall, runner_capabilities=caps)
        self.run_ledger_path = Path(run_ledger_path) if run_ledger_path else Path('data/dtl_runs')
        self.routing_stats = routing_stats
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Generate diagnostic report.
        
        Args:
            input_data: {
                'analysis_window': {
                    'start_date': str,
                    'end_date': str,
                    'run_ids': list[str]
                },
                'focus_areas': list[str]
            }
        
        Returns:
            ProposalEnvelope with diagnostic report
        """
        focus_areas = input_data.get('focus_areas', ['performance'])
        analysis_window = input_data.get('analysis_window', {})
        
        capability_claims = ['generate_diagnostics']
        
        # Collect metrics (uses read capabilities)
        metrics = self._collect_metrics(analysis_window)
        capability_claims.extend(['read_run_ledger', 'read_system_state'])
        
        if self.routing_stats:
            capability_claims.append('read_routing_stats')
        
        # Detect issues
        issues = self._detect_issues(metrics, focus_areas)
        
        # Generate suggestions (advisory only)
        suggestions = self._generate_suggestions(issues)
        if suggestions:
            capability_claims.append('propose_improvements')
        
        # Determine overall health
        health = self._assess_health(metrics, issues)
        
        # Use run_ts for deterministic report_id
        import hashlib
        report_hash = hashlib.sha256(f"{self.run_id}:{self.run_ts}".encode()).hexdigest()[:8].upper()
        
        payload = {
            'diagnostic_report': {
                'report_id': f"DIAG-{report_hash}",
                'generated_at': self.run_ts,  # Deterministic
                'system_health': health,
                'metrics': metrics,
                'issues_detected': issues,
                'improvement_suggestions': suggestions
            }
        }
        
        return self.wrap_output(payload, capability_claims=capability_claims)
    
    def _collect_metrics(self, analysis_window: dict) -> dict:
        """
        Collect metrics from run ledger and routing stats.
        """
        metrics = {
            'total_runs': 0,
            'success_rate': 0.0,
            'avg_latency_ms': 0,
            'evidence_quality_score': 0.0,
            'rejection_count': 0
        }
        
        # Read run ledger files
        if self.run_ledger_path.exists():
            run_files = list(self.run_ledger_path.glob('*.json'))
            metrics['total_runs'] = len(run_files)
            
            successes = 0
            total_latency = 0
            
            for run_file in run_files[-100:]:  # Last 100 runs
                try:
                    with open(run_file) as f:
                        run_data = json.load(f)
                    if run_data.get('success', False):
                        successes += 1
                    # Add latency if available
                    if 'latency_ms' in run_data:
                        total_latency += run_data['latency_ms']
                except (json.JSONDecodeError, IOError):
                    pass
            
            if metrics['total_runs'] > 0:
                metrics['success_rate'] = successes / min(metrics['total_runs'], 100)
                metrics['avg_latency_ms'] = total_latency // max(1, successes)
        
        # Read routing stats if available
        if self.routing_stats:
            entries = self.routing_stats.get_all()
            if entries:
                avg_success = sum(e.success_rate_30d for e in entries) / len(entries)
                avg_latency = sum(e.avg_latency_ms for e in entries) / len(entries)
                metrics['avg_latency_ms'] = int(avg_latency)
                metrics['success_rate'] = avg_success
        
        return metrics
    
    def _detect_issues(self, metrics: dict, focus_areas: list[str]) -> list[dict]:
        """
        Detect issues based on metrics and focus areas.
        """
        issues = []
        
        # Performance issues
        if 'performance' in focus_areas:
            if metrics['success_rate'] < 0.95:
                issues.append({
                    'issue_id': 'PERF-001',
                    'severity': 'high' if metrics['success_rate'] < 0.8 else 'medium',
                    'description': f"Success rate below target: {metrics['success_rate']:.1%}"
                })
        
        # Latency issues
        if 'latency' in focus_areas:
            if metrics['avg_latency_ms'] > 5000:
                issues.append({
                    'issue_id': 'LAT-001',
                    'severity': 'medium',
                    'description': f"High average latency: {metrics['avg_latency_ms']}ms"
                })
        
        # Evidence quality
        if 'evidence_quality' in focus_areas:
            if metrics['evidence_quality_score'] < 0.7:
                issues.append({
                    'issue_id': 'EVID-001',
                    'severity': 'low',
                    'description': f"Low evidence quality score: {metrics['evidence_quality_score']:.2f}"
                })
        
        return issues
    
    def _generate_suggestions(self, issues: list[dict]) -> list[dict]:
        """
        Generate improvement suggestions based on detected issues.
        
        Note: These are advisory only - no direct action.
        """
        suggestions = []
        
        for issue in issues:
            if issue['issue_id'].startswith('PERF'):
                suggestions.append({
                    'suggestion_id': f"SUG-{issue['issue_id']}",
                    'category': 'performance',
                    'description': 'Review evidence source reliability and API timeouts',
                    'estimated_impact': 'medium'
                })
            elif issue['issue_id'].startswith('LAT'):
                suggestions.append({
                    'suggestion_id': f"SUG-{issue['issue_id']}",
                    'category': 'latency',
                    'description': 'Consider reducing max_sources per request or parallelizing fetches',
                    'estimated_impact': 'high'
                })
            elif issue['issue_id'].startswith('EVID'):
                suggestions.append({
                    'suggestion_id': f"SUG-{issue['issue_id']}",
                    'category': 'evidence',
                    'description': 'Prioritize Tier 1 sources and add source validation',
                    'estimated_impact': 'medium'
                })
        
        return suggestions
    
    def _assess_health(self, metrics: dict, issues: list[dict]) -> str:
        """
        Assess overall system health.
        """
        critical_issues = [i for i in issues if i['severity'] == 'critical']
        high_issues = [i for i in issues if i['severity'] == 'high']
        
        if critical_issues:
            return 'critical'
        elif high_issues:
            return 'degraded'
        elif len(issues) > 3:
            return 'degraded'
        else:
            return 'healthy'
