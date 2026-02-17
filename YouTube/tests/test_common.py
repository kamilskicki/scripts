from datetime import timezone

import pytest

from common import extract_video_id, parse_published_datetime


def test_extract_video_id_from_watch_url() -> None:
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_from_shorts_url() -> None:
    assert extract_video_id("https://youtube.com/shorts/dQw4w9WgXcQ?feature=share") == "dQw4w9WgXcQ"


def test_extract_video_id_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        extract_video_id("not-a-video-id")


def test_parse_published_datetime_returns_utc_aware_datetime() -> None:
    parsed = parse_published_datetime("2026-02-17T11:22:33Z")
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.hour == 11
