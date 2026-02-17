#!/usr/bin/env python3
"""Fetch transcripts from YouTube videos."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi

from common import configure_logging, extract_video_id, retry_call


class VideoProcessor:
    """Fetch YouTube transcripts with basic language fallback."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.api = YouTubeTranscriptApi()
        self.logger = logger or logging.getLogger("youtube_processor")

    def _fetch_with_language(self, video_id: str, languages: list[str] | None) -> str | None:
        try:
            if languages is None:
                transcript = retry_call(
                    lambda: self.api.fetch(video_id),
                    action_name=f"transcript fetch {video_id}",
                    logger=self.logger,
                )
            else:
                transcript = retry_call(
                    lambda: self.api.fetch(video_id, languages=languages),
                    action_name=f"transcript fetch {video_id}",
                    logger=self.logger,
                )
            return " ".join(snippet.text for snippet in transcript)
        except TypeError:
            # Older library versions may not support `languages` in fetch().
            if languages is None:
                raise
            transcript = retry_call(
                lambda: self.api.fetch(video_id),
                action_name=f"transcript fetch {video_id}",
                logger=self.logger,
            )
            return " ".join(snippet.text for snippet in transcript)

    def extract_text(self, video_id: str) -> Optional[str]:
        """Fetch clean transcript text from video."""
        attempts = [None, ["en"], ["en-US", "en"], ["en-GB", "en"]]
        for languages in attempts:
            try:
                return self._fetch_with_language(video_id, languages)
            except Exception as exc:
                if languages is attempts[-1]:
                    self.logger.error("Transcript error for %s: %s", video_id, exc)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch YouTube video transcript text")
    parser.add_argument("video_id", help="YouTube video ID or URL")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
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

    processor = VideoProcessor(logger=logging.getLogger("youtube_processor"))
    text = processor.extract_text(video_id)
    if not text:
        print("No transcript available", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"video_id": video_id, "transcript": text}, ensure_ascii=False))
    else:
        print(text)


if __name__ == "__main__":
    main()
