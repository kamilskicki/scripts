# Scripts

Automation scripts for YouTube intelligence workflows: discovery, transcript extraction, summarization, key moments, notifications, and digest generation.

[![GitHub stars](https://img.shields.io/github/stars/kamilskicki/scripts)](https://github.com/kamilskicki/scripts)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/kamilskicki/scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/kamilskicki/scripts/actions/workflows/ci.yml)

## Why this repo exists

This project is optimized for fast command-line content operations:

- monitor high-signal channels
- capture transcripts reliably
- produce usable summaries and key moments
- distribute alerts to team chat systems
- create daily digests for research and briefing pipelines

## Project layout

```text
.
├─ YouTube/
│  ├─ channel_monitor.py
│  ├─ youtube_processor.py
│  ├─ yt_summarizer.py
│  ├─ yt_key_moments.py
│  ├─ yt_notify.py
│  ├─ yt_pipeline.py
│  ├─ yt_digest.py
│  ├─ channels.py
│  ├─ common.py
│  └─ tests/
├─ .github/workflows/ci.yml
├─ pyproject.toml
└─ README.md
```

## Quick start

```bash
git clone https://github.com/kamilskicki/scripts.git
cd scripts
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r YouTube/requirements.txt
pip install -e .[dev]
```

Run a smoke workflow:

```bash
python YouTube/channel_monitor.py --hours 24
python YouTube/yt_pipeline.py --hours 24 --output youtube-pipeline.md
python YouTube/yt_digest.py --days 1 --quick
```

## Core commands

| Command | Purpose |
|---|---|
| `python YouTube/channel_monitor.py` | scan RSS feeds for new videos |
| `python YouTube/youtube_processor.py <video-id-or-url>` | fetch full transcript |
| `python YouTube/yt_summarizer.py <video-id-or-url>` | produce extractive summary |
| `python YouTube/yt_key_moments.py <video-id-or-url>` | find timestamped highlights |
| `python YouTube/yt_notify.py --channel ... --test` | send test notification |
| `python YouTube/yt_pipeline.py` | monitor + transcript + summary |
| `python YouTube/yt_digest.py` | generate markdown digest |

## Engineering standards

- Shared channel config is centralized in `YouTube/channels.py`.
- Shared parsing/time helpers are centralized in `YouTube/common.py`.
- UTC-aware timestamp filtering is used for feed recency checks.
- CI validates lint + tests on Python 3.10/3.11/3.12.

## Documentation

- Full YouTube tooling guide: `YouTube/README.md`
- Environment variable template: `YouTube/.env.example`

## Contributing

```bash
ruff check YouTube
pytest
```

Use small, reviewable commits and include CLI output examples for behavior changes.

## License

MIT, see `LICENSE`.
