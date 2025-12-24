"""
Capability Map Tests (DTL-SKILL-CAPMAP v1).
"""

import pytest
import json


class TestDeterministicOrdering:
    """Tests for deterministic ordering."""

    def test_json_deterministic(self):
        """JSON output should be deterministic."""
        from src.core.capability_map import CapabilityMapExport
        
        skills = {
            "z_skill": {"description": "Last", "dependencies": [], "failure_paths": []},
            "a_skill": {"description": "First", "dependencies": [], "failure_paths": []},
        }
        agents = {"agent_a": {"cap_z": True, "cap_a": True}}
        
        export1 = CapabilityMapExport()
        export1.build_graph(skills, agents, ["DTL-001", "DTL-002"])
        json1 = export1.to_json()
        
        export2 = CapabilityMapExport()
        export2.build_graph(skills, agents, ["DTL-001", "DTL-002"])
        json2 = export2.to_json()
        
        # Should be identical
        assert json1 == json2


class TestGraphContents:
    """Tests for graph contents."""

    def test_skills_included(self):
        """All skills should be included."""
        from src.core.capability_map import CapabilityMapExport
        
        skills = {
            "skill_a": {"description": "A", "dependencies": [], "failure_paths": []},
            "skill_b": {"description": "B", "dependencies": ["skill_a"], "failure_paths": []},
        }
        
        export = CapabilityMapExport()
        export.build_graph(skills, {}, [])
        
        skill_names = export.get_skills()
        assert "skill_a" in skill_names
        assert "skill_b" in skill_names

    def test_agents_included(self):
        """Agent capabilities should be included."""
        from src.core.capability_map import CapabilityMapExport
        
        agents = {
            "executor": {"read_evidence": True, "write_evidence": True}
        }
        
        export = CapabilityMapExport()
        export.build_graph({}, agents, [])
        
        caps = export.get_agent_capabilities("executor")
        assert "read_evidence" in caps
        assert "write_evidence" in caps


class TestBuiltInCapabilityMap:
    """Tests for built-in capability map."""

    def test_build_from_system(self):
        """Should build from actual system state."""
        from src.core.capability_map import build_capability_map
        
        export = build_capability_map()
        
        skills = export.get_skills()
        assert len(skills) >= 5  # Should have autonomy skills
        
        json_output = export.to_json()
        data = json.loads(json_output)
        
        assert "version" in data
        assert "skills" in data
        assert "agents" in data
        assert "failure_codes" in data
