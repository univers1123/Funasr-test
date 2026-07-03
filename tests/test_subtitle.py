"""字幕合併模組單元測試(不需要模型與 GPU)。"""

import pytest

from app.subtitle import (
    Segment,
    SubtitleOptions,
    build_subtitles,
    format_timestamp_srt,
    format_timestamp_vtt,
    merge_segments,
    sentence_info_to_segments,
    to_srt,
    to_txt,
    to_vtt,
)

# 模擬 FunASR sentence_info 輸出
SENTENCE_INFO = [
    {"text": "大家好,", "start": 0, "end": 1200, "spk": 0},
    {"text": "歡迎收聽本集節目。", "start": 1400, "end": 3600, "spk": 0},
    {"text": "謝謝主持人邀請。", "start": 4200, "end": 6000, "spk": 1},
    {"text": "今天我們聊聊語音辨識。", "start": 7500, "end": 10000, "spk": 0},
]


class TestTimestamp:
    def test_srt_format(self):
        assert format_timestamp_srt(0) == "00:00:00,000"
        assert format_timestamp_srt(1234) == "00:00:01,234"
        assert format_timestamp_srt(61_000) == "00:01:01,000"
        assert format_timestamp_srt(3_661_005) == "01:01:01,005"

    def test_srt_negative_clamped_to_zero(self):
        assert format_timestamp_srt(-5) == "00:00:00,000"

    def test_vtt_format(self):
        assert format_timestamp_vtt(1234) == "00:00:01.234"


class TestSentenceInfoConversion:
    def test_basic(self):
        segments = sentence_info_to_segments(SENTENCE_INFO)
        assert len(segments) == 4
        assert segments[0].speaker == 0
        assert segments[2].speaker == 1
        assert segments[0].start_ms == 0
        assert segments[1].end_ms == 3600

    def test_skips_empty_text(self):
        segments = sentence_info_to_segments([{"text": "  ", "start": 0, "end": 100, "spk": 0}])
        assert segments == []

    def test_missing_spk_field(self):
        segments = sentence_info_to_segments([{"text": "哈囉", "start": 0, "end": 100}])
        assert segments[0].speaker is None


class TestMerge:
    def test_merges_same_speaker_close_gap(self):
        segments = build_subtitles(SENTENCE_INFO, SubtitleOptions(merge_gap_ms=800))
        # 前兩句同語者、間隔 200ms → 合併;第三句換語者;第四句間隔 1500ms → 不合併
        assert len(segments) == 3
        assert segments[0].text == "大家好,歡迎收聽本集節目。"
        assert segments[0].start_ms == 0
        assert segments[0].end_ms == 3600

    def test_no_merge_across_speakers(self):
        segments = build_subtitles(SENTENCE_INFO, SubtitleOptions(merge_gap_ms=99999))
        speakers = [seg.speaker for seg in segments]
        assert speakers == [0, 1, 0]

    def test_respects_max_chars(self):
        info = [
            {"text": "一" * 30, "start": 0, "end": 1000, "spk": 0},
            {"text": "二" * 30, "start": 1100, "end": 2000, "spk": 0},
        ]
        segments = build_subtitles(info, SubtitleOptions(max_chars=42))
        assert len(segments) == 2

    def test_empty_input(self):
        assert merge_segments([], SubtitleOptions()) == []


class TestOutputFormats:
    def test_srt_output(self):
        segments = build_subtitles(SENTENCE_INFO)
        srt = to_srt(segments)
        assert "1\n00:00:00,000 --> 00:00:03,600\n[Speaker 1] 大家好,歡迎收聽本集節目。" in srt
        assert "[Speaker 2] 謝謝主持人邀請。" in srt

    def test_srt_custom_speaker_names(self):
        options = SubtitleOptions(speaker_names={0: "主持人", 1: "來賓"})
        segments = build_subtitles(SENTENCE_INFO, options)
        srt = to_srt(segments, options)
        assert "[主持人]" in srt
        assert "[來賓]" in srt
        assert "Speaker" not in srt

    def test_srt_without_speaker_label(self):
        options = SubtitleOptions(show_speaker=False)
        segments = build_subtitles(SENTENCE_INFO, options)
        srt = to_srt(segments, options)
        assert "[Speaker" not in srt
        assert "大家好" in srt

    def test_vtt_output(self):
        segments = build_subtitles(SENTENCE_INFO)
        vtt = to_vtt(segments)
        assert vtt.startswith("WEBVTT\n")
        assert "00:00:00.000 --> 00:00:03.600" in vtt

    def test_txt_output(self):
        segments = build_subtitles(SENTENCE_INFO)
        txt = to_txt(segments)
        lines = txt.strip().split("\n")
        assert len(lines) == 3
        assert lines[0].startswith("[Speaker 1]")

    def test_segment_without_speaker_has_no_label(self):
        segments = [Segment(0, 1000, "哈囉", speaker=None)]
        assert "[" not in to_srt(segments)


class TestCliHelpers:
    def test_parse_speaker_names(self):
        from app.cli import parse_speaker_names

        assert parse_speaker_names("1=主持人,2=來賓") == {0: "主持人", 1: "來賓"}
        assert parse_speaker_names(None) == {}

    def test_parse_speaker_names_invalid(self):
        import argparse

        from app.cli import parse_speaker_names

        with pytest.raises(argparse.ArgumentTypeError):
            parse_speaker_names("主持人")
