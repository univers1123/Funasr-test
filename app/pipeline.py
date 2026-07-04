"""端到端處理流程:輸入影片/音檔 → 抽音軌 → ASR+語者分離 → 輸出字幕檔。"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .engine import DiarizationEngine
from .media import extract_audio
from .subtitle import SubtitleOptions, build_subtitles, to_srt, to_txt, to_vtt

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
    segments = build_subtitles(sentence_info, options)
    speakers = {seg.speaker for seg in segments if seg.speaker is not None}

    stem = input_path.stem
    srt_path = output_dir / f"{stem}.srt"
    vtt_path = output_dir / f"{stem}.vtt"
    txt_path = output_dir / f"{stem}.txt"
    srt_path.write_text(to_srt(segments, options), encoding="utf-8")
    vtt_path.write_text(to_vtt(segments, options), encoding="utf-8")
    txt_path.write_text(to_txt(segments, options), encoding="utf-8")

    elapsed = time.time() - t0
    report(1.0, f"完成:{len(segments)} 條字幕、{len(speakers)} 位語者、耗時 {elapsed:.1f}s")
    return PipelineResult(
        srt_path=srt_path,
        vtt_path=vtt_path,
        txt_path=txt_path,
        num_segments=len(segments),
        num_speakers=len(speakers),
        elapsed_sec=elapsed,
    )
