"""
Reporter Agent Implementation for DTL v2.0

Output synthesis and commit coordination agent.
Implements the interface from reporter.skill.md.
"""

from typing import Optional
from .base import BaseAgent, ProposalEnvelope


class ReporterAgent(BaseAgent):
    """
    Reporter agent for output synthesis and persistence.
    
    Capabilities (from reporter.skill.md):
    - read_evidence_queue
    - build_commit_bundle
    - create_prewrite
    - write_evidence_store
    - write_report
    """
    
    SKILL_FILE = "reporter.skill.md"
    
    def __init__(self, run_id: str, run_ts: str, commit_gate=None, evidence_queue=None, firewall=None, runner_capabilities=None):
        super().__init__(run_id, run_ts, firewall=firewall, runner_capabilities=runner_capabilities)
        self.commit_gate = commit_gate
        self.evidence_queue = evidence_queue
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Build commit bundle and coordinate persistence.
        
        Args:
            input_data: {
                'analysis': dict,
                'summary': str,
                'plan_id': str
            }
        
        Returns:
            ProposalEnvelope with commit bundle and report
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.control_plane.commit_gate import CommitBundle
        
        capability_claims = ['build_commit_bundle']
        
        # Pull evidence from queue
        evidence_refs = []
        evidence_data = []
        if self.evidence_queue:
            capability_claims.append('read_evidence_queue')
            candidates = self.evidence_queue.dequeue_all()
            evidence_refs = [c.evidence_id for c in candidates]
            evidence_data = [c.to_dict() for c in candidates]
        
        # Build analysis payload
        analysis = input_data.get('analysis', {})
        if not analysis:
            analysis = {
                'plan_id': input_data.get('plan_id', 'UNKNOWN'),
                'evidence_count': len(evidence_refs),
                'analysis_timestamp': self.run_ts  # Use run_ts for determinism
            }
        
        # Build commit bundle
        bundle = CommitBundle(
            run_id=self.run_id,
            agent_id=self.agent_id,
            schema_version='2.0.0',
            timestamp=self.run_ts,  # Use run_ts for determinism
            content_hash='placeholder',
            payload=analysis,
            evidence_refs=evidence_refs,
            capability_claims=['write_evidence_store', 'write_report']
        )
        bundle.content_hash = bundle.compute_hash()
        
        # Build report
        report = {
            'summary': input_data.get('summary', f'Analysis of {len(evidence_refs)} evidence items'),
            'confidence_level': self._compute_confidence(evidence_data),
            'analysis_items': [
                {
                    'asset': ref.split('-')[0] if '-' in ref else 'N/A',
                    'evidence_id': ref
                }
                for ref in evidence_refs[:10]  # Limit for report
            ]
        }
        
        # Add write capabilities
        capability_claims.extend(['write_evidence_store', 'write_report'])
        
        payload = {
            'commit_bundle': bundle.to_dict(),
            'report': report,
            'prewrite_required': True
        }
        
        return self.wrap_output(payload, capability_claims=capability_claims)
    
    def _compute_confidence(self, evidence_data: list) -> str:
        """
        Compute confidence level based on evidence quality.
        """
        if not evidence_data:
            return 'low'
        
        # Average trust tier (1 = best, 4 = worst)
        avg_tier = sum(e.get('source_trust_tier', 3) for e in evidence_data) / len(evidence_data)
        
        if avg_tier <= 1.5:
            return 'high'
        elif avg_tier <= 2.5:
            return 'medium'
        else:
            return 'low'
    
    def execute_commit_protocol(self, bundle) -> dict:
        """
        Execute the full commit protocol.
        
        1. Create prewrite
        2. Validate via CommitGate
        3. On success, promote and write
        4. On failure, log and return error
        """
        if not self.commit_gate:
            return {'success': False, 'error': 'No CommitGate configured'}
        
        # Step 1: Create prewrite
        prewrite_path = self.commit_gate.create_prewrite(bundle)
        
        # Step 2: Validate
        result = self.commit_gate.validate(bundle)
        
        if result.status.value == 'ACCEPTED':
            # Step 3: Promote
            promote_result = self.commit_gate.promote_to_committed(bundle)
            return {
                'success': promote_result.success,
                'committed_path': str(promote_result.path) if promote_result.path else None
            }
        else:
            return {
                'success': False,
                'rejection_code': result.rejection.code if result.rejection else 'UNKNOWN',
                'rejection_details': result.rejection.details if result.rejection else None
            }
