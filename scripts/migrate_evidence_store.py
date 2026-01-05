#!/usr/bin/env python3
"""
Migration script: Evidence Store JSON → SQLite

Migrates existing evidence_store.json to the new SQLite backend.
Preserves all payloads, metadata, and computed hashes.

Usage:
    python scripts/migrate_evidence_store.py
"""

import json
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def compute_payload_hash(payload: dict) -> str:
    """Compute SHA-256 hash of normalized payload."""
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def migrate():
    """Migrate evidence_store.json to SQLite."""
    json_path = PROJECT_ROOT / "data" / "evidence_store.json"
    db_path = PROJECT_ROOT / "data" / "evidence_store.db"
    backup_path = PROJECT_ROOT / "data" / "evidence_store.json.backup"
    
    print("=" * 60)
    print("Evidence Store Migration: JSON → SQLite")
    print("=" * 60)
    
    # Check if JSON exists
    if not json_path.exists():
        print(f"✗ JSON file not found: {json_path}")
        print("  Nothing to migrate.")
        return
    
    # Load JSON data
    print(f"\n1. Loading JSON from: {json_path}")
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        print(f"   Found {len(data)} evidence entries")
    except json.JSONDecodeError as e:
        print(f"✗ Failed to parse JSON: {e}")
        return
    
    if not data:
        print("   No entries to migrate.")
        return
    
    # Backup JSON
    print(f"\n2. Creating backup: {backup_path}")
    shutil.copy2(json_path, backup_path)
    print("   ✓ Backup created")
    
    # Initialize SQLite
    print(f"\n3. Initializing SQLite: {db_path}")
    from src.core.evidence_store import EvidenceStore
    store = EvidenceStore(str(db_path))
    print("   ✓ Database initialized")
    
    # Migrate entries
    print(f"\n4. Migrating {len(data)} entries...")
    migrated = 0
    errors = 0
    
    for evidence_id, entry in data.items():
        try:
            payload = entry.get("payload", {})
            metadata = entry.get("metadata", {})
            created_at = entry.get("created_at")
            
            # Extract indexed fields
            query_hash = metadata.pop("query_hash", None)
            source_url = metadata.pop("source_url", None)
            source_trust_tier = metadata.pop("source_trust_tier", 3)
            lifecycle = metadata.pop("lifecycle", "active")
            
            # Compute payload hash
            payload_hash = compute_payload_hash(payload)
            
            # Insert directly to preserve evidence_id
            conn = store._get_conn()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO evidence 
                    (evidence_id, payload_json, payload_hash, metadata_json, 
                     query_hash, source_url, source_trust_tier, lifecycle, 
                     created_at, sanitized)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    evidence_id,
                    json.dumps(payload, default=str),
                    payload_hash,
                    json.dumps(metadata, default=str),
                    query_hash,
                    source_url,
                    source_trust_tier,
                    lifecycle,
                    created_at or datetime.utcnow().isoformat(),
                    0
                ))
                conn.commit()
                migrated += 1
            finally:
                conn.close()
            
        except Exception as e:
            print(f"   ✗ Error migrating {evidence_id}: {e}")
            errors += 1
    
    print(f"\n   ✓ Migrated: {migrated}")
    if errors:
        print(f"   ✗ Errors: {errors}")
    
    # Verify
    print(f"\n5. Verifying migration...")
    stats = store.get_stats()
    print(f"   Total in SQLite: {stats['total']}")
    print(f"   By lifecycle: {stats['by_lifecycle']}")
    
    if stats['total'] == len(data):
        print(f"\n✓ Migration complete! All {len(data)} entries migrated successfully.")
        print(f"\nYou can safely delete the original JSON file:")
        print(f"  rm {json_path}")
    else:
        print(f"\n⚠ Migration incomplete. Expected {len(data)}, got {stats['total']}")
        print(f"  Original JSON preserved at: {backup_path}")


if __name__ == "__main__":
    migrate()
