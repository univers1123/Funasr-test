"""端到端處理流程:輸入影片/音檔 → 抽音軌 → ASR+語者分離 → 輸出字幕檔。"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .engine import DiarizationEngine
from .media import extract_audio
from .subtitle import SubtitleOptions, build_subtitles, to_srt, to_txt, to_vtt


def speaker_overview(sentence_info: list[dict], max_chars: int = 30) -> list[list]:
    """每位語者的首次發言時間與例句,協助辨認「誰是誰」。

    回傳列(依語者編號排序):[Speaker 標籤, 首次發言時間, 例句]
    """
    from .subtitle import format_timestamp_srt

    seen: dict[int, list] = {}
    for item in sentence_info:
        spk = item.get("spk")
        text = (item.get("text") or "").strip()
        if spk is None or not text or spk in seen:
            continue
        stamp = format_timestamp_srt(int(item["start"]))[:8]  # HH:MM:SS
        seen[spk] = [f"Speaker {spk + 1}", stamp, text[:max_chars]]
    return [seen[k] for k in sorted(seen)]

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


@dataclass
class PipelineResult:
    srt_path: Path
    vtt_path: Path
    txt_path: Path
    num_segments: int
    num_speakers: int
    elapsed_sec: float
    # 原始辨識結果,保留供「改語者名稱後重新輸出」使用(不需重跑 ASR)
    sentence_info: list[dict] = field(default_factory=list)


def write_outputs(
    sentence_info: list[dict],
    stem: str,
    output_dir: str | Path,
    options: SubtitleOptions | None = None,
) -> PipelineResult:
    """從辨識結果產生 SRT / VTT / TXT。改語者名稱時可重複呼叫,秒級完成。"""
    t0 = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    options = options or SubtitleOptions()

    segments = build_subtitles(sentence_info, options)
    speakers = {seg.speaker for seg in segments if seg.speaker is not None}

    srt_path = output_dir / f"{stem}.srt"
    vtt_path = output_dir / f"{stem}.vtt"
    txt_path = output_dir / f"{stem}.txt"
    srt_path.write_text(to_srt(segments, options), encoding="utf-8")
    vtt_path.write_text(to_vtt(segments, options), encoding="utf-8")
    txt_path.write_text(to_txt(segments, options), encoding="utf-8")

    return PipelineResult(
        srt_path=srt_path,
        vtt_path=vtt_path,
        txt_path=txt_path,
        num_segments=len(segments),
        num_speakers=len(speakers),
        elapsed_sec=time.time() - t0,
        sentence_info=sentence_info,
    )


def process_file(
    input_path: str | Path,
    output_dir: str | Path,
    engine: DiarizationEngine | None = None,
    options: SubtitleOptions | None = None,
    hotword: str = "",
    num_speakers: int | None = None,
    progress: ProgressCallback | None = None,
) -> PipelineResult:
    """處理單一檔案,輸出 SRT / VTT / TXT 到 output_dir。"""
    t0 = time.time()
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    options = options or SubtitleOptions()
    engine = engine or DiarizationEngine()

    def report(pct: float, msg: str) -> None:
        logger.info("[%3.0f%%] %s", pct * 100, msg)
        if progress:
            progress(pct, msg)

    report(0.05, "抽取音軌中…")
    with tempfile.TemporaryDirectory(prefix="funasr_") as tmp:
        wav_path = extract_audio(input_path, Path(tmp) / "audio.wav")

        report(0.15, "載入模型(首次執行需下載,請稍候)…")
        engine.load()

        report(0.30, "語音辨識 + 語者分離中…")
        sentence_info = engine.transcribe(
            str(wav_path), hotword=hotword, num_speakers=num_speakers
        )

    report(0.85, "產生字幕檔…")
    result = write_outputs(sentence_info, input_path.stem, output_dir, options)
    result.elapsed_sec = time.time() - t0
    report(
        1.0,
        f"完成:{result.num_segments} 條字幕、{result.num_speakers} 位語者、"
        f"耗時 {result.elapsed_sec:.1f}s",
    )
    return result
