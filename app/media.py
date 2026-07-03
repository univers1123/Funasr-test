"""音軌抽取模組:用 ffmpeg 把影片/音檔轉成 16kHz 單聲道 WAV(FunASR 的輸入格式)。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma",
}


class MediaError(RuntimeError):
    pass


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise MediaError("找不到 ffmpeg,請先安裝(Docker 版已內建)。")
    return path


def extract_audio(input_path: str | Path, output_wav: str | Path) -> Path:
    """抽取音軌並重取樣為 16kHz mono PCM WAV。

    影片與音檔皆可,ffmpeg 會自動解出音軌。
    """
    input_path = Path(input_path)
    output_wav = Path(output_wav)
    if not input_path.exists():
        raise MediaError(f"找不到輸入檔案:{input_path}")
    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise MediaError(
            f"不支援的檔案格式:{input_path.suffix}(支援:{', '.join(sorted(SUPPORTED_EXTENSIONS))})"
        )

    ffmpeg = ensure_ffmpeg()
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i", str(input_path),
        "-vn",              # 去除影像
        "-ac", "1",         # 單聲道
        "-ar", "16000",     # 16kHz
        "-acodec", "pcm_s16le",
        str(output_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg 轉檔失敗:\n{proc.stderr[-2000:]}")
    return output_wav
