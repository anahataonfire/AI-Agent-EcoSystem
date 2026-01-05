"""
Curator Advisor Agent

Reviews ingested content, suggests categorization and action items,
and learns from user feedback to improve future suggestions.
"""

import json
import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .base import BaseAgent, ProposalEnvelope


# SQLite database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "advisor_learning.db"


@dataclass
class Suggestion:
    """A single suggestion from the advisor."""
    type: str  # "category", "action", "priority"
    current_value: str
    suggested_value: str
    confidence: float
    reasoning: str
    accepted: Optional[bool] = None


class AdvisorMemory:
    """Learning memory for the advisor (SQLite-backed)."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
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
        conn.close()
    
    def record_feedback(self, content_id: str, suggestion_type: str, 
                       suggested: str, accepted: bool, notes: str = ""):
        """Record user feedback for learning."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
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
            suggestion_type,
            context,
            outcome,
            now,
            now
        ))
        
        conn.commit()
        conn.close()
    
    @property
    def feedback_history(self) -> list:
        """Get all feedback history from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_type, context, outcome, created_at
            FROM learning_patterns
            ORDER BY created_at DESC
        """)
        
        results = []
        for row in cursor.fetchall():
            pattern_type, context_json, outcome, created_at = row
            context = json.loads(context_json)
            results.append({
                "type": pattern_type,
                "content_id": context.get("content_id"),
                "suggested": context.get("suggested"),
                "accepted": outcome == "accepted",
                "notes": context.get("notes", ""),
                "timestamp": created_at,
            })
        
        conn.close()
        return results
    
    @property
    def category_preferences(self) -> dict:
        """Get category preferences from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT context, outcome
            FROM learning_patterns
            WHERE pattern_type = 'category'
        """)
        
        prefs = {}
        for row in cursor.fetchall():
            context_json, outcome = row
            context = json.loads(context_json)
            category = context.get("suggested")
            
            if category and category not in prefs:
                prefs[category] = {"accepts": 0, "rejects": 0, "weight": 1.0}
            
            if category:
                if outcome == "accepted":
                    prefs[category]["accepts"] += 1
                else:
                    prefs[category]["rejects"] += 1
        
        # Recalculate weights
        for category, data in prefs.items():
            total = data["accepts"] + data["rejects"]
            if total > 0:
                data["weight"] = data["accepts"] / total
        
        conn.close()
        return prefs
    
    @property
    def action_patterns(self) -> list:
        """Get action patterns from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT context, outcome
            FROM learning_patterns
            WHERE pattern_type = 'action'
        """)
        
        patterns = []
        for row in cursor.fetchall():
            context_json, outcome = row
            context = json.loads(context_json)
            patterns.append({**context, "outcome": outcome})
        
        conn.close()
        return patterns


class CuratorAdvisor(BaseAgent):
    """
    AI advisor that reviews content and provides suggestions.
    
    Learns from user feedback to improve recommendations over time.
    """
    
    SKILL_FILE = "advisor.skill.md"
    
    def __init__(self, run_id: str = "advisor-run", run_ts: str = None, 
                 content_store=None, api_key: str = None):
        """
        Initialize advisor.
        
        Args:
            run_id: Unique run identifier
            run_ts: Timestamp for run
            content_store: ContentStore instance for reading content
            api_key: Google API key for Gemini
        """
        if run_ts is None:
            run_ts = datetime.now().isoformat()
        
        super().__init__(run_id=run_id, run_ts=run_ts)
        
        self.content_store = content_store
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.memory = AdvisorMemory()
        self._client = None
        self._model_id = "gemini-2.0-flash"
    
    @property
    def client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Main processing - route to appropriate method.
        
        input_data should contain:
            - action: "review" | "learn" | "chat"
            - content_id: ID of content to process
            - feedback: (for learn) feedback data
            - message: (for chat) user message
        """
        action = input_data.get("action", "review")
        content_id = input_data.get("content_id")
        
        if action == "review":
            result = self._review_content(content_id)
            claims = ["suggest_category", "suggest_action_item", "suggest_priority"]
        elif action == "learn":
            result = self._learn_from_feedback(input_data.get("feedback", {}))
            claims = ["learn_preference"]
        elif action == "chat":
            result = self._chat_response(content_id, input_data.get("message", ""))
            claims = ["chat_response", "read_content"]
        else:
            result = {"error": f"Unknown action: {action}"}
            claims = []
        
        return self.wrap_output(result, claims)
    
    def _review_content(self, content_id: str) -> dict:
        """Review content and generate suggestions."""
        if not self.content_store:
            return {"error": "No content store configured"}
        
        entry = self.content_store.read(content_id)
        if not entry:
            return {"error": f"Content not found: {content_id}"}
        
        # Build prompt with memory context
        memory_context = self._build_memory_context()
        
        prompt = f"""You are a content categorization advisor for an AI development project.

Review this content and suggest improvements to its categorization and action items.

CONTENT:
Title: {entry.title}
URL: {entry.url}
Current Categories: {', '.join(entry.categories)}
Current Summary: {entry.summary}

Raw Content (excerpt):
{entry.raw_content[:4000] if entry.raw_content else 'Not available'}

Existing Action Items:
{self._format_action_items(entry.action_items)}

USER PREFERENCE CONTEXT:
{memory_context}

---

Provide suggestions in this JSON format:
{{
  "category_suggestions": [
    {{"current": "...", "suggested": "...", "confidence": 0.85, "reasoning": "..."}}
  ],
  "action_suggestions": [
    {{"description": "...", "type": "enhancement|research|documentation", "priority": 1-5, "reasoning": "..."}}
  ],
  "priority_suggestion": {{
    "current": "...",
    "suggested": "P1|P2|P3",
    "reasoning": "..."
  }}
}}

Be specific and actionable. Consider the user's past preferences when making suggestions."""

        try:
            response = self.client.models.generate_content(
                model=self._model_id,
                contents=prompt,
            )
            
            # Parse response
            text = response.text
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                suggestions = json.loads(json_match.group())
            else:
                suggestions = {"raw_response": text}
            
            return {
                "content_id": content_id,
                "title": entry.title,
                "suggestions": suggestions,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {"error": f"Review failed: {e}"}
    
    def _learn_from_feedback(self, feedback: dict) -> dict:
        """Update memory based on user feedback."""
        content_id = feedback.get("content_id")
        suggestion_type = feedback.get("type")
        suggested = feedback.get("suggested")
        accepted = feedback.get("accepted", False)
        notes = feedback.get("notes", "")
        
        if not all([content_id, suggestion_type, suggested]):
            return {"error": "Missing required feedback fields"}
        
        self.memory.record_feedback(content_id, suggestion_type, suggested, accepted, notes)
        
        return {
            "status": "learned",
            "type": suggestion_type,
            "accepted": accepted,
            "total_feedback_count": len(self.memory.feedback_history),
        }
    
    def _chat_response(self, content_id: str, message: str) -> dict:
        """Generate chat response about content."""
        if not self.content_store:
            return {"error": "No content store configured"}
        
        entry = self.content_store.read(content_id)
        if not entry:
            return {"error": f"Content not found: {content_id}"}
        
        prompt = f"""You are an AI advisor helping a user understand and categorize content for their AI development project.

CONTENT CONTEXT:
Title: {entry.title}
Categories: {', '.join(entry.categories)}
Summary: {entry.summary}

Content excerpt:
{entry.raw_content[:3000] if entry.raw_content else 'Not available'}

USER MESSAGE: {message}

---

Respond helpfully. If the user is giving feedback about categorization or priorities, acknowledge it and explain how it will affect future suggestions.
Keep your response concise and actionable."""

        try:
            response = self.client.models.generate_content(
                model=self._model_id,
                contents=prompt,
            )
            return {
                "content_id": content_id,
                "user_message": message,
                "advisor_response": response.text,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": f"Chat failed: {e}"}
    
    def _build_memory_context(self) -> str:
        """Build context string from learning memory."""
        if not self.memory.category_preferences:
            return "No preference history yet."
        
        lines = ["Based on past feedback:"]
        
        # Sort categories by weight
        sorted_cats = sorted(
            self.memory.category_preferences.items(),
            key=lambda x: x[1].get("weight", 0),
            reverse=True
        )
        
        for cat, prefs in sorted_cats[:5]:
            weight = prefs.get("weight", 1.0)
            accepts = prefs.get("accepts", 0)
            rejects = prefs.get("rejects", 0)
            if accepts + rejects > 0:
                lines.append(f"- {cat}: {weight:.0%} acceptance ({accepts} accepts, {rejects} rejects)")
        
        return "\n".join(lines)
    
    def _format_action_items(self, action_items: list) -> str:
        """Format action items for prompt."""
        if not action_items:
            return "None"
        
        lines = []
        for item in action_items:
            lines.append(f"- [{item.action_type.value}] P{item.priority}: {item.description}")
        return "\n".join(lines)
    
    def get_memory_stats(self) -> dict:
        """Get statistics about learning memory."""
        return {
            "total_feedback": len(self.memory.feedback_history),
            "categories_learned": len(self.memory.category_preferences),
            "patterns_learned": len(self.memory.action_patterns),
        }
