#!/usr/bin/env python3
"""RSS-based YouTube channel watcher."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import timedelta

import feedparser
from youtube_transcript_api import YouTubeTranscriptApi

from channels import DEFAULT_CHANNELS
from common import ensure_directory, parse_published_datetime, utc_now

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "processed_videos.db")
OUTPUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "memory")
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


def init_db() -> sqlite3.Connection:
    """Initialize local state database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            title TEXT NOT NULL,
            published TEXT,
            has_transcript INTEGER DEFAULT 0,
            processed_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get_new_videos(conn: sqlite3.Connection, channel: dict, hours: int = 24) -> list[dict]:
    """Get unprocessed videos from the last N hours."""
    url = RSS_URL.format(channel["id"])
    feed = feedparser.parse(url)
    cutoff = utc_now() - timedelta(hours=hours)
    new_videos: list[dict] = []

    for entry in feed.entries[:5]:
        video_id = getattr(entry, "yt_videoid", None)
        if not video_id:
            continue

        cursor = conn.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,))
        if cursor.fetchone():
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

    return new_videos


def fetch_transcript(video_id: str, api: YouTubeTranscriptApi) -> str | None:
    """Try to fetch transcript text for a video."""
    try:
        transcript = api.fetch(video_id)
        text = " ".join(snippet.text for snippet in transcript)
        return text[:8000]
    except Exception as exc:
        print(f"Transcript unavailable for {video_id}: {exc}", file=sys.stderr)
        return None


def run(hours: int = 24, output_file: str | None = None) -> list[dict]:
    """Scan channels and print a JSON result set."""
    conn = init_db()
    api = YouTubeTranscriptApi()
    results: list[dict] = []

    for channel in DEFAULT_CHANNELS:
        try:
            new_videos = get_new_videos(conn, channel, hours)
            for video in new_videos:
                transcript = fetch_transcript(video["id"], api)
                video["transcript"] = transcript[:4000] if transcript else None
                video["has_transcript"] = bool(transcript)
                results.append(video)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO videos
                        (video_id, channel, title, published, has_transcript, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        video["id"],
                        video["channel"],
                        video["title"],
                        video["published"],
                        int(video["has_transcript"]),
                        utc_now().isoformat(),
                    ),
                )
                conn.commit()

                status = "OK" if transcript else "WARN(no transcript)"
                print(f"{status} {video['channel']}: {video['title']}", file=sys.stderr)
        except Exception as exc:
            print(f"Error checking {channel['name']}: {exc}", file=sys.stderr)

    if output_file:
        ensure_directory(OUTPUT_DIR)
        filepath = os.path.join(OUTPUT_DIR, output_file)
        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(f"# YouTube New Videos - {utc_now().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
            if not results:
                handle.write(f"No new videos in the last {hours}h.\n")
            else:
                for video in results:
                    handle.write(f"## {video['channel']}: {video['title']}\n")
                    handle.write(f"- URL: {video['url']}\n")
                    handle.write(f"- Published: {video['published']}\n")
                    if video["transcript"]:
                        handle.write(f"- Transcript preview: {video['transcript'][:500]}...\n")
                    handle.write("\n")
        print(f"Saved to {filepath}", file=sys.stderr)

    print(json.dumps(results, indent=2, ensure_ascii=False))
    conn.close()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor YouTube channels for new videos")
    parser.add_argument("--hours", "-H", type=int, default=24, help="Look back N hours")
    parser.add_argument("--output", "-o", default=None, help="Save markdown to memory/[filename]")
    parser.add_argument("--list", "-l", action="store_true", help="List configured channels")
    args = parser.parse_args()

    if args.list:
        print("Configured channels:")
        for channel in DEFAULT_CHANNELS:
            print(f"  - {channel['name']}: {channel['id']}")
        sys.exit(0)

    run(hours=args.hours, output_file=args.output)
