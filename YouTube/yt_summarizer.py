#!/usr/bin/env python3
"""
YouTube Video Summarizer — v1.0
Generates summaries from YouTube video transcripts.
"""

import sys
import json
import argparse
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi


class VideoSummarizer:
    """Generate summaries from YouTube video transcripts."""
    
    def __init__(self):
        self.api = YouTubeTranscriptApi()
    
    def get_transcript(self, video_id: str) -> Optional[str]:
        """Fetch clean transcript text from video."""
        try:
            transcript = self.api.fetch(video_id)
            return " ".join([snippet.text for snippet in transcript])
        except Exception as e:
            print(f"Error fetching transcript: {e}", file=sys.stderr)
            return None
    
    def generate_summary(self, transcript: str, max_length: int = 500) -> str:
        """Generate a summary from transcript.
        
        This is a simple extractive summary - extracts key sentences.
        For LLM-based summarization, integrate with OpenAI/Anthropic API.
        """
        # Simple extractive: take first and last sentences, plus middle key ones
        sentences = transcript.split('. ')
        
        if len(sentences) <= 3:
            return transcript[:max_length]
        
        # Take first 2, last 1, and sample from middle
        summary_parts = sentences[:2]
        
        # Add some middle sentences if available
        if len(sentences) > 4:
            middle_idx = len(sentences) // 2
            summary_parts.append(sentences[middle_idx])
        
        if len(sentences) > 6:
            summary_parts.append(sentences[-2])
        
        summary = '. '.join(summary_parts)
        
        # Trim to max length
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(' ', 1)[0] + '...'
        
        return summary
    
    def summarize_video(self, video_id: str, output_format: str = "text") -> dict:
        """Main method to summarize a video."""
        transcript = self.get_transcript(video_id)
        
        if not transcript:
            return {
                "error": f"Could not fetch transcript for {video_id}",
                "video_id": video_id
            }
        
        summary = self.generate_summary(transcript)
        
        result = {
            "video_id": video_id,
            "transcript_length": len(transcript),
            "summary": summary,
            "format": output_format
        }
        
        if output_format == "json":
            return result
        elif output_format == "markdown":
            return f"""# Video Summary: {video_id}

## Summary
{summary}

## Stats
- Transcript length: {len(transcript)} chars
- Generated: {result.get('timestamp', 'now')}
"""
        else:
            return summary


def main():
    parser = argparse.ArgumentParser(
        description="Generate summaries from YouTube video transcripts"
    )
    parser.add_argument("video_id", help="YouTube video ID or URL")
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--length", "-l",
        type=int,
        default=500,
        help="Maximum summary length"
    )
    
    args = parser.parse_args()
    
    # Extract video ID from URL if needed
    video_id = args.video_id
    if "youtube.com" in video_id or "youtu.be" in video_id:
        # Extract ID from URL
        if "youtu.be" in video_id:
            video_id = video_id.split("/")[-1].split("?")[0]
        elif "v=" in video_id:
            video_id = video_id.split("v=")[1].split("&")[0]
    
    summarizer = VideoSummarizer()
    result = summarizer.summarize_video(video_id, args.format)
    
    if isinstance(result, dict) and "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result)


if __name__ == "__main__":
    main()
