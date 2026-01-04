"""
Curator Advisor Agent

Reviews ingested content, suggests categorization and action items,
and learns from user feedback to improve future suggestions.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from .base import BaseAgent, ProposalEnvelope


# Memory storage path
MEMORY_PATH = Path(__file__).parent.parent.parent / "data" / "advisor_memory.json"


@dataclass
class Suggestion:
    """A single suggestion from the advisor."""
    type: str  # "category", "action", "priority"
    current_value: str
    suggested_value: str
    confidence: float
    reasoning: str
    accepted: Optional[bool] = None


@dataclass
class AdvisorMemory:
    """Learning memory for the advisor."""
    category_preferences: dict = field(default_factory=dict)
    action_patterns: list = field(default_factory=list)
    feedback_history: list = field(default_factory=list)
    
    def save(self, path: Path = MEMORY_PATH):
        """Persist memory to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)
    
    @classmethod
    def load(cls, path: Path = MEMORY_PATH) -> "AdvisorMemory":
        """Load memory from disk."""
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls()
    
    def record_feedback(self, content_id: str, suggestion_type: str, 
                       suggested: str, accepted: bool, notes: str = ""):
        """Record user feedback for learning."""
        self.feedback_history.append({
            "content_id": content_id,
            "type": suggestion_type,
            "suggested": suggested,
            "accepted": accepted,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Update category preferences
        if suggestion_type == "category":
            if suggested not in self.category_preferences:
                self.category_preferences[suggested] = {"accepts": 0, "rejects": 0, "weight": 1.0}
            
            if accepted:
                self.category_preferences[suggested]["accepts"] += 1
            else:
                self.category_preferences[suggested]["rejects"] += 1
            
            # Recalculate weight
            prefs = self.category_preferences[suggested]
            total = prefs["accepts"] + prefs["rejects"]
            if total > 0:
                prefs["weight"] = prefs["accepts"] / total
        
        self.save()


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
        self.memory = AdvisorMemory.load()
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
