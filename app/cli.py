"""命令列介面:python -m app.cli input.mp4 -o output/"""

from __future__ import annotations

import argparse
import logging
import sys

from .engine import DiarizationEngine
from .media import MediaError
from .pipeline import process_file
from .subtitle import SubtitleOptions


def parse_speaker_names(raw: str | None) -> dict[int, str]:
    """解析 "1=主持人,2=來賓" 為 {0: "主持人", 1: "來賓"}(輸入 1-based)。"""
    if not raw:
        return {}
    mapping: dict[int, str] = {}
    for pair in raw.split(","):
        idx, _, name = pair.partition("=")
        idx = idx.strip()
        name = name.strip()
        if not idx.isdigit() or not name:
            raise argparse.ArgumentTypeError(f"語者名稱格式錯誤:{pair!r}(範例:1=主持人,2=來賓)")
        mapping[int(idx) - 1] = name
    return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="語者分離字幕生成(FunASR Paraformer + cam++)")
    parser.add_argument("input", help="輸入影片或音檔路徑")
    parser.add_argument("-o", "--output-dir", default="output", help="輸出目錄(預設 output/)")
    parser.add_argument("--device", default=None, help="推論裝置,如 cuda:0 或 cpu(預設自動)")
    parser.add_argument("--no-speaker", action="store_true", help="停用語者分離(僅 ASR)")
    parser.add_argument("--hotword", default="", help="熱詞,以空白分隔,可提升專有名詞辨識")
    parser.add_argument("--speaker-names", default=None, help='語者名稱,如 "1=主持人,2=來賓"')
    parser.add_argument("--merge-gap-ms", type=int, default=800, help="同語者合併間隔上限(毫秒)")
    parser.add_argument("--max-chars", type=int, default=42, help="單條字幕最大字元數")
    parser.add_argument("--simplified", action="store_true", help="保留簡體輸出(預設轉繁體)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        speaker_names = parse_speaker_names(args.speaker_names)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    options = SubtitleOptions(
        merge_gap_ms=args.merge_gap_ms,
        max_chars=args.max_chars,
        speaker_names=speaker_names,
        show_speaker=not args.no_speaker,
        traditional=not args.simplified,
    )
    engine = DiarizationEngine(device=args.device, enable_speaker=not args.no_speaker)

    try:
        result = process_file(
            args.input, args.output_dir, engine=engine, options=options, hotword=args.hotword
        )
    except MediaError as exc:
        print(f"錯誤:{exc}", file=sys.stderr)
        return 1
    print(f"SRT: {result.srt_path}")
    print(f"VTT: {result.vtt_path}")
    print(f"TXT: {result.txt_path}")
    print(f"字幕 {result.num_segments} 條、語者 {result.num_speakers} 位、耗時 {result.elapsed_sec:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
