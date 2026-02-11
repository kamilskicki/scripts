# 📺 YouTube Channel Monitor & Transcript Tools

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A lightweight toolkit for monitoring YouTube channels via RSS and fetching video transcripts. No API keys required.

## Features

- **RSS-based channel monitoring** — no YouTube API key needed
- **SQLite tracking** — never processes the same video twice
- **Automatic transcript fetching** via [`youtube-transcript-api`](https://pypi.org/project/youtube-transcript-api/)
- **Structured output** — JSON + Markdown files for easy downstream processing

## Scripts

| Script | Description |
|--------|-------------|
| [`channel_monitor.py`](channel_monitor.py) | RSS-based channel watcher with SQLite tracking, transcript fetching, and JSON/Markdown output |
| [`youtube_processor.py`](youtube_processor.py) | Standalone transcript fetcher — extract clean text from any YouTube video |

## Installation

```bash
git clone https://github.com/kamilskicki/scripts.git
cd scripts
pip install -r requirements.txt
```

## Usage

### Channel Monitor

Checks configured channels for new videos (last 24h), fetches transcripts, and saves structured output.

```bash
# Check all configured channels for new videos
python channel_monitor.py

# List all monitored channels
python channel_monitor.py --list

# Check a specific channel by ID
python channel_monitor.py --channel UCawZsQWqfGSbCI5yjkdVkTA
```

#### Cron Setup

Run every 6 hours to catch new uploads:

```bash
0 */6 * * * cd /path/to/scripts && python channel_monitor.py >> /var/log/youtube-monitor.log 2>&1
```

### YouTube Processor

Fetch a clean transcript from any YouTube video:

```bash
# By video ID
python youtube_processor.py dQw4w9WgXcQ

# From a URL — extract the video ID first
python youtube_processor.py $(echo "https://youtube.com/watch?v=dQw4w9WgXcQ" | grep -oP 'v=\K[^&]+')
```

## Monitored Channels

The channel monitor tracks these channels by default:

| Channel | Focus |
|---------|-------|
| In The World of AI | AI news & developments |
| Matthew Berman | AI tools & reviews |
| AI Revolution | AI trends |
| The AI Grid | AI workflows & tools |
| Julia McCoy | AI content creation |
| Theo (t3.gg) | Web dev & tech |
| Wes Roth | AI analysis |
| AI Code King | AI coding |
| ThePrimeTime | Dev culture & tech |
| Fireship | Quick technical updates |
| NetworkChuck | Networking & tech |
| AI Master | AI tutorials |

Channels are configured in `DEFAULT_CHANNELS` inside `channel_monitor.py`.

## Output Structure

The channel monitor creates structured output for each new video:

```
memory/
├── YYYY-MM-DD-channel-name-video-title.md    # Markdown with metadata + transcript
└── YYYY-MM-DD-channel-name-video-title.json  # Structured JSON data
```

## Requirements

- Python 3.9+
- No API keys needed

## License

[MIT](LICENSE)
