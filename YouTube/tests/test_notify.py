from __future__ import annotations

import yt_notify as yt_notify_module
from yt_notify import _escape_telegram_markdown, notify_video


def test_notify_video_prefers_body_field(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyNotifier:
        def send(self, message) -> bool:
            captured["message"] = message
            return True

    monkeypatch.setattr(
        yt_notify_module.NotifierFactory,
        "create",
        staticmethod(lambda *_args, **_kwargs: DummyNotifier()),
    )

    result = notify_video(
        video={
            "title": "Hello",
            "body": "Custom body",
            "channel": "Fallback channel",
            "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        },
        channels=["discord"],
        config={},
    )

    assert result == {"discord": "sent"}
    assert captured["message"].body == "Custom body"


def test_escape_telegram_markdown_escapes_special_characters() -> None:
    assert _escape_telegram_markdown("a_b! [x]") == r"a\_b\! \[x\]"
