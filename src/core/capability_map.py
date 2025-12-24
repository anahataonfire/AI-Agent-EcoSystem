"""
Capability Map Export (DTL-SKILL-CAPMAP v1).

Export a machine-readable capability graph.
Deterministic ordering. Used by external auditors.
"""

import json
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class SkillCapability:
    """A skill capability entry."""
    skill_name: str
    description: str
    dependencies: List[str]
    failure_paths: List[str]
    enabled: bool = True


@dataclass
class CapabilityGraph:
    """The full capability graph."""
    version: str
    skills: List[SkillCapability]
    agents: Dict[str, List[str]]  # agent -> capabilities
    failure_codes: List[str]


class CapabilityMapExport:
    """
    Export capability graph as JSON.
    
    Deterministic ordering. Read-only.
    """
    
    VERSION = "1.0.0"
    
    def __init__(self):
        self._graph: Optional[CapabilityGraph] = None
    
    def build_graph(
        self,
        skills: Dict[str, dict],
        agent_manifests: Dict[str, dict],
        failure_codes: List[str],
    ) -> CapabilityGraph:
        """
        Build capability graph from components.
        """
        skill_list = []
        
        for name, info in sorted(skills.items()):
            skill_list.append(SkillCapability(
                skill_name=name,
                description=info.get("description", ""),
                dependencies=sorted(info.get("dependencies", [])),
                failure_paths=sorted(info.get("failure_paths", [])),
                enabled=info.get("enabled", True),
            ))
        
        agents = {}
        for agent_name, manifest in sorted(agent_manifests.items()):
            caps = []
            for cap, value in sorted(manifest.items()):
                if value is True:
                    caps.append(cap)
                elif isinstance(value, list):
                    caps.append(f"{cap}:{','.join(sorted(value))}")
            agents[agent_name] = caps
        
        self._graph = CapabilityGraph(
            version=self.VERSION,
            skills=skill_list,
            agents=agents,
            failure_codes=sorted(failure_codes),
        )
        
        return self._graph
    
    def to_json(self, indent: int = 2) -> str:
        """Export graph as JSON string."""
        if self._graph is None:
            raise ValueError("Graph not built. Call build_graph() first.")
        
        data = {
            "version": self._graph.version,
            "skills": [
                {
                    "skill_name": s.skill_name,
                    "description": s.description,
                    "dependencies": s.dependencies,
                    "failure_paths": s.failure_paths,
                    "enabled": s.enabled,
                }
                for s in self._graph.skills
            ],
            "agents": self._graph.agents,
            "failure_codes": self._graph.failure_codes,
        }
        
        return json.dumps(data, indent=indent, sort_keys=True)
    
    def save(self, path: str) -> str:
        """Save export to file."""
        if self._graph is None:
            raise ValueError("Graph not built. Call build_graph() first.")
        
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        
        return str(output_path)
    
    def get_skills(self) -> List[str]:
        """Get list of skill names."""
        if self._graph is None:
            return []
        return [s.skill_name for s in self._graph.skills]
    
    def get_agent_capabilities(self, agent_name: str) -> List[str]:
        """Get capabilities for an agent."""
        if self._graph is None:
            return []
        return self._graph.agents.get(agent_name, [])


def build_capability_map() -> CapabilityMapExport:
    """
    Build capability map from current system state.
    """
    from src.agents.manifest import AGENT_MANIFESTS
    from src.core.failures import get_all_codes
    
    export = CapabilityMapExport()
    
    # Define skills
    skills = {
        "retry_strategy": {
            "description": "Bounded retry with cost caps",
            "dependencies": ["failure_attribution"],
            "failure_paths": ["DTL-AGENT-001"],
        },
        "failure_attribution": {
            "description": "Root cause classification",
            "dependencies": [],
            "failure_paths": ["DTL-FAILATTR-002"],
        },
        "context_budget": {
            "description": "Token budget management",
            "dependencies": [],
            "failure_paths": [],
        },
        "skill_scoring": {
            "description": "Performance tracking",
            "dependencies": [],
            "failure_paths": [],
        },
        "plan_validation": {
            "description": "Task decomposition validation",
            "dependencies": [],
            "failure_paths": ["DTL-PLAN-003"],
        },
        "adaptation": {
            "description": "Mid-run recovery",
            "dependencies": ["failure_attribution"],
            "failure_paths": ["DTL-ADAPT-001"],
        },
        "evals": {
            "description": "Verification pipeline",
            "dependencies": [],
            "failure_paths": [],
        },
        "state_memory": {
            "description": "Decaying state memory",
            "dependencies": [],
            "failure_paths": [],
        },
        "proactive": {
            "description": "Proactive decision triggering",
            "dependencies": ["run_ledger"],
            "failure_paths": [],
        },
        "self_improve": {
            "description": "Closed-loop improvement",
            "dependencies": ["skill_scoring", "failure_attribution", "evals"],
            "failure_paths": [],
        },
    }
    
    # Get failure codes
    codes = list(get_all_codes().keys())
    
    export.build_graph(skills, AGENT_MANIFESTS, codes)
    
    return export
