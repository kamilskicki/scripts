#!/usr/bin/env python3
"""
Channel Monitor - RSS-based YouTube channel watcher
Monitors subscribed channels and sends summaries to Telegram.
"""

import sqlite3
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict

import feedparser

from .processor import VideoProcessor


# =============================================================================
# Default Channels (AI/Tech focused)
# =============================================================================

DEFAULT_CHANNELS = [
    {"name": "Matthew Berman", "id": "UCcefcZRL2oaA_uBNeo5UOWg"},
    {"name": "The AI Advantage", "id": "UCKe_-Cai8xGZQ6OF6Xb1UqQ"},
    {"name": "AI Explained", "id": "UCNF5S2rLFtA0pEv6woF-xVg"},
    {"name": "Tina Huang", "id": "UC2UXDak6o7rBm23k3Vv5dww"},
    {"name": "Fireship", "id": "UCsBjURrPoezykLs9EqgamOA"},
]

DB_PATH = os.getenv("YOUTUBE_DB_PATH", "processed_videos.db")


# =============================================================================
# Channel Monitor
# =============================================================================

class ChannelMonitor:
    """Monitor YouTube channels via RSS and process new videos."""
    
    RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
    
    def __init__(self, channels: Optional[List[Dict]] = None, db_path: Optional[str] = None):
        self.channels = channels or DEFAULT_CHANNELS
        self.db_path = db_path or DB_PATH
        self.processor = VideoProcessor()
        self._conn: Optional[sqlite3.Connection] = None
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._init_db()
        return self._conn
    
    def _init_db(self) -> None:
        """Create database schema if needed."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                channel TEXT,
                title TEXT,
                processed_at TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def is_processed(self, video_id: str) -> bool:
        """Check if video has already been processed."""
        cursor = self.conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ?", (video_id,)
        )
        return cursor.fetchone() is not None
    
    def mark_processed(self, video_id: str, channel: str, title: str) -> None:
        """Mark video as processed in database."""
        self.conn.execute(
            "INSERT OR REPLACE INTO videos VALUES (?, ?, ?, ?)",
            (video_id, channel, title, datetime.now())
        )
        self.conn.commit()
    
    def check_channel(self, channel: Dict) -> int:
        """Check for new videos in a channel. Returns count of new videos processed."""
        url = self.RSS_URL.format(channel['id'])
        feed = feedparser.parse(url)
        
        if feed.bozo:
            print(f"⚠ Feed error for {channel['name']}: {feed.bozo_exception}")
            return 0
        
        new_count = 0
        for entry in feed.entries[:5]:
            video_id = getattr(entry, 'yt_videoid', None)
            if not video_id:
                continue
            
            if self.is_processed(video_id):
                continue
            
            print(f"\n📺 New video from {channel['name']}: {entry.title}")
            
            text = self.processor.extract_text(video_id)
            if text:
                try:
                    summary = self.processor.summarize(text, entry.title, channel['name'])
                    result = self.processor.send_to_telegram(summary, entry.link, entry.title)
                    
                    if result.get("ok"):
                        self.mark_processed(video_id, channel['name'], entry.title)
                        new_count += 1
                        print("✓ Processed and sent to Telegram")
                    else:
                        print(f"✗ Telegram error: {result.get('description', 'Unknown')}")
                        
                except Exception as e:
                    print(f"✗ Error processing: {e}")
            else:
                print("✗ No transcript available")
                # Still mark as processed to avoid retrying
                self.mark_processed(video_id, channel['name'], entry.title)
        
        return new_count
    
    def run(self) -> int:
        """Check all channels and report stats. Returns total new videos processed."""
        print(f"{'='*50}")
        print(f"🔍 YouTube Channel Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}\n")
        
        total_new = 0
        for channel in self.channels:
            try:
                count = self.check_channel(channel)
                total_new += count
                if count == 0:
                    print(f"✓ {channel['name']}: No new videos")
            except Exception as e:
                print(f"✗ Error checking {channel['name']}: {e}")
        
        print(f"\n{'='*50}")
        print(f"✅ Complete: {total_new} new videos processed")
        print(f"{'='*50}")
        
        return total_new
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor YouTube channels for new videos")
    parser.add_argument("--channel", "-c", help="Check single channel ID")
    parser.add_argument("--list", "-l", action="store_true", help="List configured channels")
    parser.add_argument("--db", help="Path to SQLite database")
    args = parser.parse_args()
    
    if args.list:
        print("Configured channels:")
        for ch in DEFAULT_CHANNELS:
            print(f"  • {ch['name']}: {ch['id']}")
        return 0
    
    db_path = args.db or DB_PATH
    
    if args.channel:
        monitor = ChannelMonitor(
            channels=[{"name": "Custom", "id": args.channel}],
            db_path=db_path
        )
    else:
        monitor = ChannelMonitor(db_path=db_path)
    
    try:
        monitor.run()
    finally:
        monitor.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
