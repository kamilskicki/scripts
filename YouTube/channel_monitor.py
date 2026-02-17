#!/usr/bin/env python3
"""
Channel Monitor v2 — RSS-based YouTube channel watcher
Checks for new videos and outputs summaries for morning briefing.
"""

import feedparser
import sqlite3
import os
import sys
import json
from datetime import datetime, timedelta
from youtube_transcript_api import YouTubeTranscriptApi

DEFAULT_CHANNELS = [
    {"name": "In The World of AI", "id": "UCYwLV1gDwzGbg7jXQ52bVnQ"},
    {"name": "Matthew Berman", "id": "UCawZsQWqfGSbCI5yjkdVkTA"},
    {"name": "AI Revolution", "id": "UC5LTm52VaiV-5Q3C-txWVGQ"},
    {"name": "The AI Grid", "id": "UCSPkiRjFYpz-8DY-aF_1wRg"},
    {"name": "Julia McCoy", "id": "UCh0xoRjLeoMj1AjGmaSsoEQ"},
    {"name": "Theo (t3.gg)", "id": "UCtuO2h6OwDueF7h3p8DYYjQ"},
    {"name": "Wes Roth", "id": "UCqcbQf6yw5KzRoDDcZ_wBSw"},
    {"name": "AI Code King", "id": "UC0m81bQuthaQZmFbXEY9QSw"},
    {"name": "ThePrimeTime", "id": "UC8ENHE5xdFSwx71u3fDH5Xw"},
    {"name": "Fireship", "id": "UC2Xd-TjJByJyK2w1zNwY0zQ"},
    {"name": "NetworkChuck", "id": "UCOuGATIAbd2DvzJmUgXn2IQ"},
    {"name": "AI Master", "id": "UC0yHbz4OxdQFwmVX2BBQqLg"},
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "processed_videos.db")
OUTPUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "memory")

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            channel TEXT,
            title TEXT,
            published TEXT,
            has_transcript INTEGER DEFAULT 0,
            processed_at TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def get_new_videos(conn, channel, hours=24):
    """Get videos from last N hours that we haven't processed."""
    url = RSS_URL.format(channel['id'])
    feed = feedparser.parse(url)
    
    new_videos = []
    cutoff = datetime.now() - timedelta(hours=hours)
    
    for entry in feed.entries[:5]:
        video_id = entry.yt_videoid
        
        # Check if already processed
        cursor = conn.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,))
        if cursor.fetchone():
            continue
        
        # Check if recent enough
        try:
            pub_date = datetime.strptime(entry.published[:19], "%Y-%m-%dT%H:%M:%S")
            if pub_date < cutoff:
                continue
        except:
            pass  # If can't parse date, include it
        
        new_videos.append({
            "id": video_id,
            "title": entry.title,
            "channel": channel['name'],
            "url": entry.link,
            "published": entry.published[:16],
        })
    
    return new_videos


def fetch_transcript(video_id):
    """Try to get transcript."""
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        text = " ".join([s.text for s in transcript])
        return text[:8000]  # Cap at 8K chars
    except:
        return None


def run(hours=24, output_file=None):
    """Scan all channels, output new videos with transcripts."""
    conn = init_db()
    results = []
    
    for channel in DEFAULT_CHANNELS:
        try:
            new_videos = get_new_videos(conn, channel, hours)
            for video in new_videos:
                transcript = fetch_transcript(video['id'])
                video['transcript'] = transcript[:4000] if transcript else None
                video['has_transcript'] = bool(transcript)
                results.append(video)
                
                # Mark as processed
                conn.execute(
                    "INSERT OR REPLACE INTO videos VALUES (?, ?, ?, ?, ?, ?)",
                    (video['id'], video['channel'], video['title'], 
                     video['published'], int(video['has_transcript']), datetime.now())
                )
                conn.commit()
                
                status = "✅" if transcript else "⚠️ (no transcript)"
                print(f"{status} {video['channel']}: {video['title']}", file=sys.stderr)
                
        except Exception as e:
            print(f"❌ Error checking {channel['name']}: {e}", file=sys.stderr)
    
    # Output results
    if output_file:
        filepath = os.path.join(OUTPUT_DIR, output_file)
        with open(filepath, 'w') as f:
            f.write(f"# YouTube New Videos — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            if not results:
                f.write("No new videos in the last 24h.\n")
            else:
                for v in results:
                    f.write(f"## {v['channel']}: {v['title']}\n")
                    f.write(f"- URL: {v['url']}\n")
                    f.write(f"- Published: {v['published']}\n")
                    if v['transcript']:
                        f.write(f"- Transcript preview: {v['transcript'][:500]}...\n")
                    f.write("\n")
        print(f"\nSaved to {filepath}", file=sys.stderr)
    
    # Also output JSON to stdout for piping
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    conn.close()
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monitor YouTube channels for new videos")
    parser.add_argument("--hours", "-H", type=int, default=24, help="Look back N hours")
    parser.add_argument("--output", "-o", default=None, help="Save markdown to memory/[filename]")
    parser.add_argument("--list", "-l", action="store_true", help="List configured channels")
    args = parser.parse_args()
    
    if args.list:
        print("Configured channels:")
        for ch in DEFAULT_CHANNELS:
            print(f"  • {ch['name']}: {ch['id']}")
        sys.exit(0)
    
    run(hours=args.hours, output_file=args.output)
