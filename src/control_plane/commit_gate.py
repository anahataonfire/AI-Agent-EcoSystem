"""
CommitGate for DTL v2.0

The CommitGate is the final checkpoint before any write to immutable stores.
It validates CommitBundles using deterministic checks only (no LLM).

Validation checks:
1. Schema validation
2. Hash verification
3. Evidence ID existence
4. Evidence time-validity
5. Capability manifest compliance
6. Kill-switch compliance
7. Ledger prewrite existence
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any
import jsonschema


class CommitStatus(Enum):
    """Commit validation status."""
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass
class RejectionPayload:
    """Structured rejection information."""
    code: str
    violating_field: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)
    manifest_rule: Optional[str] = None
    kill_switch: Optional[str] = None
    details: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CommitResult:
    """Result of CommitGate validation."""
    status: CommitStatus
    bundle_hash: str
    timestamp: str
    rejection: Optional[RejectionPayload] = None
    
    @property
    def accepted(self) -> bool:
        return self.status == CommitStatus.ACCEPTED
    
    def to_dict(self) -> dict:
        result = {
            "status": self.status.value,
            "bundle_hash": self.bundle_hash,
            "timestamp": self.timestamp
        }
        if self.rejection:
            result["rejection"] = self.rejection.to_dict()
        return result


@dataclass
class CommitBundle:
    """
    A bundle of proposed commits from Reporter.
    
    The bundle encapsulates all proposed changes and metadata required
    for CommitGate validation.
    """
    run_id: str
    agent_id: str
    schema_version: str
    timestamp: str
    content_hash: str
    payload: dict
    evidence_refs: list[str] = field(default_factory=list)
    capability_claims: list[str] = field(default_factory=list)
    
    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of the FULL bundle (not just payload).
        
        Covers: run_id, agent_id, schema_version, timestamp, payload,
                evidence_refs, capability_claims
        
        This prevents metadata tampering while preserving payload hash.
        """
        canonical = {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "evidence_refs": sorted(self.evidence_refs),
            "capability_claims": sorted(self.capability_claims)
        }
        canonical_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        return f"sha256:{hashlib.sha256(canonical_str.encode()).hexdigest()}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CommitBundle':
        return cls(**data)


class CommitGate:
    """
    CommitGate - Deterministic validation of CommitBundles.
    
    This is the final checkpoint before any persistence.
    All checks are deterministic (no LLM involvement).
    """
    
    # Rejection codes
    SCHEMA_INVALID = "SCHEMA_INVALID"
    HASH_MISMATCH = "HASH_MISMATCH"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_INVALID_TIMESTAMP = "EVIDENCE_INVALID_TIMESTAMP"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    KILL_SWITCH_BLOCKED = "KILL_SWITCH_BLOCKED"
    PREWRITE_MISSING = "PREWRITE_MISSING"
    
    def __init__(
        self,
        evidence_store_path: Optional[str] = None,
        prewrite_path: Optional[str] = None,
        evidence_ttl_seconds: int = 7 * 24 * 3600,  # 7 days default
    ):
        self.evidence_store = Path(evidence_store_path) if evidence_store_path else Path("data/evidence_store")
        self.prewrite_path = Path(prewrite_path) if prewrite_path else Path("data/run_ledger/prewrite")
        self.evidence_ttl_seconds = evidence_ttl_seconds
        self._bundle_schema = self._load_bundle_schema()
    
    def _load_bundle_schema(self) -> Optional[dict]:
        """Load CommitBundle JSON Schema if available."""
        schema_path = Path("config/schemas/commit_bundle.json")
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                return json.load(f)
        return None
    
    def validate(
        self,
        bundle: CommitBundle,
        active_kill_switches: Optional[list[str]] = None,
        allowed_capabilities: Optional[list[str]] = None
    ) -> CommitResult:
        """
        Validate a CommitBundle.
        
        Runs all 7 validation checks in order.
        Returns ACCEPTED only if ALL checks pass.
        
        Args:
            bundle: The CommitBundle to validate
            active_kill_switches: List of currently active kill switches
            allowed_capabilities: List of capabilities this agent is allowed to claim
        
        Returns:
            CommitResult with status and any rejection details
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        bundle_hash = bundle.compute_hash()
        
        # Check 1: Schema validation
        rejection = self._check_schema(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 2: Hash verification
        rejection = self._check_hash(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 3: Evidence ID existence
        rejection = self._check_evidence_exists(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 4: Evidence time-validity
        rejection = self._check_evidence_freshness(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 5: Capability manifest compliance
        rejection = self._check_capabilities(bundle, allowed_capabilities)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 6: Kill-switch compliance
        rejection = self._check_kill_switches(bundle, active_kill_switches)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 7: Ledger prewrite existence
        rejection = self._check_prewrite(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # All checks passed
        return CommitResult(CommitStatus.ACCEPTED, bundle_hash, timestamp)
    
    def _check_schema(self, bundle: CommitBundle) -> Optional[RejectionPayload]:
        """Check 1: Validate bundle against JSON Schema."""
        if not self._bundle_schema:
            # No schema defined - skip validation
            return None
        
        try:
            jsonschema.validate(bundle.to_dict(), self._bundle_schema)
            return None
        except jsonschema.ValidationError as e:
            # Convert path to JSON pointer format
            json_pointer = "/" + "/".join(str(p) for p in e.path) if e.path else "/"
            return RejectionPayload(
                code=self.SCHEMA_INVALID,
                violating_field=json_pointer,
                details=str(e.message)
            )
    
    def _check_hash(self, bundle: CommitBundle) -> Optional[RejectionPayload]:
        """Check 2: Verify content hash matches payload."""
        computed = bundle.compute_hash()
        if computed != bundle.content_hash:
            return RejectionPayload(
                code=self.HASH_MISMATCH,
                violating_field="content_hash",
                details=f"Expected {computed}, got {bundle.content_hash}"
            )
        return None
    
    def _check_evidence_exists(self, bundle: CommitBundle) -> Optional[RejectionPayload]:
        """Check 3: Verify all referenced evidence IDs exist."""
        missing = []
        for ev_id in bundle.evidence_refs:
            ev_path = self.evidence_store / f"{ev_id}.json"
            if not ev_path.exists():
                missing.append(ev_id)
        
        if missing:
            return RejectionPayload(
                code=self.EVIDENCE_MISSING,
                evidence_ids=missing,
                details=f"Missing evidence files: {missing}"
            )
        return None
    
    def _check_evidence_freshness(self, bundle: CommitBundle) -> Optional[RejectionPayload]:
        """
        Check 4: Verify evidence is not stale (within TTL).
        
        Requires fetched_at to be RFC3339 with timezone (Z or offset).
        Missing/invalid timezone is EVIDENCE_INVALID_TIMESTAMP, not stale.
        """
        stale = []
        invalid_timestamp = []
        now = datetime.now(timezone.utc)
        
        for ev_id in bundle.evidence_refs:
            ev_path = self.evidence_store / f"{ev_id}.json"
            if ev_path.exists():
                try:
                    with open(ev_path, 'r') as f:
                        evidence = json.load(f)
                    
                    fetched_at_str = evidence.get("fetched_at", "")
                    if not fetched_at_str:
                        invalid_timestamp.append(ev_id)
                        continue
                    
                    # Parse ISO format
                    fetched_at = datetime.fromisoformat(fetched_at_str.replace('Z', '+00:00'))
                    
                    # Ensure timezone-aware
                    if fetched_at.tzinfo is None:
                        invalid_timestamp.append(ev_id)
                        continue
                    
                    age_seconds = (now - fetched_at).total_seconds()
                    if age_seconds > self.evidence_ttl_seconds:
                        stale.append(ev_id)
                        
                except json.JSONDecodeError:
                    invalid_timestamp.append(ev_id)
                except ValueError:
                    invalid_timestamp.append(ev_id)
        
        # Invalid timestamps are a distinct error (not stale)
        if invalid_timestamp:
            return RejectionPayload(
                code=self.EVIDENCE_INVALID_TIMESTAMP,
                evidence_ids=invalid_timestamp,
                details=f"Evidence with missing/invalid timezone: {invalid_timestamp}"
            )
        
        if stale:
            return RejectionPayload(
                code=self.EVIDENCE_STALE,
                evidence_ids=stale,
                details=f"Evidence older than {self.evidence_ttl_seconds}s: {stale}"
            )
        return None
    
    def _check_capabilities(
        self, 
        bundle: CommitBundle, 
        allowed: Optional[list[str]]
    ) -> Optional[RejectionPayload]:
        """Check 5: Verify agent capabilities are allowed by manifest."""
        if allowed is None:
            # No manifest defined - allow all
            return None
        
        allowed_set = set(allowed)
        claimed = set(bundle.capability_claims)
        unauthorized = claimed - allowed_set
        
        if unauthorized:
            return RejectionPayload(
                code=self.CAPABILITY_DENIED,
                violating_field="capability_claims",
                details=f"Unauthorized capabilities: {list(unauthorized)}"
            )
        return None
    
    def _check_kill_switches(
        self, 
        bundle: CommitBundle, 
        active_switches: Optional[list[str]]
    ) -> Optional[RejectionPayload]:
        """Check 6: Verify no active kill switch blocks this commit."""
        if not active_switches:
            return None
        
        # DISABLE_WRITES blocks all commits
        if "DISABLE_WRITES" in active_switches:
            return RejectionPayload(
                code=self.KILL_SWITCH_BLOCKED,
                kill_switch="DISABLE_WRITES",
                details="All writes disabled by kill switch"
            )
        
        # DISABLE_LEARNING blocks certain capability claims
        if "DISABLE_LEARNING" in active_switches:
            learning_caps = {"routing_statistics_write", "strategy_adaptation"}
            if learning_caps.intersection(set(bundle.capability_claims)):
                return RejectionPayload(
                    code=self.KILL_SWITCH_BLOCKED,
                    kill_switch="DISABLE_LEARNING",
                    details="Learning-related capabilities blocked"
                )
        
        return None
    
    def _check_prewrite(self, bundle: CommitBundle) -> Optional[RejectionPayload]:
        """Check 7: Verify ledger prewrite exists with matching hash."""
        prewrite_file = self.prewrite_path / f"PREWRITE-{bundle.run_id}.json"
        
        if not prewrite_file.exists():
            return RejectionPayload(
                code=self.PREWRITE_MISSING,
                violating_field="run_id",
                details=f"No prewrite found for run {bundle.run_id}"
            )
        
        try:
            with open(prewrite_file, 'r') as f:
                prewrite = json.load(f)
            prewrite_hash = prewrite.get("bundle_hash")
            
            if prewrite_hash != bundle.content_hash:
                return RejectionPayload(
                    code=self.HASH_MISMATCH,
                    violating_field="prewrite.bundle_hash",
                    details=f"Prewrite hash {prewrite_hash} != bundle hash {bundle.content_hash}"
                )
        except (json.JSONDecodeError, KeyError) as e:
            return RejectionPayload(
                code=self.PREWRITE_MISSING,
                details=f"Invalid prewrite file: {e}"
            )
        
        return None
    
    def create_prewrite(self, bundle: CommitBundle) -> Path:
        """
        Create a prewrite token for a bundle.
        
        This must be called BEFORE validate() to satisfy Check 7.
        
        IMPORTANT: Prewrite stores the FULL bundle hash (compute_hash()),
        not just payload hash. This locks the exact commit intent.
        """
        self.prewrite_path.mkdir(parents=True, exist_ok=True)
        prewrite_file = self.prewrite_path / f"PREWRITE-{bundle.run_id}.json"
        
        # Use compute_hash() which covers the full bundle
        full_hash = bundle.compute_hash()
        
        prewrite_data = {
            "run_id": bundle.run_id,
            "bundle_hash": full_hash,  # Full bundle hash, not just payload
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": bundle.agent_id,
            "evidence_refs": bundle.evidence_refs,
            "capability_claims": bundle.capability_claims
        }
        
        with open(prewrite_file, 'w') as f:
            json.dump(prewrite_data, f, indent=2)
        
        return prewrite_file
    
    def promote_to_committed(self, bundle: CommitBundle) -> 'PromoteResult':
        """
        Promote a prewrite to committed status after successful validation.
        
        Returns explicit result codes for deterministic behavior.
        Logs the promotion to the ledger.
        
        Returns:
            PromoteResult with status and details
        """
        prewrite_file = self.prewrite_path / f"PREWRITE-{bundle.run_id}.json"
        committed_path = self.prewrite_path.parent / "committed"
        committed_path.mkdir(parents=True, exist_ok=True)
        committed_file = committed_path / f"COMMITTED-{bundle.run_id}.json"
        
        # IMMUTABILITY: Check for already committed FIRST
        # If committed file exists, this run_id cannot be re-promoted
        if committed_file.exists():
            # Clean up any dangling prewrite for this run_id
            if prewrite_file.exists():
                prewrite_file.unlink()
            return PromoteResult(
                status=PromoteStatus.ALREADY_COMMITTED,
                run_id=bundle.run_id,
                path=committed_file,
                message=f"Already committed: {committed_file}"
            )
        
        # Check for missing prewrite
        if not prewrite_file.exists():
            return PromoteResult(
                status=PromoteStatus.PREWRITE_NOT_FOUND,
                run_id=bundle.run_id,
                path=None,
                message=f"Prewrite not found: {prewrite_file}"
            )
        
        # Perform atomic rename
        try:
            prewrite_file.rename(committed_file)
            
            # Log to ledger
            self._log_promotion(bundle.run_id, committed_file)
            
            return PromoteResult(
                status=PromoteStatus.SUCCESS,
                run_id=bundle.run_id,
                path=committed_file,
                message=f"Promoted to: {committed_file}"
            )
        except OSError as e:
            return PromoteResult(
                status=PromoteStatus.RENAME_FAILED,
                run_id=bundle.run_id,
                path=None,
                message=f"Rename failed: {e}"
            )
    
    def _log_promotion(self, run_id: str, committed_file: Path):
        """Log promotion to ledger."""
        ledger_path = self.prewrite_path.parent / "promotion_log.jsonl"
        log_entry = {
            "event": "PROMOTED",
            "run_id": run_id,
            "committed_file": str(committed_file),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(ledger_path, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def validate_prewrite_eligibility(
        self,
        bundle: CommitBundle,
        active_kill_switches: Optional[list[str]] = None,
        allowed_capabilities: Optional[list[str]] = None
    ) -> CommitResult:
        """
        Validate bundle is eligible for prewrite creation.
        
        Runs checks 1-6 (schema, hash, evidence, capabilities, kill switches).
        Does NOT check prewrite existence (check 7).
        
        P0 Fix: Call this BEFORE create_prewrite() to avoid dangling prewrites.
        
        Returns:
            CommitResult - only create prewrite if ACCEPTED
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        bundle_hash = bundle.compute_hash()
        
        # Check 1: Schema validation
        rejection = self._check_schema(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 2: Hash verification
        rejection = self._check_hash(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 3: Evidence ID existence
        rejection = self._check_evidence_exists(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 4: Evidence time-validity
        rejection = self._check_evidence_freshness(bundle)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 5: Capability manifest compliance
        rejection = self._check_capabilities(bundle, allowed_capabilities)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Check 6: Kill-switch compliance
        rejection = self._check_kill_switches(bundle, active_kill_switches)
        if rejection:
            return CommitResult(CommitStatus.REJECTED, bundle_hash, timestamp, rejection)
        
        # Checks 1-6 passed - eligible for prewrite
        return CommitResult(CommitStatus.ACCEPTED, bundle_hash, timestamp)
    
    def delete_prewrite(self, bundle: CommitBundle) -> bool:
        """
        Delete a prewrite token.
        
        P0 Fix: Use this to clean up prewrites after validation failure.
        
        Returns:
            True if deleted, False if not found
        """
        prewrite_file = self.prewrite_path / f"PREWRITE-{bundle.run_id}.json"
        
        if prewrite_file.exists():
            prewrite_file.unlink()
            
            # Log deletion
            ledger_path = self.prewrite_path.parent / "promotion_log.jsonl"
            log_entry = {
                "event": "PREWRITE_DELETED",
                "run_id": bundle.run_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            with open(ledger_path, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
            
            return True
        
        return False


class PromoteStatus(Enum):
    """Result status for promote_to_committed."""
    SUCCESS = "SUCCESS"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    PREWRITE_NOT_FOUND = "PREWRITE_NOT_FOUND"
    RENAME_FAILED = "RENAME_FAILED"


@dataclass
class PromoteResult:
    """Result of promote_to_committed operation."""
    status: PromoteStatus
    run_id: str
    path: Optional[Path]
    message: str
    
    @property
    def success(self) -> bool:
        return self.status == PromoteStatus.SUCCESS


