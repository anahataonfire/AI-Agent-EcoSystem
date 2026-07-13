"""
Telegram Alerter

Sends weather trading opportunities to Telegram.
"""

import json
import logging
import os
from typing import List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from pathlib import Path

from config import TELEGRAM_CONFIG, WeatherOpportunity

# Try to load .env if dotenv is available
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).parent.parent.parent
    load_dotenv(_project_root / ".env", override=True)
except ImportError:
    pass  # dotenv not available, rely on environment variables

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """
    Sends alerts to Telegram via Bot API.
    
    Setup:
    1. Message @BotFather on Telegram
    2. Create bot with /newbot
    3. Get token and add to .env as TELEGRAM_BOT_TOKEN
    4. Start chat with your bot
    5. Get chat ID (message bot, then visit:
       https://api.telegram.org/bot<TOKEN>/getUpdates)
    6. Add chat ID to .env as TELEGRAM_CHAT_ID
    """
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get(TELEGRAM_CONFIG["env_token_key"])
        self.chat_id = chat_id or os.environ.get(TELEGRAM_CONFIG["env_chat_id_key"])
        
        if not self.token:
            logger.warning(
                f"Telegram bot token not set. "
                f"Set {TELEGRAM_CONFIG['env_token_key']} in .env"
            )
        if not self.chat_id:
            logger.warning(
                f"Telegram chat ID not set. "
                f"Set {TELEGRAM_CONFIG['env_chat_id_key']} in .env"
            )
    
    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.token and self.chat_id)
    
    def _make_request(self, method: str, data: dict) -> Optional[dict]:
        """Make POST request to Telegram Bot API."""
        if not self.is_configured:
            logger.error("Telegram not configured")
            return None
        
        url = f"{self.BASE_URL}{self.token}/{method}"
        
        try:
            req = Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                if not result.get("ok"):
                    logger.error(f"Telegram API error: {result}")
                return result
                
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.error(f"Telegram request failed: {e}")
            return None
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message to the configured chat.
        
        Args:
            text: Message text (supports HTML formatting)
            parse_mode: "HTML" or "Markdown"
            
        Returns:
            True if successful
        """
        result = self._make_request("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,  # Don't show link previews
        })
        
        return result is not None and result.get("ok", False)
    
    def send_opportunity_alert(self, opportunity: WeatherOpportunity) -> bool:
        """
        Send a formatted opportunity alert.
        
        Uses the WeatherOpportunity.to_alert_message() format.
        """
        message = opportunity.to_alert_message()
        return self.send_message(message, parse_mode="HTML")
    
    def send_batch_alert(self, opportunities: List[WeatherOpportunity]) -> int:
        """
        Send alerts for multiple opportunities.
        
        Returns number of successfully sent alerts.
        """
        if not opportunities:
            return 0
        
        # Send header
        header = (
            f"🌡️ <b>Weather Trading Scan Complete</b>\n"
            f"Found {len(opportunities)} opportunities with edge ≥15%\n"
            f"{'='*30}"
        )
        self.send_message(header)
        
        sent = 0
        for opp in opportunities:
            if self.send_opportunity_alert(opp):
                sent += 1
        
        return sent
    
    def send_no_opportunities_message(self) -> bool:
        """Send message when no opportunities found."""
        message = (
            "📊 <b>Weather Scan Complete</b>\n\n"
            "No opportunities found with edge ≥15%.\n"
            "Will scan again in 30 minutes."
        )
        return self.send_message(message)
    
    def send_error_message(self, error: str) -> bool:
        """Send error notification."""
        message = f"⚠️ <b>Weather Scanner Error</b>\n\n{error}"
        return self.send_message(message)


# Module-level singleton
_alerter: Optional[TelegramAlerter] = None

def get_alerter() -> TelegramAlerter:
    """Get or create the singleton alerter instance."""
    global _alerter
    if _alerter is None:
        _alerter = TelegramAlerter()
    return _alerter


def test_telegram_connection() -> bool:
    """Test if Telegram is properly configured."""
    alerter = get_alerter()
    if not alerter.is_configured:
        print("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False
    
    success = alerter.send_message("🧪 Weather Trading Bot - Connection Test Successful!")
    if success:
        print("✅ Telegram connection successful!")
    else:
        print("❌ Failed to send Telegram message")
    
    return success
