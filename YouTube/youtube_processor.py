#!/usr/bin/env python3
"""
YouTube Video Processor — v2
Fetches transcripts via youtube-transcript-api and outputs summaries.
No LLM integration needed — morning briefing cron handles summarization.
"""

import sys
import os
import json
from typing import Optional
from datetime import datetime

from youtube_transcript_api import YouTubeTranscriptApi


class VideoProcessor:
    """Fetch YouTube transcripts."""
    
    def __init__(self):
        self.api = YouTubeTranscriptApi()
    
    def extract_text(self, video_id: str) -> Optional[str]:
        """Fetch clean transcript text from video."""
        try:
            transcript = self.api.fetch(video_id)
            return " ".join([snippet.text for snippet in transcript])
        except Exception as e:
            # Try with different languages
            try:
                transcript = self.api.fetch(video_id)
                return " ".join([snippet.text for snippet in transcript])
            except Exception as e2:
                print(f"Transcript error for {video_id}: {e2}", file=sys.stderr)
                return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python youtube_processor.py <video_id>")
        sys.exit(1)
    
    video_id = sys.argv[1]
    processor = VideoProcessor()
    text = processor.extract_text(video_id)
    
    if text:
        print(text)
    else:
        print("No transcript available", file=sys.stderr)
        sys.exit(1)
