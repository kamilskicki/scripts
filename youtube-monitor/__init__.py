"""
YouTube Monitor - Automated video transcript summarization pipeline

Modules:
    transcripts: Fetch YouTube video transcripts
    processor: Summarize transcripts with LLM and send to Telegram
    monitor: RSS-based channel watcher for automated processing
"""

from .transcripts import YouTubeTranscriptApi, FetchedTranscript, TranscriptError
from .processor import VideoProcessor
from .monitor import ChannelMonitor

__all__ = [
    "YouTubeTranscriptApi",
    "FetchedTranscript", 
    "TranscriptError",
    "VideoProcessor",
    "ChannelMonitor",
]
