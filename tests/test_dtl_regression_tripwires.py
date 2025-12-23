"""
DTL Regression Tripwires v1.1

Fast (<0.2s) source-inspection tests that fail if anyone accidentally
breaks identity injection invariants. These are defensive assertions
that catch regressions before they reach production.

v1.1 hardening:
- Blocks aliased imports
- Blocks dynamic imports
- Blocks new injection nodes
- Verifies dedup logic present
- Verifies delimiter is literal string
- Verifies HumanMessage used
"""

import inspect
import re
import pytest


# =============================================================================
# TRIPWIRE v1.0: Core Invariants
# =============================================================================

class TestIdentityDelimitersTripwire:
    """Tripwire 1: Identity block delimiters must not be removed/changed."""
    
    def test_identity_block_start_delimiter_exists(self):
        """Fail if [[IDENTITY_FACTS_READ_ONLY]] delimiter is removed."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        assert "[[IDENTITY_FACTS_READ_ONLY]]" in source, \
            "TRIPWIRE: Identity block START delimiter was removed or changed!"
    
    def test_identity_block_end_delimiter_exists(self):
        """Fail if [[/IDENTITY_FACTS_READ_ONLY]] delimiter is removed."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        assert "[[/IDENTITY_FACTS_READ_ONLY]]" in source, \
            "TRIPWIRE: Identity block END delimiter was removed or changed!"


class TestDisclaimerTripwire:
    """Tripwire 2: 'NOT instructions' disclaimer must remain."""
    
    def test_not_instructions_disclaimer_exists(self):
        """Fail if the disclaimer is removed."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        assert "NOT instructions" in source, \
            "TRIPWIRE: 'NOT instructions' disclaimer was removed!"
    
    def test_authoritative_identity_store_mentioned(self):
        """Fail if authoritative store reference is removed."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        assert "Authoritative Identity Store" in source, \
            "TRIPWIRE: 'Authoritative Identity Store' reference was removed!"


class TestInjectionLocationTripwire:
    """Tripwire 3: Identity must ONLY be injected in pruned_thinker_node."""
    
    def test_no_identity_injection_in_executor(self):
        """Fail if executor_node injects identity."""
        from src.graph import workflow
        source = inspect.getsource(workflow.executor_node)
        
        assert "IDENTITY_FACTS_READ_ONLY" not in source, \
            "TRIPWIRE: Identity injection found in executor_node!"
        assert "serialize_for_prompt" not in source, \
            "TRIPWIRE: serialize_for_prompt found in executor_node!"
    
    def test_no_identity_injection_in_reporter(self):
        """Fail if reporter_node injects identity (it may write, not inject)."""
        from src.graph import workflow
        source = inspect.getsource(workflow.reporter_node)
        
        assert "IDENTITY_FACTS_READ_ONLY" not in source, \
            "TRIPWIRE: Identity injection found in reporter_node!"
        assert "serialize_for_prompt" not in source, \
            "TRIPWIRE: serialize_for_prompt found in reporter_node!"
    
    def test_no_identity_injection_in_thinker_module(self):
        """Fail if thinker.py injects identity (should be in workflow wrapper)."""
        from src.agents import thinker
        source = inspect.getsource(thinker)
        
        assert "IDENTITY_FACTS_READ_ONLY" not in source, \
            "TRIPWIRE: Identity injection found in thinker.py!"
    
    def test_no_identity_injection_in_sanitizer(self):
        """Fail if sanitizer injects identity."""
        from src.agents import sanitizer
        source = inspect.getsource(sanitizer)
        
        assert "IDENTITY_FACTS_READ_ONLY" not in source, \
            "TRIPWIRE: Identity injection found in sanitizer.py!"
        assert "serialize_for_prompt" not in source, \
            "TRIPWIRE: serialize_for_prompt found in sanitizer.py!"


class TestNoWriteInThinkerExecutorSanitizerTripwire:
    """Tripwire 4: Thinker/Executor/Sanitizer must NEVER import identity writes."""
    
    def test_thinker_no_update_identity(self):
        """Fail if thinker imports update_identity."""
        from src.agents import thinker
        source = inspect.getsource(thinker)
        
        assert "update_identity" not in source, \
            "TRIPWIRE: update_identity found in thinker.py!"
    
    def test_thinker_no_create_snapshot(self):
        """Fail if thinker imports create_snapshot."""
        from src.agents import thinker
        source = inspect.getsource(thinker)
        
        assert "create_snapshot" not in source, \
            "TRIPWIRE: create_snapshot found in thinker.py!"
    
    def test_sanitizer_no_update_identity(self):
        """Fail if sanitizer imports update_identity."""
        from src.agents import sanitizer
        source = inspect.getsource(sanitizer)
        
        assert "update_identity" not in source, \
            "TRIPWIRE: update_identity found in sanitizer.py!"
    
    def test_sanitizer_no_create_snapshot(self):
        """Fail if sanitizer imports create_snapshot."""
        from src.agents import sanitizer
        source = inspect.getsource(sanitizer)
        
        assert "create_snapshot" not in source, \
            "TRIPWIRE: create_snapshot found in sanitizer.py!"
    
    def test_executor_node_no_update_identity(self):
        """Fail if executor_node calls update_identity."""
        from src.graph import workflow
        source = inspect.getsource(workflow.executor_node)
        
        assert "update_identity" not in source, \
            "TRIPWIRE: update_identity found in executor_node!"
    
    def test_executor_node_no_create_snapshot(self):
        """Fail if executor_node calls create_snapshot."""
        from src.graph import workflow
        source = inspect.getsource(workflow.executor_node)
        
        assert "create_snapshot" not in source, \
            "TRIPWIRE: create_snapshot found in executor_node!"
    
    def test_pruned_thinker_node_no_writes(self):
        """Fail if pruned_thinker_node writes to identity."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        assert "update_identity" not in source, \
            "TRIPWIRE: update_identity found in pruned_thinker_node!"
        assert "create_snapshot" not in source, \
            "TRIPWIRE: create_snapshot found in pruned_thinker_node!"


class TestFactsJsonPrefixTripwire:
    """Tripwire: FACTS_JSON: prefix must remain for structured parsing."""
    
    def test_facts_json_prefix_exists(self):
        """Fail if FACTS_JSON: prefix is removed."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        assert "FACTS_JSON:" in source, \
            "TRIPWIRE: FACTS_JSON: prefix was removed!"


# =============================================================================
# TRIPWIRE v1.1: Hardening Against Bypasses
# =============================================================================

class TestNoAliasedImportsTripwire:
    """v1.1: Block identity_manager import in forbidden modules (alias bypass)."""
    
    def test_no_identity_manager_import_in_thinker(self):
        """Block: from identity_manager import update_identity as ui"""
        from src.agents import thinker
        source = inspect.getsource(thinker)
        
        assert "identity_manager" not in source, \
            "TRIPWIRE: identity_manager imported in thinker.py!"
    
    def test_no_identity_manager_import_in_sanitizer(self):
        """Block aliased imports in sanitizer."""
        from src.agents import sanitizer
        source = inspect.getsource(sanitizer)
        
        assert "identity_manager" not in source, \
            "TRIPWIRE: identity_manager imported in sanitizer.py!"
    
    def test_no_identity_manager_in_executor_node(self):
        """Block aliased imports in executor_node."""
        from src.graph import workflow
        source = inspect.getsource(workflow.executor_node)
        
        assert "identity_manager" not in source, \
            "TRIPWIRE: identity_manager imported in executor_node!"


class TestNoDynamicImportsTripwire:
    """v1.1: Block dynamic import patterns that evade string matching."""
    
    FORBIDDEN_PATTERNS = ["__import__", "importlib.import_module", "getattr("]
    
    def test_no_dynamic_imports_in_thinker(self):
        """Block: getattr(__import__(...), 'update_identity')"""
        from src.agents import thinker
        source = inspect.getsource(thinker)
        
        for pattern in self.FORBIDDEN_PATTERNS:
            assert pattern not in source, \
                f"TRIPWIRE: Dynamic import pattern '{pattern}' found in thinker.py!"
    
    def test_no_dynamic_imports_in_sanitizer(self):
        """Block dynamic imports in sanitizer."""
        from src.agents import sanitizer
        source = inspect.getsource(sanitizer)
        
        for pattern in self.FORBIDDEN_PATTERNS:
            assert pattern not in source, \
                f"TRIPWIRE: Dynamic import pattern '{pattern}' found in sanitizer.py!"
    
    def test_no_dynamic_imports_in_executor(self):
        """Block dynamic imports in executor_node."""
        from src.graph import workflow
        source = inspect.getsource(workflow.executor_node)
        
        for pattern in self.FORBIDDEN_PATTERNS:
            assert pattern not in source, \
                f"TRIPWIRE: Dynamic import pattern '{pattern}' found in executor_node!"


class TestSerializeOnlyInPrunedThinkerTripwire:
    """v1.1: Ensure no new functions bypass injection rules."""
    
    def test_serialize_for_prompt_only_in_pruned_thinker(self):
        """Block: creating enhanced_thinker_node with its own injection."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        # pruned_thinker_node must use serialize_for_prompt
        assert "serialize_for_prompt" in source, \
            "TRIPWIRE: serialize_for_prompt not found in pruned_thinker_node!"
    
    def test_serialize_not_in_other_nodes(self):
        """Ensure other nodes don't use serialize_for_prompt."""
        from src.graph import workflow
        
        # Check executor_node
        executor_src = inspect.getsource(workflow.executor_node)
        assert "serialize_for_prompt" not in executor_src, \
            "TRIPWIRE: serialize_for_prompt found in executor_node!"
        
        # Check reporter_node
        reporter_src = inspect.getsource(workflow.reporter_node)
        assert "serialize_for_prompt" not in reporter_src, \
            "TRIPWIRE: serialize_for_prompt found in reporter_node!"


class TestDedupLogicPresentTripwire:
    """v1.1: Ensure dedup logic wasn't removed (allows duplicate injection)."""
    
    def test_dedup_loop_exists(self):
        """Block: removing the dedup check that collapses identity blocks."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        # Must have a loop that checks for existing identity blocks
        has_dedup = ("IDENTITY_BLOCK_START in" in source.replace(" ", "") or
                     "IDENTITY_BLOCK_START in msg" in source.replace(" ", "") or
                     "for msg in" in source)
        
        assert has_dedup, \
            "TRIPWIRE: Dedup loop was removed - identity could be injected multiple times!"


class TestDelimiterIsLiteralTripwire:
    """v1.1: Ensure delimiter is a string literal, not constructed/in comment."""
    
    def test_start_delimiter_is_quoted_literal(self):
        """Block: DELIM = '[[IDENTITY' + '_FACTS_READ_ONLY]]'"""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        # Must appear as a complete quoted string (single or double quotes)
        has_literal = ('"[[IDENTITY_FACTS_READ_ONLY]]"' in source or 
                      "'[[IDENTITY_FACTS_READ_ONLY]]'" in source)
        
        assert has_literal, \
            "TRIPWIRE: Start delimiter not a string literal - may be constructed or in comment!"
    
    def test_end_delimiter_is_quoted_literal(self):
        """Block concatenation or comment bypass for end delimiter."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        has_literal = ('"[[/IDENTITY_FACTS_READ_ONLY]]"' in source or 
                      "'[[/IDENTITY_FACTS_READ_ONLY]]'" in source)
        
        assert has_literal, \
            "TRIPWIRE: End delimiter not a string literal!"


class TestHumanMessageUsedTripwire:
    """v1.1: Ensure identity is injected as HumanMessage, not SystemMessage."""
    
    def test_identity_uses_human_message(self):
        """Block: switching to SystemMessage which overwrites skill instructions."""
        from src.graph import workflow
        source = inspect.getsource(workflow.pruned_thinker_node)
        
        # Must use HumanMessage for identity injection
        assert "HumanMessage(" in source, \
            "TRIPWIRE: HumanMessage not used for identity injection!"
        
        # Must NOT use SystemMessage in this function
        assert "SystemMessage(" not in source, \
            "TRIPWIRE: SystemMessage found in pruned_thinker_node - use HumanMessage!"


# =============================================================================
# TRIPWIRE v1.2: Identity Manager Invariants + Reporter Hardening
# =============================================================================

class TestAllowedSourceTypesConstantTripwire:
    """v1.2: Ensure ALLOWED_SOURCE_TYPES is not weakened."""
    
    def test_allowed_source_types_is_frozenset(self):
        """Block: changing from frozenset to mutable set."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager)
        
        assert "ALLOWED_SOURCE_TYPES = frozenset" in source, \
            "TRIPWIRE: ALLOWED_SOURCE_TYPES must be frozenset (immutable)!"
    
    def test_only_three_allowed_types(self):
        """Block: expanding ALLOWED_SOURCE_TYPES to include llm_output, inferred, etc."""
        from src.core.identity_manager import ALLOWED_SOURCE_TYPES
        
        assert ALLOWED_SOURCE_TYPES == frozenset({"explicit_user", "snapshot", "admin"}), \
            f"TRIPWIRE: ALLOWED_SOURCE_TYPES was modified! Got: {ALLOWED_SOURCE_TYPES}"
    
    def test_no_llm_output_allowed(self):
        """Explicit check that llm_output is NOT in allowed types."""
        from src.core.identity_manager import ALLOWED_SOURCE_TYPES
        
        assert "llm_output" not in ALLOWED_SOURCE_TYPES, \
            "TRIPWIRE: 'llm_output' was added to ALLOWED_SOURCE_TYPES!"
        assert "inferred" not in ALLOWED_SOURCE_TYPES, \
            "TRIPWIRE: 'inferred' was added to ALLOWED_SOURCE_TYPES!"


class TestMaxContextCharsConstantTripwire:
    """v1.2: Ensure MAX_CONTEXT_CHARS is not raised (context creep)."""
    
    def test_max_context_chars_exists(self):
        """Block: removing the context limit."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager)
        
        assert "MAX_CONTEXT_CHARS" in source, \
            "TRIPWIRE: MAX_CONTEXT_CHARS constant was removed!"
    
    def test_max_context_chars_is_500(self):
        """Block: raising limit above 500."""
        from src.core.identity_manager import MAX_CONTEXT_CHARS
        
        assert MAX_CONTEXT_CHARS == 500, \
            f"TRIPWIRE: MAX_CONTEXT_CHARS was changed from 500 to {MAX_CONTEXT_CHARS}!"


class TestWriteBarrierLogicTripwire:
    """v1.2: Ensure write barrier logic is present in update_identity."""
    
    def test_write_barrier_check_exists(self):
        """Block: removing the source_type validation."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager.IdentityManager.update_identity)
        
        assert "source_type not in ALLOWED_SOURCE_TYPES" in source, \
            "TRIPWIRE: Write barrier check was removed from update_identity!"
    
    def test_write_barrier_raises_valueerror(self):
        """Block: returning silently instead of raising."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager.IdentityManager.update_identity)
        
        assert "raise ValueError" in source, \
            "TRIPWIRE: update_identity no longer raises ValueError on illegal source_type!"


class TestSnapshotFirstInvariantTripwire:
    """v1.2: Ensure snapshot-first invariant is enforced in code."""
    
    def test_snapshot_hash_required_check(self):
        """Block: removing the snapshot_hash requirement."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager.IdentityManager.update_identity)
        
        assert 'source_type == "snapshot"' in source or "source_type == 'snapshot'" in source, \
            "TRIPWIRE: Snapshot type check was removed!"
        assert "snapshot_hash" in source, \
            "TRIPWIRE: snapshot_hash validation was removed!"
    
    def test_snapshot_existence_verified(self):
        """Block: removing the DB lookup that verifies snapshot exists."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager.IdentityManager.update_identity)
        
        assert "SELECT 1 FROM snapshots WHERE snapshot_hash" in source or \
               "SELECT 1 FROM snapshots" in source, \
            "TRIPWIRE: Snapshot existence check was removed!"


class TestReporterNodeWriteGatingTripwire:
    """v1.2: Ensure reporter_node only writes on success."""
    
    def test_success_gating_exists(self):
        """Block: removing the is_successful check."""
        from src.graph import workflow
        source = inspect.getsource(workflow.reporter_node)
        
        assert "is_successful" in source, \
            "TRIPWIRE: Success gating variable removed from reporter_node!"
        assert "if is_successful:" in source or "if is_successful" in source, \
            "TRIPWIRE: Success gating conditional removed from reporter_node!"
    
    def test_update_identity_inside_success_block(self):
        """Block: moving update_identity outside the success block."""
        from src.graph import workflow
        source = inspect.getsource(workflow.reporter_node)
        
        # Find the if is_successful block and verify update_identity is inside
        # Simple heuristic: update_identity should appear AFTER "if is_successful"
        success_pos = source.find("if is_successful")
        update_pos = source.find("update_identity")
        
        assert success_pos != -1, \
            "TRIPWIRE: 'if is_successful' block not found in reporter_node!"
        assert update_pos > success_pos, \
            "TRIPWIRE: update_identity appears BEFORE is_successful check!"
    
    def test_create_snapshot_before_update_identity(self):
        """Block: calling update_identity before create_snapshot."""
        from src.graph import workflow
        source = inspect.getsource(workflow.reporter_node)
        
        snapshot_pos = source.find("create_snapshot")
        update_pos = source.find("update_identity")
        
        if snapshot_pos != -1 and update_pos != -1:
            assert snapshot_pos < update_pos, \
                "TRIPWIRE: update_identity called BEFORE create_snapshot!"


class TestNoIdentityWriteOutsideReporterTripwire:
    """v1.2: Ensure update_identity/create_snapshot ONLY in reporter_node."""
    
    def test_no_update_identity_in_sanitizer_node(self):
        """Block: adding identity writes to sanitizer_node."""
        from src.graph import workflow
        source = inspect.getsource(workflow.sanitizer_node)
        
        assert "update_identity" not in source, \
            "TRIPWIRE: update_identity found in sanitizer_node!"
        assert "create_snapshot" not in source, \
            "TRIPWIRE: create_snapshot found in sanitizer_node!"


class TestSerializeTruncationLogicTripwire:
    """v1.2: Ensure serialize_for_prompt has truncation."""
    
    def test_truncation_logic_exists(self):
        """Block: removing the truncation check."""
        from src.core import identity_manager
        source = inspect.getsource(identity_manager.IdentityManager.serialize_for_prompt)
        
        assert "MAX_CONTEXT_CHARS" in source, \
            "TRIPWIRE: MAX_CONTEXT_CHARS check removed from serialize_for_prompt!"
        assert "truncated" in source.lower(), \
            "TRIPWIRE: Truncation indicator removed from serialize_for_prompt!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
