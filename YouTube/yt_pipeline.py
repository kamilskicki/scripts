#!/usr/bin/env python3
"""All-in-one pipeline: monitor channels, fetch transcripts, summarize."""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from datetime import timedelta

from youtube_transcript_api import YouTubeTranscriptApi

from channels import DEFAULT_CHANNELS
from common import (
    configure_logging,
    ensure_directory,
    fetch_feed,
    parse_published_datetime,
    retry_call,
    utc_now,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "pipeline.db")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "memory")


class YouTubePipeline:
    """Full YouTube monitoring and processing pipeline."""

    def __init__(self, db_path: str = DB_PATH, logger: logging.Logger | None = None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger("yt_pipeline")
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

    def check_channels(self, channels: list[dict], hours: int = 24) -> list[dict]:
        """Check channels for new, not-yet-completed videos."""
        cutoff = utc_now() - timedelta(hours=hours)
        new_videos: list[dict] = []
        seen: set[str] = set()
        conn = self.get_db_connection()

        try:
            for channel in channels:
                try:
                    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel['id']}"
                    feed = fetch_feed(url, logger=self.logger)
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
                    self.logger.exception("Error checking %s: %s", channel["name"], exc)
        finally:
            conn.close()
        return new_videos

    def fetch_transcript(self, video_id: str) -> str | None:
        """Fetch video transcript."""
        try:
            transcript = retry_call(
                lambda: self.api.fetch(video_id),
                action_name=f"transcript fetch {video_id}",
                logger=self.logger,
            )
            return " ".join(snippet.text for snippet in transcript)
        except Exception as exc:
            self.logger.warning("Transcript error for %s: %s", video_id, exc)
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

    def process_video(self, video: dict) -> dict:
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

    def run(self, channels: list[dict] | None = None, hours: int = 24, output_file: str | None = None) -> dict:
        """Run full pipeline."""
        channels = channels or DEFAULT_CHANNELS
        self.logger.info("Checking %s channels...", len(channels))
        new_videos = self.check_channels(channels, hours)
        self.logger.info("Found %s new videos", len(new_videos))
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
            self.logger.info("Results saved to %s", output_path)

        return {"new_videos": len(new_videos), "processed": processed, "failed": failed, "videos": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Pipeline: Monitor -> Transcript -> Summarize")
    parser.add_argument("--hours", "-H", type=int, default=24, help="Look back N hours")
    parser.add_argument("--output", "-o", default="youtube-pipeline.md", help="Output file name")
    parser.add_argument("--list-channels", "-l", action="store_true", help="List configured channels")
    parser.add_argument("--dry-run", action="store_true", help="Check for new videos without processing")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    args = parser.parse_args()

    try:
        configure_logging(verbose=args.verbose, quiet=args.quiet)
    except ValueError as exc:
        parser.error(str(exc))

    if args.list_channels:
        print("Configured channels:")
        for channel in DEFAULT_CHANNELS:
            print(f"  - {channel['name']}: {channel['id']}")
        return

    pipeline = YouTubePipeline(logger=logging.getLogger("yt_pipeline"))
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
