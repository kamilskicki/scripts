#!/usr/bin/env python3
"""
YouTube Video Processor
Fetches transcripts, summarizes with LLM, and sends to Telegram.
"""

import sys
import os
import re
import time
from typing import Optional, List

from .transcripts import YouTubeTranscriptApi, TranscriptError


# =============================================================================
# Configuration
# =============================================================================

def _get_required_env(name: str, required_for: str = "this script") -> str:
    """Get required environment variable or exit with helpful error."""
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required for {required_for}", file=sys.stderr)
        print(f"Set it with: export {name}='your-value'", file=sys.stderr)
        sys.exit(1)
    return value


# Lazy-loaded config (only checked when actually needed)
def get_telegram_config() -> tuple:
    return (
        _get_required_env("TELEGRAM_BOT_TOKEN", "Telegram notifications"),
        _get_required_env("TELEGRAM_CHAT_ID", "Telegram notifications"),
    )


LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")


# =============================================================================
# Telegram Helpers
# =============================================================================

def escape_markdown(text: str) -> str:
    """Escape special Markdown characters to prevent formatting errors."""
    # Characters that need escaping in Telegram Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text


def send_telegram_message(
    text: str,
    parse_mode: str = "Markdown",
    max_retries: int = 3,
    disable_preview: bool = False,
) -> dict:
    """Send message to Telegram with retry logic."""
    import requests
    
    bot_token, chat_id = get_telegram_config()
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get("ok"):
                return result
            
            # If markdown fails, try plain text
            if "can't parse" in str(result.get("description", "")).lower():
                payload["parse_mode"] = None
                continue
                
            # Rate limited - wait and retry
            if response.status_code == 429:
                retry_after = result.get("parameters", {}).get("retry_after", 5)
                time.sleep(retry_after)
                continue
                
            return result
            
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
    
    return {"ok": False, "description": "Max retries exceeded"}


# =============================================================================
# Video Processor
# =============================================================================

class VideoProcessor:
    """Fetch YouTube transcripts and summarize with LLM."""
    
    def __init__(self):
        self.api = YouTubeTranscriptApi()
    
    def extract_text(self, video_id: str, languages: Optional[List[str]] = None) -> Optional[str]:
        """Fetch clean transcript text from video."""
        if languages is None:
            languages = ["en"]
        try:
            transcript = self.api.get_transcript(video_id, languages=languages)
            return " ".join([snippet.text for snippet in transcript])
        except TranscriptError as e:
            print(f"Transcript error for {video_id}: {e}")
            return None
    
    def summarize(self, text: str, title: str, channel: str) -> str:
        """Send to LLM for business-focused summary."""
        max_chars = 12000
        if len(text) > max_chars:
            text = text[:max_chars] + "... [truncated]"
        
        prompt = f"""Analyze this YouTube video transcript and provide a structured summary focused on actionable business insights.

TITLE: {title}
CHANNEL: {channel}

TRANSCRIPT:
{text}

FORMAT:
🎯 KEY POINTS (3-5 bullets):
• 

💼 BUSINESS IMPLICATIONS:
• 

📊 MARKETING TAKEAWAYS:
• 

⚡ ACTION ITEMS:
• 

PRIORITY (1-10):
"""
        return self._call_llm(prompt)
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API (Anthropic preferred, OpenAI fallback)."""
        # Try Anthropic first
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                response = client.messages.create(
                    model=LLM_MODEL,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            except ImportError:
                pass  # Fall through to OpenAI
        
        # Fallback to OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )
            return response.choices[0].message.content
        
        raise RuntimeError(
            "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable."
        )
    
    def send_to_telegram(self, summary: str, video_url: str, title: str) -> dict:
        """Deliver formatted summary to Telegram."""
        # Escape title for markdown safety
        safe_title = title[:60]
        if len(title) > 60:
            safe_title += "..."
        
        message = f"""🎬 *{safe_title}*

{summary[:3800]}

🔗 [Watch Video]({video_url})"""
        
        return send_telegram_message(message, disable_preview=False)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m youtube_monitor.processor <video_id> [title] [channel]")
        sys.exit(1)
    
    video_id = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "YouTube Video"
    channel = sys.argv[3] if len(sys.argv) > 3 else "Unknown Channel"
    
    processor = VideoProcessor()
    text = processor.extract_text(video_id)
    
    if text:
        summary = processor.summarize(text, title, channel)
        result = processor.send_to_telegram(summary, f"https://youtube.com/watch?v={video_id}", title)
        if result.get("ok"):
            print("✓ Summary sent to Telegram")
        else:
            print(f"✗ Telegram error: {result.get('description', 'Unknown error')}")
    else:
        print("✗ Could not fetch transcript")
