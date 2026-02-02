#!/usr/bin/env python3
"""
Channel Monitor - RSS-based YouTube channel watcher
Monitors subscribed channels and sends summaries to Telegram
"""

import feedparser
import sqlite3
import os
import sys
from datetime import datetime
from youtube_processor import VideoProcessor

DEFAULT_CHANNELS = [
    {"name": "Matthew Berman", "id": "UCV0qAVeOoC9IqGvXOiBj8zA"},
    {"name": "The AI Advantage", "id": "UCKe_-Cai8xGZQ6OF6Xb1UqQ"},
    {"name": "AI Explained", "id": "UCybDaveeU0GJ9SdPJ5bqlZw"},
    {"name": "Tina Huang", "id": "UCYjYv_1LMZHZnG3_QCjXwA"},
    {"name": "Fireship", "id": "UCsBjURrPoezykLs9EqgamOA"},
]

DB_PATH = os.getenv("YOUTUBE_DB_PATH", "processed_videos.db")


class ChannelMonitor:
    """Monitor YouTube channels via RSS and process new videos."""
    
    RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
    
    def __init__(self, channels=None):
        self.channels = channels or DEFAULT_CHANNELS
        self.processor = VideoProcessor()
        self.init_db()
    
    def init_db(self):
        """Track which videos we've processed."""
        self.conn = sqlite3.connect(DB_PATH)
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
        cursor = self.conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ?", (video_id,)
        )
        return cursor.fetchone() is not None
    
    def mark_processed(self, video_id: str, channel: str, title: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO videos VALUES (?, ?, ?, ?)",
            (video_id, channel, title, datetime.now())
        )
        self.conn.commit()
    
    def check_channel(self, channel: dict):
        """Check for new videos in a channel."""
        url = self.RSS_URL.format(channel['id'])
        feed = feedparser.parse(url)
        
        new_count = 0
        for entry in feed.entries[:5]:
            video_id = entry.yt_videoid
            
            if self.is_processed(video_id):
                continue
            
            print(f"\n📺 New video from {channel['name']}: {entry.title}")
            
            text = self.processor.extract_text(video_id)
            if text:
                try:
                    summary = self.processor.summarize(text, entry.title, channel['name'])
                    self.processor.send_to_telegram(summary, entry.link, entry.title)
                    self.mark_processed(video_id, channel['name'], entry.title)
                    new_count += 1
                    print(f"✓ Processed and sent to Telegram")
                except Exception as e:
                    print(f"✗ Error processing: {e}")
            else:
                print(f"✗ No transcript available")
                self.mark_processed(video_id, channel['name'], entry.title)
        
        return new_count
    
    def run(self):
        """Check all channels and report stats."""
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


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor YouTube channels for new videos")
    parser.add_argument("--channel", "-c", help="Check single channel ID")
    parser.add_argument("--list", "-l", action="store_true", help="List configured channels")
    args = parser.parse_args()
    
    if args.list:
        print("Configured channels:")
        for ch in DEFAULT_CHANNELS:
            print(f"  • {ch['name']}: {ch['id']}")
        sys.exit(0)
    
    if args.channel:
        monitor = ChannelMonitor(channels=[{"name": "Custom", "id": args.channel}])
    else:
        monitor = ChannelMonitor()
    
    monitor.run()
