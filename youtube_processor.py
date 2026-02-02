#!/usr/bin/env python3
"""
YouTube Video Processor
Connects _transcripts.py to LLM summarization and Telegram delivery
"""

import sys
import os
from typing import Optional
from datetime import datetime

# Import Kamil's transcript library
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _transcripts import YouTubeTranscriptApi, TranscriptError

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")


class VideoProcessor:
    """Fetch YouTube transcripts and summarize with LLM."""
    
    def __init__(self):
        self.api = YouTubeTranscriptApi()
    
    def extract_text(self, video_id: str) -> Optional[str]:
        """Fetch clean transcript text from video."""
        try:
            transcript = self.api.get_transcript(video_id, languages=["en"])
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
        """Integrate with Anthropic Claude (recommended)."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except ImportError:
            import openai
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )
            return response.choices[0].message.content
    
    def send_to_telegram(self, summary: str, video_url: str, title: str):
        """Deliver formatted summary to Telegram."""
        import requests
        
        message = f"""🎬 *{title[:60]}...*

{summary[:3800]}

🔗 [Watch Video]({video_url})"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        
        response = requests.post(url, json=payload)
        return response.json()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python youtube_processor.py <video_id> [title] [channel]")
        sys.exit(1)
    
    video_id = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "YouTube Video"
    channel = sys.argv[3] if len(sys.argv) > 3 else "Unknown Channel"
    
    processor = VideoProcessor()
    text = processor.extract_text(video_id)
    
    if text:
        summary = processor.summarize(text, title, channel)
        processor.send_to_telegram(summary, f"https://youtube.com/watch?v={video_id}", title)
        print("✓ Summary sent to Telegram")
    else:
        print("✗ Could not fetch transcript")
