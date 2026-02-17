#!/usr/bin/env python3
"""Generate summaries from YouTube video transcripts."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi

from common import configure_logging, extract_video_id, retry_call, utc_now

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class VideoSummarizer:
    """Generate summaries from YouTube video transcripts."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.api = YouTubeTranscriptApi()
        self.logger = logger or logging.getLogger("yt_summarizer")

    def get_transcript(self, video_id: str) -> Optional[str]:
        """Fetch clean transcript text from video."""
        try:
            transcript = retry_call(
                lambda: self.api.fetch(video_id),
                action_name=f"transcript fetch {video_id}",
                logger=self.logger,
            )
            return " ".join(snippet.text for snippet in transcript)
        except Exception as exc:
            self.logger.error("Error fetching transcript for %s: %s", video_id, exc)
            return None

    def generate_summary(self, transcript: str, max_length: int = 500) -> str:
        """Generate an extractive summary from transcript text."""
        sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(transcript) if sentence.strip()]
        if len(sentences) <= 3:
            return transcript[:max_length]

        summary_parts = sentences[:2]
        if len(sentences) > 4:
            summary_parts.append(sentences[len(sentences) // 2])
        if len(sentences) > 6:
            summary_parts.append(sentences[-2])

        summary = " ".join(summary_parts)
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(" ", 1)[0] + "..."
        return summary

    def summarize_video(self, video_id: str, max_length: int = 500) -> dict:
        """Fetch transcript and build summary metadata."""
        transcript = self.get_transcript(video_id)
        if not transcript:
            return {"error": f"Could not fetch transcript for {video_id}", "video_id": video_id}

        summary = self.generate_summary(transcript, max_length=max_length)
        return {
            "video_id": video_id,
            "transcript_length": len(transcript),
            "summary_length": len(summary),
            "summary": summary,
            "generated_at": utc_now().isoformat(),
        }


def render_markdown(payload: dict) -> str:
    """Render markdown output."""
    return (
        f"# Video Summary: {payload['video_id']}\n\n"
        f"## Summary\n{payload['summary']}\n\n"
        "## Stats\n"
        f"- Transcript length: {payload['transcript_length']} chars\n"
        f"- Summary length: {payload['summary_length']} chars\n"
        f"- Generated: {payload['generated_at']}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate summaries from YouTube video transcripts")
    parser.add_argument("video_id", help="YouTube video ID or URL")
    parser.add_argument("--format", "-f", choices=["text", "json", "markdown"], default="text", help="Output format")
    parser.add_argument("--length", "-l", type=int, default=500, help="Maximum summary length")
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

    summarizer = VideoSummarizer(logger=logging.getLogger("yt_summarizer"))
    result = summarizer.summarize_video(video_id, max_length=args.length)
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(render_markdown(result))
    else:
        print(result["summary"])


if __name__ == "__main__":
    main()
