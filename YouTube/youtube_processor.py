#!/usr/bin/env python3
"""Fetch transcripts from YouTube videos."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi

from common import extract_video_id


class VideoProcessor:
    """Fetch YouTube transcripts with basic language fallback."""

    def __init__(self) -> None:
        self.api = YouTubeTranscriptApi()

    def _fetch_with_language(self, video_id: str, languages: list[str] | None) -> str | None:
        try:
            if languages is None:
                transcript = self.api.fetch(video_id)
            else:
                transcript = self.api.fetch(video_id, languages=languages)
            return " ".join(snippet.text for snippet in transcript)
        except TypeError:
            # Older library versions may not support `languages` in fetch().
            if languages is None:
                raise
            transcript = self.api.fetch(video_id)
            return " ".join(snippet.text for snippet in transcript)

    def extract_text(self, video_id: str) -> Optional[str]:
        """Fetch clean transcript text from video."""
        attempts = [None, ["en"], ["en-US", "en"], ["en-GB", "en"]]
        for languages in attempts:
            try:
                return self._fetch_with_language(video_id, languages)
            except Exception as exc:
                if languages is attempts[-1]:
                    print(f"Transcript error for {video_id}: {exc}", file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch YouTube video transcript text")
    parser.add_argument("video_id", help="YouTube video ID or URL")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args()

    try:
        video_id = extract_video_id(args.video_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    processor = VideoProcessor()
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
