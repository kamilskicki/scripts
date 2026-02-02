# YouTube Monitor

Automated YouTube video transcript summarization pipeline. Monitors channels via RSS, fetches transcripts, summarizes with LLM, and delivers to Telegram.

## Features

- 🎬 **Transcript Fetching** - Extract transcripts from any YouTube video
- 🤖 **LLM Summarization** - Claude or GPT-4 powered business-focused summaries
- 📱 **Telegram Delivery** - Formatted summaries sent directly to your chat
- 📡 **Channel Monitoring** - RSS-based automatic new video detection
- 💾 **Duplicate Prevention** - SQLite tracking of processed videos

## Installation

```bash
cd youtube-monitor
pip install -r requirements.txt
```

## Configuration

Set these environment variables:

```bash
# Required for LLM (at least one)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."  # Fallback

# Required for Telegram
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="-100123456789"

# Optional
export LLM_MODEL="claude-3-5-sonnet-20241022"
export YOUTUBE_DB_PATH="/path/to/videos.db"
```

## Usage

### As a Module

```python
from youtube_monitor import YouTubeTranscriptApi, VideoProcessor, ChannelMonitor

# Fetch transcript only
api = YouTubeTranscriptApi()
transcript = api.get_transcript("dQw4w9WgXcQ")

# Process single video
processor = VideoProcessor()
text = processor.extract_text("VIDEO_ID")
summary = processor.summarize(text, "Title", "Channel")
processor.send_to_telegram(summary, "https://youtube.com/...", "Title")

# Monitor channels
monitor = ChannelMonitor()
monitor.run()
```

### CLI

```bash
# Fetch transcript
python -m youtube_monitor.transcripts dQw4w9WgXcQ

# Process single video
python -m youtube_monitor.processor VIDEO_ID "Video Title" "Channel Name"

# Monitor all configured channels
python -m youtube_monitor.monitor

# List configured channels
python -m youtube_monitor.monitor --list

# Check single channel
python -m youtube_monitor.monitor --channel UC_CHANNEL_ID
```

### Cron Setup

Run every 6 hours:

```bash
0 */6 * * * cd /path/to/scripts && python -m youtube_monitor.monitor >> /var/log/youtube-monitor.log 2>&1
```

## Default Channels

- Matthew Berman (AI news)
- The AI Advantage (marketing/agency)
- AI Explained (balanced analysis)
- Tina Huang (career/productivity)
- Fireship (quick technical updates)

Edit `monitor.py` to customize the channel list.
