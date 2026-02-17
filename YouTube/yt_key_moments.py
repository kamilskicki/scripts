#!/usr/bin/env python3
"""
YouTube Key Moments Extractor — v1.0
Extracts key moments with timestamps from YouTube video transcripts.
"""

import argparse
import json
import logging
import re
import sys

from youtube_transcript_api import YouTubeTranscriptApi

from common import configure_logging, extract_video_id, retry_call


class KeyMomentsExtractor:
    """Extract key moments with timestamps from video transcripts."""
    
    # Keywords that often indicate important moments
    IMPORTANT_PATTERNS = [
        r'\bimportant\b',
        r'\bkey\b',
        r'\bmain\b',
        r'\bcrucial\b',
        r'\bessential\b',
        r'\bkey takeaway\b',
        r'\bsummary\b',
        r'\bconclusion\b',
        r'\bfinally\b',
        r'\bin conclusion\b',
        r'\bto sum up\b',
        r'\bthe best\b',
        r'\bworst\b',
        r'\btop \d+\b',
        r'\bnumber \d+\b',
        r'\bfirst\b.*\bsecond\b',
        r'\bone\b.*\btwo\b.*\bthree\b',
        r'\bstep \d+\b',
        r'\bhow to\b',
        r'\bway to\b',
        r'\btutorial\b',
        r'\bguide\b',
        r'\btips?\b',
        r'\btrick\b',
        r'\bhack\b',
    ]
    
    def __init__(self, logger: logging.Logger | None = None):
        self.api = YouTubeTranscriptApi()
        self.logger = logger or logging.getLogger("yt_key_moments")
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.IMPORTANT_PATTERNS]
    
    def get_transcript_with_timestamps(self, video_id: str) -> list[dict] | None:
        """Fetch transcript with timestamps."""
        try:
            transcript = retry_call(
                lambda: self.api.fetch(video_id),
                action_name=f"transcript fetch {video_id}",
                logger=self.logger,
            )
            return [
                {
                    "start": snippet.start,
                    "text": snippet.text,
                }
                for snippet in transcript
            ]
        except Exception as exc:
            self.logger.error("Error fetching transcript for %s: %s", video_id, exc)
            return None
    
    def find_key_moments(
        self, 
        transcript: list[dict], 
        num_moments: int = 10,
        min_duration: int = 30
    ) -> list[dict]:
        """Find key moments in the transcript."""
        moments = []
        
        for i, snippet in enumerate(transcript):
            text = snippet["text"]
            score = 0
            
            # Check for important patterns
            for pattern in self.patterns:
                if pattern.search(text):
                    score += 1
            
            # Boost moments at the beginning and end
            if i < 3:  # First 3 snippets
                score += 2
            elif i > len(transcript) - 4:  # Last 3 snippets
                score += 1
            
            # Longer snippets often contain more info
            if len(text) > 50:
                score += 0.5
            
            if score >= 1:
                moments.append({
                    "start": snippet["start"],
                    "text": text,
                    "score": score
                })
        
        # Sort by score and take top N
        moments.sort(key=lambda x: x["score"], reverse=True)
        
        # Filter to minimum duration between moments
        filtered = []
        last_start = -1000
        
        for moment in moments:
            if moment["start"] - last_start >= min_duration:
                filtered.append(moment)
                last_start = moment["start"]
            
            if len(filtered) >= num_moments:
                break
        
        # Sort by timestamp
        filtered.sort(key=lambda x: x["start"])
        
        return filtered
    
    def format_timestamp(self, seconds: float) -> str:
        """Format seconds to MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def extract_moments(self, video_id: str, num_moments: int = 10) -> dict:
        """Main method to extract key moments."""
        transcript = self.get_transcript_with_timestamps(video_id)
        
        if not transcript:
            return {
                "error": f"Could not fetch transcript for {video_id}",
                "video_id": video_id
            }
        
        moments = self.find_key_moments(transcript, num_moments)
        
        # Add formatted timestamps
        for moment in moments:
            moment["timestamp"] = self.format_timestamp(moment["start"])
        
        return {
            "video_id": video_id,
            "total_snippets": len(transcript),
            "moments_found": len(moments),
            "moments": moments
        }


def main():
    parser = argparse.ArgumentParser(
        description="Extract key moments with timestamps from YouTube videos"
    )
    parser.add_argument("video_id", help="YouTube video ID or URL")
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=10,
        help="Number of key moments to extract"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    
    args = parser.parse_args()

    try:
        configure_logging(verbose=args.verbose, quiet=args.quiet)
    except ValueError as exc:
        parser.error(str(exc))
    
    try:
        video_id = extract_video_id(args.video_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    
    extractor = KeyMomentsExtractor(logger=logging.getLogger("yt_key_moments"))
    result = extractor.extract_moments(video_id, args.count)
    
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        md = f"# Key Moments: {video_id}\n\n"
        md += f"Found {result['moments_found']} key moments\n\n"
        
        for i, moment in enumerate(result["moments"], 1):
            md += f"## {i}. [{moment['timestamp']}](https://youtube.com/watch?v={video_id}&t={int(moment['start'])})\n\n"
            md += f"{moment['text']}\n\n"
        
        print(md)
    else:
        print(f"Key Moments for: {video_id}\n")
        print(f"Found {result['moments_found']} moments\n")
        
        for i, moment in enumerate(result["moments"], 1):
            print(f"{i}. [{moment['timestamp']}] {moment['text'][:100]}...")
            print()


if __name__ == "__main__":
    main()
