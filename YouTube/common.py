#!/usr/bin/env python3
"""Shared helpers used by YouTube scripts."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


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

