"""
Strategist Agent Implementation for DTL v2.0

Strategic planning and asset selection agent.
Implements the interface from strategist.skill.md.
"""

from typing import Optional
from .base import BaseAgent, ProposalEnvelope, generate_plan_id


class StrategistAgent(BaseAgent):
    """
    Strategist agent for planning and asset selection.
    
    Capabilities (from strategist.skill.md):
    - read_market_data
    - read_evidence
    - propose_plan
    - select_assets
    - read_routing_stats
    """
    
    SKILL_FILE = "strategist.skill.md"
    
    def __init__(self, run_id: str, run_ts: str, routing_stats=None, firewall=None, runner_capabilities=None):
        # P1 Fix #6: Runner decides if routing_stats capability is granted
        caps = runner_capabilities or []
        if routing_stats and 'read_routing_stats' not in caps:
            caps = caps + ['read_routing_stats']
        
        super().__init__(run_id, run_ts, firewall=firewall, runner_capabilities=caps)
        self.routing_stats = routing_stats
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Create a research plan based on market context.
        
        Args:
            input_data: {
                'market_context': {
                    'date': str,
                    'market_status': str,
                    'available_assets': list[str]
                }
            }
        
        Returns:
            ProposalEnvelope with plan payload
        """
        market_context = input_data.get('market_context', {})
        available_assets = market_context.get('available_assets', ['XAU', 'GME'])
        market_status = market_context.get('market_status', 'pre_market')
        
        # P0 Fix #2: Deterministic plan_id using run_ts
        plan_id = generate_plan_id(self.run_id, self.agent_id, self.run_ts)
        
        # Select assets (max 10 per manifest constraint)
        selected_assets = available_assets[:10]
        
        # Build evidence requests based on market status
        evidence_requests = []
        if market_status == 'pre_market':
            evidence_requests = [
                {'query_type': 'price', 'max_sources': 3},
                {'query_type': 'news', 'max_sources': 3},
                {'query_type': 'catalyst', 'max_sources': 2},
            ]
        elif market_status == 'open':
            evidence_requests = [
                {'query_type': 'price', 'max_sources': 5},
                {'query_type': 'technical', 'max_sources': 2},
            ]
        else:  # closed
            evidence_requests = [
                {'query_type': 'news', 'max_sources': 2},
            ]
        
        # Determine priority
        priority = 'normal'
        if market_status == 'pre_market':
            priority = 'high'
        elif market_status == 'closed':
            priority = 'low'
        
        payload = {
            'plan_id': plan_id,
            'asset_universe': selected_assets,
            'evidence_requests': evidence_requests,
            'priority': priority
        }
        
        # Declare capability claims based on actual usage
        capability_claims = ['read_market_data', 'propose_plan', 'select_assets']
        if self.routing_stats:
            capability_claims.append('read_routing_stats')
        
        return self.wrap_output(payload, capability_claims=capability_claims)
    
    def select_assets(self, available: list[str], criteria: Optional[dict] = None) -> list[str]:
        """
        Select assets based on criteria.
        
        Default: return all available up to limit.
        """
        limit = criteria.get('limit', 10) if criteria else 10
        return available[:limit]
