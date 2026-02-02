# Scripts

A collection of standalone utility scripts and tools.

## Projects

| Project | Description |
|---------|-------------|
| [`youtube-monitor/`](./youtube-monitor/) | YouTube transcript fetcher + LLM summarization → Telegram pipeline |

## Quick Start

```bash
git clone https://github.com/kamilskicki/scripts.git
cd scripts

# Install YouTube monitor dependencies
pip install -r youtube-monitor/requirements.txt

# Set up environment (see youtube-monitor/README.md)
export ANTHROPIC_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# Run channel monitor
python -m youtube_monitor.monitor
```

## Structure

```
scripts/
├── youtube-monitor/          # YouTube automation pipeline
│   ├── __init__.py          # Package exports
│   ├── transcripts.py       # YouTube transcript fetcher
│   ├── processor.py         # LLM summarization + Telegram
│   ├── monitor.py           # RSS channel watcher
│   ├── requirements.txt     # Dependencies
│   └── README.md            # Detailed docs
├── .gitignore
└── README.md                # This file
```

## License

MIT
