"""
Centralized LLM Configuration and Validation

This module provides fail-fast validation for LLM API keys,
preventing silent failures when keys are missing or invalid.
"""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Load .env with override=True so it takes priority over shell env
from dotenv import load_dotenv
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env", override=True)


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class LLMConnectionError(Exception):
    """Raised when LLM API connection fails."""
    pass


@dataclass
class LLMHealthStatus:
    """Result of LLM health check."""
    status: str  # "ok" | "error" | "unconfigured"
    model: Optional[str] = None
    message: Optional[str] = None
    
    def is_healthy(self) -> bool:
        return self.status == "ok"


def get_llm_api_key(allow_missing: bool = False) -> Optional[str]:
    """
    Get LLM API key from environment.
    
    Args:
        allow_missing: If False, raises ConfigurationError on missing key
        
    Returns:
        API key string or None if allow_missing=True and key not set
        
    Raises:
        ConfigurationError: If key is missing/placeholder and allow_missing=False
    """
    key = os.environ.get("GOOGLE_API_KEY", "")
    
    # Check for placeholder values
    placeholders = ["your_google_api_key_here", "YOUR_API_KEY", ""]
    
    if key in placeholders:
        if allow_missing:
            return None
        raise ConfigurationError(
            "GOOGLE_API_KEY not set or is placeholder. "
            "Get your key at https://aistudio.google.com/"
        )
    
    return key


def validate_llm_connectivity(timeout: float = 10.0) -> LLMHealthStatus:
    """
    Test LLM API connectivity with a minimal call.
    
    Args:
        timeout: Request timeout in seconds
        
    Returns:
        LLMHealthStatus with result
    """
    try:
        key = get_llm_api_key(allow_missing=True)
        if not key:
            return LLMHealthStatus(
                status="unconfigured",
                message="GOOGLE_API_KEY not set"
            )
        
        # Use google.genai (new library) like curator.py does
        from google import genai
        client = genai.Client(api_key=key)
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Reply with only the word 'ok'"
        )
        
        if response.text:
            return LLMHealthStatus(
                status="ok",
                model="gemini-2.0-flash",
                message=f"Connected (response: {response.text.strip()[:20]})"
            )
        else:
            return LLMHealthStatus(
                status="error",
                message="Empty response from API"
            )
            
    except ConfigurationError as e:
        return LLMHealthStatus(status="unconfigured", message=str(e))
    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
            return LLMHealthStatus(
                status="error",
                message="API key is invalid - check your GOOGLE_API_KEY"
            )
        return LLMHealthStatus(status="error", message=error_msg)


def require_llm_connection() -> str:
    """
    Require valid LLM connection or raise.
    
    Use this at startup of LLM-dependent features.
    
    Returns:
        API key if valid
        
    Raises:
        LLMConnectionError: If LLM is not available
    """
    status = validate_llm_connectivity()
    
    if status.status == "ok":
        return get_llm_api_key()
    
    raise LLMConnectionError(
        f"LLM not available: {status.message}. "
        "Set GOOGLE_API_KEY in .env file."
    )
