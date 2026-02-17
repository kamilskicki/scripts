#!/usr/bin/env python3
"""Shared helpers used by YouTube scripts."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar
from urllib.parse import parse_qs, urlparse

import feedparser

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_RETRIES = 3
T = TypeVar("T")


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure process-wide logging."""
    if verbose and quiet:
        raise ValueError("Cannot use --verbose and --quiet together.")

    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int = DEFAULT_RETRIES,
    initial_delay: float = 0.5,
    backoff_multiplier: float = 2.0,
    max_delay: float = 4.0,
    action_name: str = "operation",
    logger: logging.Logger | None = None,
) -> T:
    """Run an operation with bounded exponential backoff."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= attempts:
                raise
            delay_seconds = min(max_delay, initial_delay * (backoff_multiplier ** (attempt - 1)))
            if logger:
                logger.warning(
                    "Retrying %s after error (%s/%s): %s",
                    action_name,
                    attempt,
                    attempts,
                    exc,
                )
            time.sleep(delay_seconds)

    raise RuntimeError(f"Unreachable retry loop while running {action_name}")


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def parse_published_datetime(value: str) -> datetime | None:
    """Parse YouTube/RSS published timestamp as timezone-aware UTC datetime."""
    if not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_video_id(value: str) -> str:
    """Extract canonical 11-char video ID from ID or URL."""
    candidate = value.strip()
    if VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host.endswith("youtu.be") and path:
        part = path.split("/")[0]
        if VIDEO_ID_RE.fullmatch(part):
            return part

    if "youtube.com" in host:
        if path in {"watch", "watch/"}:
            query = parse_qs(parsed.query)
            part = (query.get("v") or [None])[0]
            if part and VIDEO_ID_RE.fullmatch(part):
                return part

        segments = [segment for segment in path.split("/") if segment]
        if len(segments) >= 2 and segments[0] in {"shorts", "embed", "live", "v"}:
            part = segments[1]
            if VIDEO_ID_RE.fullmatch(part):
                return part

    raise ValueError(f"Unable to parse YouTube video id from '{value}'")


def ensure_directory(path: str) -> None:
    """Create directory if missing."""
    os.makedirs(path, exist_ok=True)


def fetch_feed(
    url: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    logger: logging.Logger | None = None,
) -> Any:
    """Fetch and parse an RSS feed with retries."""

    def _read_url() -> bytes:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return response.read()

    raw_bytes = retry_call(
        _read_url,
        attempts=retries,
        action_name=f"feed request {url}",
        logger=logger,
    )
    return feedparser.parse(raw_bytes)


def post_json(
    url: str,
    payload: dict,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    logger: logging.Logger | None = None,
) -> str:
    """POST JSON payload with retries and return decoded response body."""
    body = json.dumps(payload).encode("utf-8")

    def _send() -> str:
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    return retry_call(
        _send,
        attempts=retries,
        action_name=f"POST {url}",
        logger=logger,
    )
