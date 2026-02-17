# 🔧 Scripts

CLI automation scripts for productivity, AI, and development.

[![GitHub stars](https://img.shields.io/github/stars/kamilskicki/scripts)](https://github.com/kamilskicki/scripts)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📺 YouTube Tools

YouTube monitoring, transcript processing, and content automation CLI tools.

**Location:** [`./YouTube/`](./YouTube/)

### Features

- 📡 **Channel Monitoring** — RSS-based YouTube channel watcher
- 📝 **Transcript Processing** — Fetch and process video transcripts  
- ✨ **Summarization** — AI-powered video summaries
- ⏰ **Key Moments** — Extract important timestamps
- 🔔 **Notifications** — Discord/Slack/Telegram alerts
- 🔄 **Pipeline** — All-in-one monitoring and processing
- 📊 **Digest** — Daily content digests

### Quick Start

```bash
cd YouTube
pip install -r requirements.txt

# Monitor channels
python channel_monitor.py --hours 24

# Summarize video
python yt_summarizer.py VIDEO_ID

# Generate digest
python yt_digest.py --quick
```

## 📦 Available Scripts

### YouTube Automation
| Script | Description |
|--------|-------------|
| `channel_monitor.py` | Monitor YouTube channels via RSS |
| `youtube_processor.py` | Fetch video transcripts |
| `yt_summarizer.py` | Generate video summaries |
| `yt_key_moments.py` | Extract key moments with timestamps |
| `yt_notify.py` | Send notifications (Discord/Slack/Telegram) |
| `yt_pipeline.py` | Full pipeline: monitor → process → summarize |
| `yt_digest.py` | Daily content digest generator |

## 🔍 Search Keywords

youtube, youtube-dl, youtube-transcript, youtube-api, cli-tool, automation, transcript, summarizer, python, rss-monitor, content-automation, digital-marketing, ai-tools, productivity, morning-briefing, news-digest

## 📋 Use Cases

- **Content Creation** — Monitor YouTube for research
- **Learning** — Extract key moments from tutorials
- **Automation** — Build automated content pipelines
- **Daily Briefings** — Generate daily digests

## 🛠️ Tech Stack

- Python 3.9+
- youtube-transcript-api
- feedparser

## 📄 License

MIT License - see LICENSE file

## 👤 Author

[kamilskicki](https://github.com/kamilskicki)

---
*Part of the kamilskicki developer ecosystem*
