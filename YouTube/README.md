# 📺 YouTube Tools

CLI tools for YouTube monitoring, transcript processing, and content automation.

## Installation

```bash
cd YouTube
pip install -r requirements.txt
```

## Scripts

| Script | Description |
|--------|-------------|
| `channel_monitor.py` | RSS-based channel watcher - monitors 12 AI YouTube channels for new videos |
| `youtube_processor.py` | Fetch transcripts from any YouTube video |
| `yt_summarizer.py` | Generate summaries from video transcripts |
| `yt_key_moments.py` | Extract key moments with timestamps |
| `yt_notify.py` | Send notifications to Discord/Slack/Telegram |
| `yt_pipeline.py` | All-in-one: monitor → download → transcript → summarize |
| `yt_digest.py` | Daily digest generator for content curation |

## Usage

```bash
# Monitor channels for new videos
python channel_monitor.py --hours 24 --output output.md

# Get video transcript
python youtube_processor.py dQw4w9WgXcQ

# Summarize video
python yt_summarizer.py dQw4w9WgXcQ

# Extract key moments
python yt_key_moments.py dQw4w9WgXcQ --count 5

# Send notification
python yt_notify.py --channel discord --test

# Run full pipeline
python yt_pipeline.py --hours 24

# Quick digest
python yt_digest.py --quick
```

## Channel List

Default monitored channels:
- In The World of AI
- Matthew Berman
- AI Revolution
- The AI Grid
- Julia McCoy
- Theo (t3.gg)
- Wes Roth
- AI Code King
- ThePrimeTime
- Fireship
- NetworkChuck
- AI Master

## Use Cases

- **Content Curation** — Monitor AI/tech channels for new content
- **Research** — Extract transcripts for analysis
- **Summarization** — Generate video summaries for newsletters
- **Notifications** — Alert when new videos are published
- **Digest** — Daily/weekly digests for Morning Briefing

---
*Part of github.com/kamilskicki/scripts*
