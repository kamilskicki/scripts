#!/usr/bin/env python3
"""Daily digest generator for YouTube videos."""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from datetime import timedelta
from typing import Dict, List

from channels import DEFAULT_CHANNELS
from common import configure_logging, ensure_directory, fetch_feed, parse_published_datetime, utc_now

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "pipeline.db")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "memory")


class YouTubeDigest:
    """Generate daily digests from YouTube channels."""

    def __init__(self, db_path: str = DB_PATH, logger: logging.Logger | None = None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger("yt_digest")

    def get_recent_videos(self, days: int = 1) -> List[Dict]:
        """Get videos from last N days."""
        videos: list[dict] = []
        cutoff = utc_now() - timedelta(days=days)
        seen: set[str] = set()

        for channel in DEFAULT_CHANNELS:
            try:
                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel['id']}"
                feed = fetch_feed(url, logger=self.logger)
                for entry in feed.entries[:10]:
                    video_id = getattr(entry, "yt_videoid", None)
                    if not video_id or video_id in seen:
                        continue
                    published_raw = getattr(entry, "published", "")
                    published_at = parse_published_datetime(published_raw)
                    if not published_at or published_at < cutoff:
                        continue
                    seen.add(video_id)
                    videos.append(
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

        videos.sort(key=lambda video: video.get("published", ""), reverse=True)
        return videos

    def get_video_metadata_map(self, video_ids: List[str]) -> Dict[str, Dict]:
        """Get metadata for a batch of videos from pipeline DB."""
        if not video_ids:
            return {}

        placeholders = ",".join("?" for _ in video_ids)
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            f"""
            SELECT video_id, title, channel, transcript, summary
            FROM videos
            WHERE status = 'done' AND video_id IN ({placeholders})
            """,
            video_ids,
        ).fetchall()
        conn.close()

        metadata: dict[str, dict] = {}
        for row in rows:
            metadata[row[0]] = {
                "title": row[1],
                "channel": row[2],
                "transcript": row[3],
                "summary": row[4],
            }
        return metadata

    def generate_digest(self, days: int = 1, include_transcripts: bool = False, output_file: str | None = None) -> str:
        """Generate digest markdown."""
        videos = self.get_recent_videos(days)
        metadata_map = self.get_video_metadata_map([video["id"] for video in videos])

        digest = (
            "# YouTube Daily Digest\n\n"
            f"**Generated:** {utc_now().strftime('%Y-%m-%d %H:%M UTC')}  \n"
            f"**Period:** Last {days} day(s)  \n"
            f"**Sources:** {len(DEFAULT_CHANNELS)} channels\n\n"
            "---\n\n"
        )

        if not videos:
            digest += "No new videos in the specified period.\n"
            return digest

        by_channel: dict[str, list[dict]] = {}
        for video in videos:
            by_channel.setdefault(video["channel"], []).append(video)

        for channel, channel_videos in by_channel.items():
            digest += f"## {channel}\n\n"
            for video in channel_videos:
                digest += f"### [{video['title']}]({video['url']})\n\n"
                digest += f"**Published:** {video['published']}\n\n"

                metadata = metadata_map.get(video["id"])
                if metadata and metadata.get("summary"):
                    digest += f"**Summary:** {metadata['summary']}\n\n"

                if include_transcripts and metadata and metadata.get("transcript"):
                    digest += f"**Transcript Preview:** {metadata['transcript'][:200]}...\n\n"

                digest += "---\n\n"

        summaries_count = sum(1 for video in videos if metadata_map.get(video["id"], {}).get("summary"))
        digest += (
            "## Stats\n\n"
            f"- **Total videos:** {len(videos)}\n"
            f"- **Channels with new content:** {len(by_channel)}\n"
            f"- **Videos with summaries:** {summaries_count}\n\n"
        )

        if output_file:
            ensure_directory(OUTPUT_DIR)
            output_path = os.path.join(OUTPUT_DIR, output_file)
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(digest)
            self.logger.info("Digest saved to %s", output_path)
        return digest

    def quick_summary(self, days: int = 1) -> str:
        """Generate quick summary (without full details)."""
        videos = self.get_recent_videos(days)
        if not videos:
            return f"No new videos in the last {days} day(s)."

        by_channel: dict[str, int] = {}
        for video in videos:
            by_channel[video["channel"]] = by_channel.get(video["channel"], 0) + 1

        lines = [f"YouTube Digest - Last {days} day(s):"]
        for channel, count in sorted(by_channel.items(), key=lambda item: -item[1]):
            lines.append(f"  {channel}: {count} new video(s)")
        lines.append(f"\nTotal: {len(videos)} videos from {len(by_channel)} channels")
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YouTube daily digest")
    parser.add_argument("--days", "-d", type=int, default=1, help="Number of days to look back")
    parser.add_argument("--output", "-o", default="youtube-digest.md", help="Output file name")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick summary only (no full details)")
    parser.add_argument("--transcripts", "-t", action="store_true", help="Include transcript previews")
    parser.add_argument("--list-channels", "-l", action="store_true", help="List configured channels")
    parser.add_argument("--no-save", action="store_true", help="Don't save to file, just print")
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

    digest = YouTubeDigest(logger=logging.getLogger("yt_digest"))
    if args.quick:
        print(digest.quick_summary(args.days))
        return

    output_file = None if args.no_save else args.output
    result = digest.generate_digest(args.days, args.transcripts, output_file)
    if args.no_save:
        print(result)
    else:
        print(result[:500] + "..." if len(result) > 500 else result)


if __name__ == "__main__":
    main()
