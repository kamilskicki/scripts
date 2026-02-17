#!/usr/bin/env python3
"""
YouTube Notify — v1.0
Sends notifications to Discord/Slack/Telegram when new videos are found.
"""

import os
import sys
import json
import argparse
import logging
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

from common import configure_logging, post_json


@dataclass
class NotificationMessage:
    """Notification message structure."""
    title: str
    body: str
    url: str
    channel: str
    thumbnail: Optional[str] = None


class DiscordNotifier:
    """Send notifications to Discord via webhooks."""
    
    def __init__(self, webhook_url: str, logger: logging.Logger | None = None):
        self.webhook_url = webhook_url
        self.logger = logger or logging.getLogger("yt_notify.discord")
    
    def send(self, message: NotificationMessage) -> bool:
        """Send Discord notification."""
        payload = {
            "embeds": [{
                "title": message.title,
                "description": message.body,
                "url": message.url,
                "color": 16711680,  # Red for YouTube
            }]
        }
        
        if message.thumbnail:
            payload["embeds"][0]["thumbnail"] = {"url": message.thumbnail}
        
        try:
            post_json(self.webhook_url, payload, logger=self.logger)
            return True
        except Exception as exc:
            self.logger.error("Discord error: %s", exc)
            return False


class SlackNotifier:
    """Send notifications to Slack via webhooks."""
    
    def __init__(self, webhook_url: str, logger: logging.Logger | None = None):
        self.webhook_url = webhook_url
        self.logger = logger or logging.getLogger("yt_notify.slack")
    
    def send(self, message: NotificationMessage) -> bool:
        """Send Slack notification."""
        payload = {
            "text": message.title,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{message.title}*\n{message.body}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Watch Video"},
                            "url": message.url
                        }
                    ]
                }
            ]
        }
        
        try:
            post_json(self.webhook_url, payload, logger=self.logger)
            return True
        except Exception as exc:
            self.logger.error("Slack error: %s", exc)
            return False


class TelegramNotifier:
    """Send notifications to Telegram via Bot API."""
    
    def __init__(self, bot_token: str, chat_id: str, logger: logging.Logger | None = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logger or logging.getLogger("yt_notify.telegram")
    
    def send(self, message: NotificationMessage) -> bool:
        """Send Telegram notification."""
        import urllib.request
        import urllib.error

        escaped_title = _escape_telegram_markdown(message.title)
        escaped_body = _escape_telegram_markdown(message.body)
        escaped_url = message.url.replace(")", "%29")
        text = f"*{escaped_title}*\n\n{escaped_body}\n\n[Watch Video]({escaped_url})"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "MarkdownV2"
        }
        
        try:
            url = f"{self.api_url}/sendMessage"
            post_json(url, payload, logger=self.logger)
            return True
        except Exception as exc:
            self.logger.error("Telegram error: %s", exc)
            return False


class NotifierFactory:
    """Factory to create notifiers based on channel."""
    
    @staticmethod
    def create(channel: str, config: Dict, logger: logging.Logger | None = None) -> Optional[object]:
        """Create notifier for given channel."""
        channel = channel.lower()
        logger = logger or logging.getLogger("yt_notify.factory")
        
        if channel == "discord":
            webhook = config.get("webhook_url") or os.environ.get("DISCORD_WEBHOOK_URL")
            if not webhook:
                logger.error("Discord webhook URL not provided")
                return None
            return DiscordNotifier(webhook, logger=logging.getLogger("yt_notify.discord"))
        
        elif channel == "slack":
            webhook = config.get("webhook_url") or os.environ.get("SLACK_WEBHOOK_URL")
            if not webhook:
                logger.error("Slack webhook URL not provided")
                return None
            return SlackNotifier(webhook, logger=logging.getLogger("yt_notify.slack"))
        
        elif channel == "telegram":
            token = config.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = config.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
            if not token or not chat_id:
                logger.error("Telegram bot_token and chat_id required")
                return None
            return TelegramNotifier(token, chat_id, logger=logging.getLogger("yt_notify.telegram"))
        
        else:
            logger.error("Unknown channel '%s'", channel)
            return None


def _escape_telegram_markdown(value: str) -> str:
    """Escape Telegram MarkdownV2 special chars."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", value or "")


def notify_video(
    video: Dict,
    channels: List[str],
    config: Dict,
    logger: logging.Logger | None = None,
) -> Dict:
    """Send notification for a video to specified channels."""
    logger = logger or logging.getLogger("yt_notify")
    
    message = NotificationMessage(
        title=video.get("title", "New Video"),
        body=video.get("body", video.get("channel", "YouTube")),
        url=video.get("url", ""),
        channel=",".join(channels),
        thumbnail=video.get("thumbnail")
    )
    
    results = {}
    
    for channel in channels:
        notifier = NotifierFactory.create(channel, config, logger=logger)
        
        if notifier:
            success = notifier.send(message)
            results[channel] = "sent" if success else "failed"
        else:
            results[channel] = "error: no notifier"
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Send YouTube video notifications to Discord/Slack/Telegram"
    )
    parser.add_argument(
        "--channel", "-c",
        choices=["discord", "slack", "telegram"],
        required=True,
        help="Notification channel"
    )
    parser.add_argument(
        "--webhook-url",
        help="Discord/Slack webhook URL (or use env var)"
    )
    parser.add_argument(
        "--bot-token",
        help="Telegram bot token (or use env var)"
    )
    parser.add_argument(
        "--chat-id",
        help="Telegram chat ID (or use env var)"
    )
    parser.add_argument(
        "--video-title",
        default="New YouTube Video!",
        help="Notification title"
    )
    parser.add_argument(
        "--video-body",
        default="A new video was published",
        help="Notification body"
    )
    parser.add_argument(
        "--video-url",
        help="Video URL"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send test notification"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    
    args = parser.parse_args()

    try:
        configure_logging(verbose=args.verbose, quiet=args.quiet)
    except ValueError as exc:
        parser.error(str(exc))
    logger = logging.getLogger("yt_notify")
    
    config = {
        "webhook_url": args.webhook_url,
        "bot_token": args.bot_token,
        "chat_id": args.chat_id
    }
    
    if args.test:
        video = {
            "title": "Test Notification",
            "body": "This is a test from yt-notify",
            "url": "https://youtube.com",
            "channel": args.channel
        }
    else:
        video = {
            "title": args.video_title,
            "body": args.video_body,
            "url": args.video_url or "https://youtube.com",
            "channel": args.channel
        }
    
    result = notify_video(video, [args.channel], config, logger=logger)
    
    print(json.dumps(result, indent=2))
    
    if any("failed" in v or "error" in v for v in result.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
