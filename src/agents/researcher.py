"""
Researcher Agent Implementation for DTL v2.0

Evidence gathering agent.
Implements the interface from researcher.skill.md.
"""

from typing import Optional
from .base import BaseAgent, ProposalEnvelope


class ResearcherAgent(BaseAgent):
    """
    Researcher agent for evidence gathering.
    
    Capabilities (from researcher.skill.md):
    - fetch_market_data
    - fetch_news
    - fetch_sentiment
    - enqueue_evidence
    - compute_hash
    """
    
    SKILL_FILE = "researcher.skill.md"
    
    def __init__(self, run_id: str, run_ts: str, evidence_queue=None, firewall=None, runner_capabilities=None):
        super().__init__(run_id, run_ts, firewall=firewall, runner_capabilities=runner_capabilities)
        self.evidence_queue = evidence_queue
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Gather evidence based on strategist plan.
        
        Args:
            input_data: {
                'plan': {
                    'plan_id': str,
                    'asset_universe': list[str],
                    'evidence_requests': list[dict]
                }
            }
        
        Returns:
            ProposalEnvelope with evidence candidates
        """
        # Import here to avoid circular dependency
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.control_plane.evidence_queue import EvidenceCandidate
        
        plan = input_data.get('plan', {})
        asset_universe = plan.get('asset_universe', [])
        evidence_requests = plan.get('evidence_requests', [])
        
        evidence_candidates = []
        capability_claims = []
        
        # Process each evidence request for each asset
        for asset in asset_universe:
            for request in evidence_requests:
                query_type = request.get('query_type', 'price')
                max_sources = request.get('max_sources', 3)
                
                # Track capabilities used
                if query_type == 'price' and 'fetch_market_data' not in capability_claims:
                    capability_claims.append('fetch_market_data')
                elif query_type == 'news' and 'fetch_news' not in capability_claims:
                    capability_claims.append('fetch_news')
                elif query_type == 'sentiment' and 'fetch_sentiment' not in capability_claims:
                    capability_claims.append('fetch_sentiment')
                
                # Generate mock evidence (real implementation would fetch from APIs)
                for i in range(min(max_sources, 2)):  # Limit for mock
                    candidate = self._fetch_evidence(asset, query_type, i)
                    evidence_candidates.append(candidate.to_dict())
                    
                    # Enqueue if queue provided
                    if self.evidence_queue:
                        self.evidence_queue.enqueue(candidate)
                        if 'enqueue_evidence' not in capability_claims:
                            capability_claims.append('enqueue_evidence')
        
        # Always add compute_hash as we compute content hashes
        capability_claims.append('compute_hash')
        
        payload = {
            'evidence_candidates': evidence_candidates,
            'plan_id': plan.get('plan_id', 'UNKNOWN')
        }
        
        return self.wrap_output(payload, capability_claims=capability_claims)
    
    def _fetch_evidence(self, asset: str, query_type: str, source_idx: int):
        """
        Fetch evidence from external source.
        
        This is a mock implementation. Real implementation would:
        1. Call appropriate API based on query_type
        2. Compute content hash
        3. Assign trust tier based on source
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.control_plane.evidence_queue import EvidenceCandidate
        
        # Mock source URLs by type
        source_urls = {
            'price': f'https://api.alpaca.markets/v2/stocks/{asset}/trades',
            'news': f'https://api.polygon.io/v2/reference/news?ticker={asset}',
            'sentiment': f'https://api.socialsentiment.io/v1/{asset}',
            'catalyst': f'https://api.earningswhispers.com/v1/{asset}',
            'technical': f'https://api.tradingview.com/indicators/{asset}',
        }
        
        # Trust tiers by source type
        trust_tiers = {
            'price': 1,  # Official API
            'news': 2,   # Major sources
            'sentiment': 3,
            'catalyst': 3,
            'technical': 2,
        }
        
        # Use run_ts for deterministic evidence ID (not datetime.now())
        import hashlib
        seed = f"{self.run_id}:{self.run_ts}:{asset}:{query_type}:{source_idx}"
        hash_part = hashlib.sha256(seed.encode()).hexdigest()[:12].upper()
        evidence_id = f"EV-{hash_part}"
        
        return EvidenceCandidate(
            evidence_id=evidence_id,
            source_url=source_urls.get(query_type, f'https://api.example.com/{asset}'),
            source_trust_tier=trust_tiers.get(query_type, 3),
            fetched_at=self.run_ts,  # Use run_ts for determinism
            summary=f'{query_type.title()} data for {asset} from source {source_idx + 1}',
            relevance_score=0.8 - (source_idx * 0.1),
            asset_tags=[asset]
        )
