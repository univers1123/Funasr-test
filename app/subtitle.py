"""字幕合併模組:將 FunASR 的 sentence_info(含 speaker 標籤)轉為 SRT / VTT / 純文字。

FunASR AutoModel 搭配 spk_model 時,generate() 回傳結果中的 ``sentence_info``
是一個 list,每個元素形如::

    {"text": "你好", "start": 1230, "end": 2890, "spk": 0}

start / end 單位為毫秒,spk 為語者編號(從 0 開始)。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Segment:
    """一段字幕:起訖時間(毫秒)、文字、語者編號。"""

    start_ms: int
    end_ms: int
    text: str
    speaker: int | None = None


@dataclass
class SubtitleOptions:
    """輸出選項。"""

    # 相同語者且間隔小於此毫秒數的相鄰句子會合併為同一條字幕
    merge_gap_ms: int = 800
    # 合併後單條字幕的最大長度(字元數),超過就不再合併
    max_chars: int = 42
    # 語者顯示名稱對照表,例如 {0: "主持人", 1: "來賓"}
    speaker_names: dict[int, str] = field(default_factory=dict)
    # 是否在字幕文字前加上語者標籤
    show_speaker: bool = True
    # 是否將簡體輸出轉為繁體中文(台灣正體 + 台灣用語)
    traditional: bool = True


def sentence_info_to_segments(sentence_info: list[dict]) -> list[Segment]:
    """將 FunASR 的 sentence_info 轉為 Segment 列表。

    容忍缺少 spk 欄位的情況(未啟用語者分離時 speaker 為 None)。
    """
    segments: list[Segment] = []
    for item in sentence_info:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            Segment(
                start_ms=int(item["start"]),
                end_ms=int(item["end"]),
                text=text,
                speaker=item.get("spk"),
            )
        )
    return segments


def merge_segments(segments: list[Segment], options: SubtitleOptions) -> list[Segment]:
    """合併相鄰、同語者、間隔短的片段,讓字幕不要太碎。"""
    if not segments:
        return []

    merged: list[Segment] = [
        Segment(segments[0].start_ms, segments[0].end_ms, segments[0].text, segments[0].speaker)
    ]
    for seg in segments[1:]:
        last = merged[-1]
        gap = seg.start_ms - last.end_ms
        same_speaker = seg.speaker == last.speaker
        would_fit = len(last.text) + len(seg.text) <= options.max_chars
        if same_speaker and gap <= options.merge_gap_ms and would_fit:
            last.text = f"{last.text}{seg.text}"
            last.end_ms = seg.end_ms
        else:
            merged.append(Segment(seg.start_ms, seg.end_ms, seg.text, seg.speaker))
    return merged


def _speaker_label(speaker: int | None, options: SubtitleOptions) -> str:
    if speaker is None or not options.show_speaker:
        return ""
    name = options.speaker_names.get(speaker, f"Speaker {speaker + 1}")
    return f"[{name}] "


def format_timestamp_srt(ms: int) -> str:
    """毫秒 → SRT 時間格式 ``HH:MM:SS,mmm``。"""
    if ms < 0:
        ms = 0
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def format_timestamp_vtt(ms: int) -> str:
    """毫秒 → WebVTT 時間格式 ``HH:MM:SS.mmm``。"""
    return format_timestamp_srt(ms).replace(",", ".")


def to_srt(segments: list[Segment], options: SubtitleOptions | None = None) -> str:
    """輸出 SRT 字幕內容。"""
    options = options or SubtitleOptions()
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        label = _speaker_label(seg.speaker, options)
        lines.append(str(i))
        lines.append(f"{format_timestamp_srt(seg.start_ms)} --> {format_timestamp_srt(seg.end_ms)}")
        lines.append(f"{label}{seg.text}")
        lines.append("")
    return "\n".join(lines)


def to_vtt(segments: list[Segment], options: SubtitleOptions | None = None) -> str:
    """輸出 WebVTT 字幕內容。"""
    options = options or SubtitleOptions()
    lines: list[str] = ["WEBVTT", ""]
    for seg in segments:
        label = _speaker_label(seg.speaker, options)
        lines.append(f"{format_timestamp_vtt(seg.start_ms)} --> {format_timestamp_vtt(seg.end_ms)}")
        lines.append(f"{label}{seg.text}")
        lines.append("")
    return "\n".join(lines)


def to_txt(segments: list[Segment], options: SubtitleOptions | None = None) -> str:
    """輸出純文字逐字稿(含語者標籤)。"""
    options = options or SubtitleOptions()
    lines = [f"{_speaker_label(seg.speaker, options)}{seg.text}" for seg in segments]
    return "\n".join(lines) + ("\n" if lines else "")


def build_subtitles(
    sentence_info: list[dict], options: SubtitleOptions | None = None
) -> list[Segment]:
    """從 FunASR sentence_info 產生合併後的字幕片段(單一入口)。

    語者編號沿用 cam++ 的原始聚類標籤(顯示時 +1,即 spk 0 → Speaker 1)。
    """
    options = options or SubtitleOptions()
    segments = sentence_info_to_segments(sentence_info)
    if options.traditional:
        from .convert import to_traditional

        for seg in segments:
            seg.text = to_traditional(seg.text)
    return merge_segments(segments, options)
