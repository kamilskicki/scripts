from yt_summarizer import VideoSummarizer


def test_summarize_video_respects_max_length() -> None:
    summarizer = VideoSummarizer.__new__(VideoSummarizer)
    summarizer.get_transcript = lambda _video_id: "First sentence. " + "Middle sentence. " * 30 + "Last sentence."

    result = VideoSummarizer.summarize_video(summarizer, "dQw4w9WgXcQ", max_length=120)

    assert "error" not in result
    assert len(result["summary"]) <= 123  # allows trailing ellipsis
