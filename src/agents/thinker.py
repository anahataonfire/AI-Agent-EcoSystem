"""
Thinker agent node for the LangGraph pipeline.

This module implements the planning agent that:
- Dynamically loads skill instructions from markdown files
- Makes LLM calls to generate structured action plans
- Outputs JSON matching the ProposedAction schema
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from src.core.schemas import ProposedAction
from src.graph.state import RunState


# Default model configuration
DEFAULT_MODEL = "gpt-4o-mini"
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def load_skill(skill_name: str) -> str:
    """
    Load a skill definition from the skills directory.
    
    Args:
        skill_name: Name of the skill file (without .md extension)
        
    Returns:
        Content of the skill markdown file
    """
    skill_path = SKILLS_DIR / f"{skill_name}.md"
    
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_path}")
    
    return skill_path.read_text(encoding="utf-8")


def generate_fingerprint(plan: Dict[str, Any]) -> str:
    """Generate a SHA-256 fingerprint for a plan."""
    # Sort keys for consistent hashing
    normalized = json.dumps(plan, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def build_system_prompt(skills: list[str] = None) -> str:
    """
    Build the system prompt with dynamically loaded skills.
    
    Args:
        skills: List of skill names to load. Defaults to ['skill_planning_basic']
    """
    if skills is None:
        skills = ["skill_planning_basic", "skill_deep_research", "skill_identity_usage"]
    
    # Load skill content
    skill_content = []
    for skill_name in skills:
        try:
            content = load_skill(skill_name)
            skill_content.append(f"## {skill_name}\n\n{content}")
        except FileNotFoundError:
            skill_content.append(f"## {skill_name}\n\n[Skill not found]")
    
    skills_text = "\n\n---\n\n".join(skill_content)
    
    return f"""You are a planning agent for an RSS-to-Summary pipeline.

Your task is to analyze user requests and generate structured action plans.

# Skills & Instructions

{skills_text}

# Output Requirements

You MUST output ONLY a valid JSON object matching this exact schema:

{{
  "action_type": "tool_call",
  "tool_name": "<DataFetchRSS|CompleteTask>",
  "params": {{}},
  "success_criteria": [],
  "plan_fingerprint": "<will_be_generated>"
}}

Do NOT include any explanation, markdown formatting, or additional text.
Output ONLY the JSON object."""


def parse_llm_response(content: str) -> Dict[str, Any]:
    """
    Parse LLM response to extract JSON.
    
    Handles common issues like markdown code blocks.
    """
    # Remove markdown code blocks if present
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    # Strip whitespace
    content = content.strip()
    
    return json.loads(content)


def get_llm(model_name: str = None) -> BaseChatModel:
    """
    Get an LLM instance. Supports multiple providers via environment variables.
    
    Priority:
    1. OPENAI_API_KEY -> ChatOpenAI
    2. ANTHROPIC_API_KEY -> ChatAnthropic
    3. GOOGLE_API_KEY -> ChatGoogleGenerativeAI
    """
    model_name = model_name or DEFAULT_MODEL
    
    def is_valid_key(key: str) -> bool:
        """Check if an API key is valid (not a placeholder)."""
        if not key:
            return False
        placeholders = ["your_", "sk-xxx", "placeholder", "your-api-key"]
        return not any(p in key.lower() for p in placeholders)
    
    # Try OpenAI first
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if is_valid_key(openai_key):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_name, temperature=0)
    
    # Try Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if is_valid_key(anthropic_key):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-3-haiku-20240307", temperature=0)
    
    # Try Google
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if is_valid_key(google_key):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    
    raise RuntimeError(
        "No valid LLM API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY."
    )


def thinker_node(
    state: RunState,
    llm: Optional[BaseChatModel] = None,
    skills: list[str] = None,
) -> Dict[str, Any]:
    """
    Generate an action plan based on the current state and messages.
    
    This node:
    1. Loads skill instructions from markdown files
    2. Builds a system prompt with the skills
    3. Calls the LLM to generate a structured plan
    4. Parses and validates the response
    5. Returns the plan as current_plan
    
    Args:
        state: Current RunState with messages
        llm: Optional LLM instance (auto-detected if not provided)
        skills: Optional list of skill names to load
        
    Returns:
        State update with current_plan containing the ProposedAction
    """
    print("[THINKER-CORE] Starting thinker_node")
    
    # Get LLM instance
    if llm is None:
        try:
            llm = get_llm()
            print(f"[THINKER-CORE] LLM initialized: {type(llm).__name__}")
        except RuntimeError as e:
            print(f"[THINKER-CORE] ERROR: LLM init failed: {e}")
            return {
                "messages": [AIMessage(content=f"LLM initialization failed: {e}")]
            }
    
    # Build system prompt with skills
    system_prompt = build_system_prompt(skills)
    
    # Build message list for LLM with full history
    # Start with system prompt
    messages = [SystemMessage(content=system_prompt)]
    
    # Add conversation history
    # We filter out system messages from history to avoid confusion, 
    # as we just added the fresh system prompt
    history = [msg for msg in state.messages if not isinstance(msg, SystemMessage)]
    messages.extend(history)
    
    print(f"[THINKER-CORE] Calling LLM with {len(messages)} messages")
    
    # Call LLM
    try:
        response = llm.invoke(messages)
        response_content = response.content
        print(f"[THINKER-CORE] LLM response: {response_content[:300]}...")
    except Exception as e:
        print(f"[THINKER-CORE] ERROR: LLM call failed: {e}")
        return {
            "messages": [AIMessage(content=f"LLM call failed: {e}")]
        }
    
    # Parse response
    try:
        plan = parse_llm_response(response_content)
        print(f"[THINKER-CORE] Parsed plan: {plan.get('tool_name', 'N/A')}")
    except json.JSONDecodeError as e:
        print(f"[THINKER-CORE] ERROR: JSON parse failed: {e}")
        return {
            "messages": [AIMessage(
                content=f"Failed to parse LLM response as JSON: {e}\n"
                        f"Raw response: {response_content[:500]}"
            )]
        }
    
    # Generate fingerprint if not present
    if not plan.get("plan_fingerprint"):
        plan["plan_fingerprint"] = generate_fingerprint(plan)
    
    # Validate against ProposedAction schema
    try:
        action = ProposedAction(**plan)
        print(f"[THINKER-CORE] SUCCESS: Plan validated: {action.tool_name}")
    except Exception as e:
        print(f"[THINKER-CORE] ERROR: Schema validation failed: {e}")
        return {
            "messages": [AIMessage(
                content=f"Plan does not match ProposedAction schema: {e}\n"
                        f"Plan: {json.dumps(plan, indent=2)}"
            )]
        }
    
    # Success - return the plan
    return {
        "messages": [AIMessage(
            content=f"Generated plan: {action.tool_name} for {action.params}"
        )],
        "current_plan": action.model_dump(),
    }

