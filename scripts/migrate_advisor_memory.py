"""
Migrate advisor_memory.json to SQLite database.

This script converts the existing JSON-based learning memory to a SQLite database
for better querying, concurrency, and transaction safety.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime


def create_schema(conn):
    """Create the learning patterns table schema."""
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            context TEXT NOT NULL,
            outcome TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_type ON learning_patterns(pattern_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON learning_patterns(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON learning_patterns(outcome)")
    
    conn.commit()


def migrate_json_to_sqlite():
    """Migrate existing JSON memory to SQLite."""
    old_file = Path("data/advisor_memory.json")
    new_db = Path("data/advisor_learning.db")
    
    # Check if old file exists
    if not old_file.exists():
        print(f"✓ No old memory file found at {old_file}")
        print(f"✓ Creating new SQLite database at {new_db}")
        conn = sqlite3.connect(new_db)
        create_schema(conn)
        conn.close()
        return
    
    # Load old data
    print(f"📖 Reading old memory from {old_file}")
    with open(old_file, 'r') as f:
        old_data = json.load(f)
    
    # Connect to new DB
    print(f"📦 Creating SQLite database at {new_db}")
    conn = sqlite3.connect(new_db)
    create_schema(conn)
    cursor = conn.cursor()
    
    # Migrate feedback history
    now = datetime.utcnow().isoformat()
    migrated = 0
    
    feedback_history = old_data.get("feedback_history", [])
    print(f"📋 Migrating {len(feedback_history)} feedback entries...")
    
    for entry in feedback_history:
        # Extract fields
        pattern_type = entry.get("type", "unknown")
        content_id = entry.get("content_id", "unknown")
        suggested = entry.get("suggested", "")
        accepted = entry.get("accepted", False)
        notes = entry.get("notes", "")
        timestamp = entry.get("timestamp", now)
        
        # Build context JSON
        context = json.dumps({
            "content_id": content_id,
            "suggested": suggested,
            "notes": notes
        })
        
        outcome = "accepted" if accepted else "rejected"
        
        cursor.execute("""
            INSERT INTO learning_patterns
            (pattern_type, context, outcome, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pattern_type,
            context,
            outcome,
            timestamp,
            now
        ))
        migrated += 1
    
    # Migrate category preferences
    category_prefs = old_data.get("category_preferences", {})
    print(f"🏷️  Migrating {len(category_prefs)} category preferences...")
    
    for category, prefs in category_prefs.items():
        accepts = prefs.get("accepts", 0)
        rejects = prefs.get("rejects", 0)
        weight = prefs.get("weight", 1.0)
        
        # Create synthetic feedback entries for category preferences
        for _ in range(accepts):
            context = json.dumps({
                "category": category,
                "weight": weight
            })
            cursor.execute("""
                INSERT INTO learning_patterns
                (pattern_type, context, outcome, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "category",
                context,
                "accepted",
                weight,
                now,
                now
            ))
            migrated += 1
    
    conn.commit()
    conn.close()
    
    print(f"✓ Migrated {migrated} learning patterns to SQLite")
    
    # Backup old file
    backup = old_file.with_suffix(".json.backup")
    old_file.rename(backup)
    print(f"✓ Backed up old file to {backup}")
    print(f"\n✅ Migration complete!")
    print(f"   Database: {new_db}")
    print(f"   Backup:   {backup}")


if __name__ == "__main__":
    migrate_json_to_sqlite()
