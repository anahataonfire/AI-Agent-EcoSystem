"""
Design Agent for UI/UX analysis and improvement suggestions.

Analyzes UI code, identifies usability issues, and provides
actionable recommendations for layout, spacing, colors, and accessibility.
"""

import json
import os
import re
from typing import Optional
from datetime import datetime

from .base import BaseAgent, ProposalEnvelope


class DesignAgent(BaseAgent):
    """
    AI agent for analyzing and improving UI designs.
    
    Capabilities (from designer.skill.md):
    - analyze_ui: Review UI code for usability issues
    - suggest_layout: Propose layout improvements
    - suggest_colors: Recommend color scheme changes
    - suggest_spacing: Identify padding/margin issues
    - generate_mockup: Create HTML/CSS mockups
    - accessibility_audit: Check WCAG compliance
    """
    
    SKILL_FILE = "designer.skill.md"
    
    def __init__(self, run_id: str = "design-run", run_ts: str = None, 
                 api_key: str = None):
        """
        Initialize design agent.
        
        Args:
            run_id: Unique run identifier
            run_ts: Timestamp for run
            api_key: Google API key for Gemini
        """
        if run_ts is None:
            run_ts = datetime.now().isoformat()
        
        super().__init__(run_id=run_id, run_ts=run_ts)
        
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
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
            - action: "analyze" | "mockup" | "accessibility"
            - ui_code: Source code to analyze
            - context: Additional context about the UI
        """
        action = input_data.get("action", "analyze")
        ui_code = input_data.get("ui_code", "")
        context = input_data.get("context", "")
        
        if action == "analyze":
            result = self.analyze_ui(ui_code, context)
            claims = ["analyze_ui", "suggest_layout", "suggest_spacing", "suggest_colors"]
        elif action == "mockup":
            result = self.generate_mockup(input_data.get("description", ""))
            claims = ["generate_mockup"]
        elif action == "accessibility":
            result = self.accessibility_audit(ui_code)
            claims = ["accessibility_audit"]
        else:
            result = {"error": f"Unknown action: {action}"}
            claims = []
        
        return self.wrap_output(result, claims)
    
    def analyze_ui(self, ui_code: str, context: str = "") -> dict:
        """
        Analyze UI code and suggest improvements.
        
        Args:
            ui_code: The source code to analyze
            context: Additional context (e.g., "Streamlit dashboard", "Chat interface")
        
        Returns:
            dict with issues and suggestions
        """
        if not ui_code:
            return {"error": "No UI code provided"}
        
        prompt = f"""You are a UI/UX design expert. Analyze this interface code and provide specific, actionable improvement suggestions.

CONTEXT: {context or "Web application interface"}

UI CODE:
```
{ui_code[:10000]}
```

---

Provide your analysis as JSON in this exact format:
{{
  "summary": "Brief overall assessment",
  "issues": [
    {{
      "severity": "high|medium|low",
      "category": "layout|spacing|color|accessibility|hierarchy|ux",
      "location": "specific line or component",
      "description": "What's wrong",
      "suggestion": "Specific fix with code example if applicable"
    }}
  ],
  "quick_wins": [
    "Easy improvements that can be made immediately"
  ],
  "design_principles_violated": [
    "e.g., 'Visual hierarchy unclear', 'Insufficient spacing'"
  ]
}}

Focus on:
1. Visual hierarchy - are sections clearly separated?
2. Spacing - is there enough breathing room?
3. Color usage - contrast, consistency, meaning
4. Layout - logical grouping, alignment
5. User experience - discoverability, feedback, flow
6. Accessibility - screen reader support, color contrast

Be specific and constructive. Limit to top 10 most impactful issues."""

        try:
            response = self.client.models.generate_content(
                model=self._model_id,
                contents=prompt,
            )
            
            text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                analysis = {"raw_response": text}
            
            return {
                "status": "analyzed",
                "analysis": analysis,
                "code_length": len(ui_code),
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {"error": f"Analysis failed: {e}"}
    
    def generate_mockup(self, description: str) -> dict:
        """
        Generate HTML/CSS mockup from description.
        
        Args:
            description: Natural language description of desired UI
        
        Returns:
            dict with HTML/CSS mockup code
        """
        if not description:
            return {"error": "No description provided"}
        
        prompt = f"""You are a UI designer. Generate clean, modern HTML/CSS for:

{description}

Requirements:
- Use flexbox/grid for layout
- Include subtle shadows and rounded corners
- Use a professional color palette
- Make it responsive
- Add hover states for interactive elements

Return ONLY valid HTML with embedded CSS. No markdown code blocks."""

        try:
            response = self.client.models.generate_content(
                model=self._model_id,
                contents=prompt,
            )
            
            return {
                "status": "generated",
                "mockup_html": response.text,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {"error": f"Mockup generation failed: {e}"}
    
    def accessibility_audit(self, ui_code: str) -> dict:
        """
        Audit UI code for accessibility issues (WCAG 2.1 AA).
        
        Args:
            ui_code: The source code to audit
        
        Returns:
            dict with accessibility issues and recommendations
        """
        if not ui_code:
            return {"error": "No UI code provided"}
        
        prompt = f"""You are an accessibility expert. Audit this UI code for WCAG 2.1 AA compliance.

UI CODE:
```
{ui_code[:8000]}
```

---

Return JSON with:
{{
  "score": "A|AA|AAA|Fail",
  "issues": [
    {{
      "wcag_criterion": "e.g., 1.4.3 Contrast",
      "severity": "critical|major|minor",
      "description": "What's wrong",
      "fix": "How to fix it"
    }}
  ],
  "passed_checks": ["List of things done correctly"],
  "recommendations": ["Suggested improvements"]
}}"""

        try:
            response = self.client.models.generate_content(
                model=self._model_id,
                contents=prompt,
            )
            
            text = response.text
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                audit = json.loads(json_match.group())
            else:
                audit = {"raw_response": text}
            
            return {
                "status": "audited",
                "audit": audit,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {"error": f"Accessibility audit failed: {e}"}
