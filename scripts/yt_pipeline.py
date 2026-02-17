#!/usr/bin/env python3
"""
YouTube Pipeline — v1.0
All-in-one: monitor channel → download → transcript → summarize.
"""

import os
import sys
import json
import argparse
import feedparser
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi


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


class YouTubePipeline:
    """Full YouTube monitoring and processing pipeline."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.api = YouTubeTranscriptApi()
        self._init_db()
    
    def _init_db(self):
        """Initialize database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                channel TEXT,
                title TEXT,
                published TEXT,
                transcript TEXT,
                summary TEXT,
                processed_at TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()
        conn.close()
    
    def get_db_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def check_channels(self, channels: List[Dict], hours: int = 24) -> List[Dict]:
        """Check channels for new videos."""
        new_videos = []
        cutoff = datetime.now() - timedelta(hours=hours)
        
        for channel in channels:
            try:
                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel['id']}"
                feed = feedparser.parse(url)
                
                for entry in feed.entries[:5]:
                    video_id = entry.yt_videoid
                    
                    # Check if already processed
                    conn = self.get_db_connection()
                    cursor = conn.execute(
                        "SELECT status FROM videos WHERE video_id = ?",
                        (video_id,)
                    )
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row and row[0] == "done":
                        continue
                    
                    # Check if recent
                    try:
                        pub_date = datetime.strptime(
                            entry.published[:19], "%Y-%m-%dT%H:%M:%S"
                        )
                        if pub_date < cutoff:
                            continue
                    except:
                        pass
                    
                    new_videos.append({
                        "id": video_id,
                        "title": entry.title,
                        "channel": channel['name'],
                        "url": entry.link,
                        "published": entry.published[:16]
                    })
                    
            except Exception as e:
                print(f"Error checking {channel['name']}: {e}", file=sys.stderr)
        
        return new_videos
    
    def fetch_transcript(self, video_id: str) -> Optional[str]:
        """Fetch video transcript."""
        try:
            transcript = self.api.fetch(video_id)
            return " ".join([s.text for s in transcript])
        except:
            return None
    
    def generate_summary(self, transcript: str, max_length: int = 500) -> str:
        """Generate summary from transcript."""
        sentences = transcript.split('. ')
        
        if len(sentences) <= 3:
            return transcript[:max_length]
        
        # Simple extractive: first few and last
        summary_parts = sentences[:2]
        if len(sentences) > 4:
            middle_idx = len(sentences) // 2
            summary_parts.append(sentences[middle_idx])
        
        summary = '. '.join(summary_parts)
        
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(' ', 1)[0] + '...'
        
        return summary
    
    def process_video(self, video: Dict) -> Dict:
        """Process a single video: transcript + summary."""
        video_id = video["id"]
        
        # Check if already processed
        conn = self.get_db_connection()
        cursor = conn.execute(
            "SELECT transcript, summary, status FROM videos WHERE video_id = ?",
            (video_id,)
        )
        row = cursor.fetchone()
        
        if row and row[2] == "done":
            conn.close()
            return {"status": "already_done", "video_id": video_id}
        
        # Fetch transcript
        transcript = self.fetch_transcript(video_id)
        
        if not transcript:
            conn.execute(
                """INSERT OR REPLACE INTO videos 
                   (video_id, channel, title, published, status) 
                   VALUES (?, ?, ?, ?, 'failed')""",
                (video_id, video["channel"], video["title"], video.get("published"))
            )
            conn.commit()
            conn.close()
            return {"status": "failed", "video_id": video_id}
        
        # Generate summary
        summary = self.generate_summary(transcript)
        
        # Save to database
        conn.execute(
            """INSERT OR REPLACE INTO videos 
               (video_id, channel, title, published, transcript, summary, processed_at, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, 'done')""",
            (video_id, video["channel"], video["title"], video.get("published"),
             transcript, summary, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        return {
            "status": "done",
            "video_id": video_id,
            "title": video["title"],
            "channel": video["channel"],
            "summary": summary,
            "transcript_length": len(transcript)
        }
    
    def run(
        self,
        channels: List[Dict] = None,
        hours: int = 24,
        output_file: str = None
    ) -> Dict:
        """Run full pipeline."""
        if channels is None:
            channels = DEFAULT_CHANNELS
        
        print(f"Checking {len(channels)} channels...")
        
        # Step 1: Find new videos
        new_videos = self.check_channels(channels, hours)
        print(f"Found {len(new_videos)} new videos")
        
        if not new_videos:
            return {
                "new_videos": 0,
                "processed": 0,
                "failed": 0,
                "videos": []
            }
        
        # Step 2: Process each video
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
        
        # Step 3: Save output
        if output_file:
            output_path = os.path.join(OUTPUT_DIR, output_file)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(f"# YouTube Pipeline Results\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n\n")
                
                for r in results:
                    f.write(f"## {r['channel']}: {r['title']}\n")
                    f.write(f"- URL: https://youtube.com/watch?v={r['video_id']}\n")
                    f.write(f"- Summary: {r['summary']}\n\n")
            
            print(f"Results saved to {output_path}")
        
        return {
            "new_videos": len(new_videos),
            "processed": processed,
            "failed": failed,
            "videos": results
        }


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Pipeline: Monitor → Transcript → Summarize"
    )
    parser.add_argument(
        "--hours", "-H",
        type=int,
        default=24,
        help="Look back N hours"
    )
    parser.add_argument(
        "--output", "-o",
        default="youtube-pipeline.md",
        help="Output file name"
    )
    parser.add_argument(
        "--list-channels", "-l",
        action="store_true",
        help="List configured channels"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for new videos without processing"
    )
    
    args = parser.parse_args()
    
    if args.list_channels:
        print("Configured channels:")
        for ch in DEFAULT_CHANNELS:
            print(f"  - {ch['name']}: {ch['id']}")
        return
    
    pipeline = YouTubePipeline()
    
    if args.dry_run:
        new_videos = pipeline.check_channels(DEFAULT_CHANNELS, args.hours)
        print(f"Found {len(new_videos)} new videos:")
        for v in new_videos:
            print(f"  - {v['channel']}: {v['title']}")
    else:
        result = pipeline.run(DEFAULT_CHANNELS, args.hours, args.output)
        
        print("\n=== Pipeline Results ===")
        print(f"New videos: {result['new_videos']}")
        print(f"Processed: {result['processed']}")
        print(f"Failed: {result['failed']}")
        
        if result['videos']:
            print("\nProcessed videos:")
            for v in result['videos']:
                print(f"  - {v['title'][:50]}...")


if __name__ == "__main__":
    main()
