#!/usr/bin/env python3
"""All-in-one pipeline: monitor channels, fetch transcripts, summarize."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import timedelta
from typing import Dict, List, Optional

import feedparser
from youtube_transcript_api import YouTubeTranscriptApi

from channels import DEFAULT_CHANNELS
from common import ensure_directory, parse_published_datetime, utc_now

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "pipeline.db")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "memory")


class YouTubePipeline:
    """Full YouTube monitoring and processing pipeline."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.api = YouTubeTranscriptApi()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                title TEXT NOT NULL,
                published TEXT,
                transcript TEXT,
                summary TEXT,
                processed_at TEXT,
                status TEXT DEFAULT 'pending'
            )
            """
        )
        conn.commit()
        conn.close()

    def get_db_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def check_channels(self, channels: List[Dict], hours: int = 24) -> List[Dict]:
        """Check channels for new, not-yet-completed videos."""
        cutoff = utc_now() - timedelta(hours=hours)
        new_videos: list[dict] = []
        seen: set[str] = set()
        conn = self.get_db_connection()

        try:
            for channel in channels:
                try:
                    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel['id']}"
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:5]:
                        video_id = getattr(entry, "yt_videoid", None)
                        if not video_id or video_id in seen:
                            continue
                        seen.add(video_id)

                        row = conn.execute("SELECT status FROM videos WHERE video_id = ?", (video_id,)).fetchone()
                        if row and row[0] == "done":
                            continue

                        published_raw = getattr(entry, "published", "")
                        published_at = parse_published_datetime(published_raw)
                        if published_at and published_at < cutoff:
                            continue

                        new_videos.append(
                            {
                                "id": video_id,
                                "title": getattr(entry, "title", "(untitled)"),
                                "channel": channel["name"],
                                "url": getattr(entry, "link", f"https://youtube.com/watch?v={video_id}"),
                                "published": published_raw[:19] if published_raw else "",
                            }
                        )
                except Exception as exc:
                    print(f"Error checking {channel['name']}: {exc}", file=sys.stderr)
        finally:
            conn.close()
        return new_videos

    def fetch_transcript(self, video_id: str) -> Optional[str]:
        """Fetch video transcript."""
        try:
            transcript = self.api.fetch(video_id)
            return " ".join(snippet.text for snippet in transcript)
        except Exception as exc:
            print(f"Transcript error for {video_id}: {exc}", file=sys.stderr)
            return None

    def generate_summary(self, transcript: str, max_length: int = 500) -> str:
        """Generate simple extractive summary from transcript."""
        sentences = [sentence.strip() for sentence in transcript.split(". ") if sentence.strip()]
        if len(sentences) <= 3:
            return transcript[:max_length]

        summary_parts = sentences[:2]
        if len(sentences) > 4:
            summary_parts.append(sentences[len(sentences) // 2])

        summary = ". ".join(summary_parts)
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(" ", 1)[0] + "..."
        return summary

    def process_video(self, video: Dict) -> Dict:
        """Process a single video: transcript + summary."""
        video_id = video["id"]
        conn = self.get_db_connection()
        row = conn.execute(
            "SELECT transcript, summary, status FROM videos WHERE video_id = ?",
            (video_id,),
        ).fetchone()

        if row and row[2] == "done":
            conn.close()
            return {"status": "already_done", "video_id": video_id}

        transcript = self.fetch_transcript(video_id)
        if not transcript:
            conn.execute(
                """
                INSERT OR REPLACE INTO videos (video_id, channel, title, published, status, processed_at)
                VALUES (?, ?, ?, ?, 'failed', ?)
                """,
                (video_id, video["channel"], video["title"], video.get("published"), utc_now().isoformat()),
            )
            conn.commit()
            conn.close()
            return {"status": "failed", "video_id": video_id}

        summary = self.generate_summary(transcript)
        conn.execute(
            """
            INSERT OR REPLACE INTO videos
                (video_id, channel, title, published, transcript, summary, processed_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'done')
            """,
            (
                video_id,
                video["channel"],
                video["title"],
                video.get("published"),
                transcript,
                summary,
                utc_now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return {
            "status": "done",
            "video_id": video_id,
            "title": video["title"],
            "channel": video["channel"],
            "summary": summary,
            "transcript_length": len(transcript),
        }

    def run(self, channels: List[Dict] | None = None, hours: int = 24, output_file: str | None = None) -> Dict:
        """Run full pipeline."""
        channels = channels or DEFAULT_CHANNELS
        print(f"Checking {len(channels)} channels...")
        new_videos = self.check_channels(channels, hours)
        print(f"Found {len(new_videos)} new videos")
        if not new_videos:
            return {"new_videos": 0, "processed": 0, "failed": 0, "videos": []}

        results = []
        processed = 0
        failed = 0
        for video in new_videos:
            result = self.process_video(video)
            if result["status"] == "done":
                processed += 1
                results.append(result)
            elif result["status"] == "failed":
                failed += 1

        if output_file:
            ensure_directory(OUTPUT_DIR)
            output_path = os.path.join(OUTPUT_DIR, output_file)
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write("# YouTube Pipeline Results\n")
                handle.write(f"Generated: {utc_now().isoformat()}\n\n")
                for result in results:
                    handle.write(f"## {result['channel']}: {result['title']}\n")
                    handle.write(f"- URL: https://youtube.com/watch?v={result['video_id']}\n")
                    handle.write(f"- Summary: {result['summary']}\n\n")
            print(f"Results saved to {output_path}")

        return {"new_videos": len(new_videos), "processed": processed, "failed": failed, "videos": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Pipeline: Monitor -> Transcript -> Summarize")
    parser.add_argument("--hours", "-H", type=int, default=24, help="Look back N hours")
    parser.add_argument("--output", "-o", default="youtube-pipeline.md", help="Output file name")
    parser.add_argument("--list-channels", "-l", action="store_true", help="List configured channels")
    parser.add_argument("--dry-run", action="store_true", help="Check for new videos without processing")
    args = parser.parse_args()

    if args.list_channels:
        print("Configured channels:")
        for channel in DEFAULT_CHANNELS:
            print(f"  - {channel['name']}: {channel['id']}")
        return

    pipeline = YouTubePipeline()
    if args.dry_run:
        new_videos = pipeline.check_channels(DEFAULT_CHANNELS, args.hours)
        print(f"Found {len(new_videos)} new videos:")
        for video in new_videos:
            print(f"  - {video['channel']}: {video['title']}")
        return

    result = pipeline.run(DEFAULT_CHANNELS, args.hours, args.output)
    print("\n=== Pipeline Results ===")
    print(f"New videos: {result['new_videos']}")
    print(f"Processed: {result['processed']}")
    print(f"Failed: {result['failed']}")
    if result["videos"]:
        print("\nProcessed videos:")
        for video in result["videos"]:
            print(f"  - {video['title'][:50]}...")


if __name__ == "__main__":
    main()
