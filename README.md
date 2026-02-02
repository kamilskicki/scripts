# Scripts

A collection of standalone utility scripts for various tasks.

## Scripts

| Script | Description | Dependencies |
|--------|-------------|--------------|
| [`_transcripts.py`](_transcripts.py) | Fetch YouTube video transcripts | requests, defusedxml |
| [`youtube_processor.py`](youtube_processor.py) | Transcript → LLM summary → Telegram | anthropic/openai, requests |
| [`channel_monitor.py`](channel_monitor.py) | RSS-based channel watcher with auto-processing | feedparser, sqlite3 |

## Installation

```bash
# Clone the repository
git clone https://github.com/kamilskicki/scripts.git
cd scripts

# Install base dependencies
pip install requests defusedxml

# For YouTube summarization features
pip install anthropic openai feedparser
```

## Usage

### YouTube Transcript Fetcher

Fetch transcripts from YouTube videos programmatically.

```bash
# CLI usage
python _transcripts.py <video_id> [language_code]
python _transcripts.py dQw4w9WgXcQ en

# Programmatic usage
from _transcripts import YouTubeTranscriptApi

api = YouTubeTranscriptApi()
transcript = api.get_transcript("VIDEO_ID", languages=["en"])
for snippet in transcript:
    print(f"{snippet.start:.2f}s: {snippet.text}")
```

### YouTube Video Processor

Fetch transcript, summarize with LLM, and send to Telegram.

```bash
# Set environment variables
export ANTHROPIC_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# Process single video
python youtube_processor.py <video_id> "Video Title" "Channel Name"
```

### Channel Monitor

RSS-based watcher that monitors subscribed channels automatically.

```bash
# Check all configured channels
python channel_monitor.py

# List configured channels
python channel_monitor.py --list

# Check single channel
python channel_monitor.py --channel CHANNEL_ID
```

**Default Channels:**
- Matthew Berman (AI news)
- The AI Advantage (marketing/agency)
- AI Explained (balanced analysis)
- Tina Huang (career/productivity)
- Fireship (quick technical updates)

### Cron Setup

Run every 6 hours:

```bash
0 */6 * * * cd /path/to/scripts && python channel_monitor.py >> /var/log/youtube-monitor.log 2>&1
```

## Environment Variables

| Variable | Required For | Description |
|----------|--------------|-------------|
| `ANTHROPIC_API_KEY` | youtube_processor.py | Claude API key |
| `OPENAI_API_KEY` | youtube_processor.py | Fallback to GPT-4 |
| `TELEGRAM_BOT_TOKEN` | youtube_processor.py, channel_monitor.py | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | youtube_processor.py, channel_monitor.py | Your Telegram chat ID |
| `LLM_MODEL` | youtube_processor.py | Model name (default: claude-3-5-sonnet-20241022) |
| `YOUTUBE_DB_PATH` | channel_monitor.py | SQLite DB path |

## License

MIT
