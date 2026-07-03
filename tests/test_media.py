"""media 模組測試:格式檢查不需要 ffmpeg;轉檔測試在 ffmpeg 存在時執行。"""

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app.media import MediaError, extract_audio

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def test_rejects_missing_file(tmp_path):
    with pytest.raises(MediaError, match="找不到輸入檔案"):
        extract_audio(tmp_path / "nope.mp4", tmp_path / "out.wav")


def test_rejects_unsupported_extension(tmp_path):
    bad = tmp_path / "file.xyz"
    bad.write_bytes(b"data")
    with pytest.raises(MediaError, match="不支援的檔案格式"):
        extract_audio(bad, tmp_path / "out.wav")


@pytest.mark.skipif(not HAS_FFMPEG, reason="需要 ffmpeg")
def test_extracts_16k_mono_wav(tmp_path):
    # 用 ffmpeg 產生 1 秒 440Hz 立體聲 44.1kHz 測試音檔
    src = tmp_path / "tone.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1:sample_rate=44100",
            "-ac", "2", str(src),
        ],
        check=True,
        capture_output=True,
    )
    out = extract_audio(src, tmp_path / "out.wav")
    assert out.exists()
    with wave.open(str(out)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
