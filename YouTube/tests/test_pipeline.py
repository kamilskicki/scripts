from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from common import utc_now
from yt_pipeline import YouTubePipeline
import yt_pipeline as yt_pipeline_module


def test_check_channels_filters_done_and_deduplicates(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "pipeline.db"
    pipeline = YouTubePipeline(db_path=str(db_path))

    done_id = "AAAAAAAAAAA"
    new_id = "BBBBBBBBBBB"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO videos (video_id, channel, title, published, status)
        VALUES (?, ?, ?, ?, 'done')
        """,
        (done_id, "Any", "Already done", utc_now().isoformat()),
    )
    conn.commit()
    conn.close()

    published = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = [
        SimpleNamespace(yt_videoid=done_id, title="Old done", link=f"https://youtube.com/watch?v={done_id}", published=published),
        SimpleNamespace(yt_videoid=new_id, title="Fresh one", link=f"https://youtube.com/watch?v={new_id}", published=published),
    ]

    monkeypatch.setattr(yt_pipeline_module, "fetch_feed", lambda *_args, **_kwargs: SimpleNamespace(entries=entries))

    channels = [
        {"name": "Channel A", "id": "chan_a"},
        {"name": "Channel B", "id": "chan_b"},
    ]
    results = pipeline.check_channels(channels, hours=24)

    assert [video["id"] for video in results] == [new_id]
    assert results[0]["channel"] == "Channel A"


def test_process_video_marks_failed_when_transcript_missing(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "pipeline.db"
    pipeline = YouTubePipeline(db_path=str(db_path))
    monkeypatch.setattr(pipeline, "fetch_transcript", lambda _video_id: None)

    video = {
        "id": "CCCCCCCCCCC",
        "title": "No transcript",
        "channel": "Channel X",
        "published": utc_now().isoformat(),
    }

    result = pipeline.process_video(video)
    assert result["status"] == "failed"

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM videos WHERE video_id = ?", (video["id"],)).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "failed"
