#!/usr/bin/env python3
"""
YouTube Digest — v1.0
Daily digest generator for YouTube videos (complements Morning Briefing).
"""

import os
import sys
import json
import argparse
import feedparser
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional


# Default channels to monitor
DEFAULT_CHANNELS = [
    {"name": "In The World of AI", "id": "UCYwLV1gDwzGbg7jXQ52bVnQ"},
    {"name": "Matthew Berman", "id": "UCawZsQWqfGSbCI5yjkdVkTA"},
    {"name": "AI Revolution", "id": "UC5LTm52VaiV-5Q3C-txWVGQ"},
    {"name": "The AI Grid", "id": "UCSPkiRjFYpz-8DY-aF_1wRg"},
    {"name": "Julia McCoy", "id": "UCh0xoRjLeoMj1AjGmaSsoEQ"},
    {"name": "Theo (t3.gg)", "id": "UCOuGATIAbd2DvzJmUgXn2IQ"},
    {"name": "Wes Roth", "id": "UCqcbQf6yw5KzRoDDcZ_wBSw"},
    {"name": "AI Code King", "id": "UC0m81bQuthaQZmFbXEY9QSw"},
    {"name": "ThePrimeTime", "id": "UC8ENHE5xdFSwx71u3fDH5Xw"},
    {"name": "Fireship", "id": "UC2Xd-TjJByJyK2w1zNwY0zQ"},
    {"name": "NetworkChuck", "id": "UCOuGATIAbd2DvzJmUgXn2IQ"},
    {"name": "AI Master", "id": "UC0yHbz4OxdQFwmVX2BBQqLg"},
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "pipeline.db")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "memory")


class YouTubeDigest:
    """Generate daily digests from YouTube channels."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def get_recent_videos(self, days: int = 1) -> List[Dict]:
        """Get videos from last N days."""
        videos = []
        
        for channel in DEFAULT_CHANNELS:
            try:
                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel['id']}"
                feed = feedparser.parse(url)
                
                cutoff = datetime.now() - timedelta(days=days)
                
                for entry in feed.entries[:10]:
                    try:
                        pub_date = datetime.strptime(
                            entry.published[:19], "%Y-%m-%dT%H:%M:%S"
                        )
                        if pub_date >= cutoff:
                            videos.append({
                                "id": entry.yt_videoid,
                                "title": entry.title,
                                "channel": channel['name'],
                                "url": entry.link,
                                "published": entry.published[:16]
                            })
                    except:
                        pass
            
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
        
        # Sort by published date (newest first)
        videos.sort(key=lambda x: x.get("published", ""), reverse=True)
        return videos
    
    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
        """Get video metadata."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT title, channel, transcript, summary 
               FROM videos WHERE video_id = ? AND status = 'done'""",
            (video_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "title": row[0],
                "channel": row[1],
                "transcript": row[2],
                "summary": row[3]
            }
        return None
    
    def generate_digest(
        self,
        days: int = 1,
        include_transcripts: bool = False,
        output_file: str = None
    ) -> str:
        """Generate digest markdown."""
        videos = self.get_recent_videos(days)
        
        digest = f"""# 📺 YouTube Daily Digest

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**Period:** Last {days} day(s)  
**Sources:** {len(DEFAULT_CHANNELS)} channels

---

"""
        
        if not videos:
            digest += "No new videos in the specified period.\n"
            return digest
        
        # Group by channel
        by_channel = {}
        for v in videos:
            ch = v["channel"]
            if ch not in by_channel:
                by_channel[ch] = []
            by_channel[ch].append(v)
        
        # Generate digest
        for channel, channel_videos in by_channel.items():
            digest += f"## 📺 {channel}\n\n"
            
            for video in channel_videos:
                digest += f"### [{video['title']}]({video['url']})\n\n"
                digest += f"**Published:** {video['published']}\n\n"
                
                # Try to get summary from DB
                meta = self.get_video_metadata(video["id"])
                if meta and meta.get("summary"):
                    digest += f"**Summary:** {meta['summary']}\n\n"
                
                if include_transcripts and meta and meta.get("transcript"):
                    # Add first 200 chars of transcript
                    transcript_preview = meta["transcript"][:200]
                    digest += f"**Transcript Preview:** {transcript_preview}...\n\n"
                
                digest += "---\n\n"
        
        # Summary stats
        digest += f"""## 📊 Stats

- **Total videos:** {len(videos)}
- **Channels with new content:** {len(by_channel)}
- **Videos with summaries:** {sum(1 for v in videos if self.get_video_metadata(v['id']) and self.get_video_metadata(v['id']).get('summary'))}

"""
        
        # Save to file
        if output_file:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(OUTPUT_DIR, output_file)
            with open(output_path, 'w') as f:
                f.write(digest)
            print(f"Digest saved to: {output_path}")
        
        return digest
    
    def quick_summary(self, days: int = 1) -> str:
        """Generate quick summary (without full details)."""
        videos = self.get_recent_videos(days)
        
        if not videos:
            return f"No new videos in the last {days} day(s)."
        
        # Group by channel
        by_channel = {}
        for v in videos:
            ch = v["channel"]
            if ch not in by_channel:
                by_channel[ch] = 0
            by_channel[ch] += 1
        
        lines = [f"YouTube Digest - Last {days} day(s):"]
        
        for channel, count in sorted(by_channel.items(), key=lambda x: -x[1]):
            lines.append(f"  {channel}: {count} new video(s)")
        
        lines.append(f"\nTotal: {len(videos)} videos from {len(by_channel)} channels")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate YouTube daily digest"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=1,
        help="Number of days to look back"
    )
    parser.add_argument(
        "--output", "-o",
        default="youtube-digest.md",
        help="Output file name"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick summary only (no full details)"
    )
    parser.add_argument(
        "--transcripts", "-t",
        action="store_true",
        help="Include transcript previews"
    )
    parser.add_argument(
        "--list-channels", "-l",
        action="store_true",
        help="List configured channels"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save to file, just print"
    )
    
    args = parser.parse_args()
    
    if args.list_channels:
        print("Configured channels:")
        for ch in DEFAULT_CHANNELS:
            print(f"  - {ch['name']}")
        return
    
    digest = YouTubeDigest()
    
    if args.quick:
        result = digest.quick_summary(args.days)
        print(result)
    else:
        output_file = None if args.no_save else args.output
        result = digest.generate_digest(
            args.days,
            args.transcripts,
            output_file
        )
        
        if args.no_save:
            print(result)
        else:
            print(result[:500] + "..." if len(result) > 500 else result)


if __name__ == "__main__":
    main()
