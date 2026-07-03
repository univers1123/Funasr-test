"""Gradio Web 介面:上傳影片/音檔 → 進度顯示 → 下載 SRT/VTT/TXT。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import gradio as gr

from .cli import parse_speaker_names
from .engine import DiarizationEngine
from .pipeline import process_file
from .subtitle import SubtitleOptions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))

# 全域單例:模型只載入一次,之後的請求直接重用
_engine: DiarizationEngine | None = None


def get_engine() -> DiarizationEngine:
    global _engine
    if _engine is None:
        _engine = DiarizationEngine()
    return _engine


def run(
    file_path: str | None,
    speaker_names_raw: str,
    hotword: str,
    show_speaker: bool,
    progress: gr.Progress = gr.Progress(),
):
    if not file_path:
        raise gr.Error("請先上傳影片或音檔")
    try:
        speaker_names = parse_speaker_names(speaker_names_raw or None)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"語者名稱格式錯誤:{exc}") from exc

    options = SubtitleOptions(speaker_names=speaker_names, show_speaker=show_speaker)

    def on_progress(pct: float, msg: str) -> None:
        progress(pct, desc=msg)

    try:
        result = process_file(
            file_path,
            OUTPUT_DIR,
            engine=get_engine(),
            options=options,
            hotword=hotword or "",
            progress=on_progress,
        )
    except Exception as exc:  # noqa: BLE001
        logging.exception("處理失敗")
        raise gr.Error(f"處理失敗:{exc}") from exc

    preview = result.srt_path.read_text(encoding="utf-8")
    if len(preview) > 4000:
        preview = preview[:4000] + "\n…(僅顯示前段,完整內容請下載檔案)"
    summary = (
        f"✅ 完成:{result.num_segments} 條字幕、偵測到 {result.num_speakers} 位語者、"
        f"耗時 {result.elapsed_sec:.1f} 秒"
    )
    files = [str(result.srt_path), str(result.vtt_path), str(result.txt_path)]
    return summary, preview, files


def build_app() -> gr.Blocks:
    with gr.Blocks(title="語者分離字幕生成") as demo:
        gr.Markdown(
            "# 🎙️ 語者分離字幕生成系統\n"
            "上傳影片或音檔,自動進行中文語音辨識(FunASR Paraformer)與語者分離(cam++),"
            "輸出帶語者標籤的 SRT / VTT / 逐字稿。首次執行需下載模型,請耐心等候。"
        )
        with gr.Row():
            with gr.Column():
                file_input = gr.File(
                    label="影片 / 音檔(mp4、mp3、wav…)",
                    file_types=["video", "audio"],
                    type="filepath",
                )
                show_speaker = gr.Checkbox(value=True, label="字幕加上語者標籤")
                speaker_names = gr.Textbox(
                    label="語者名稱(選填)",
                    placeholder="例:1=主持人,2=來賓",
                )
                hotword = gr.Textbox(
                    label="熱詞(選填,空白分隔)",
                    placeholder="例:范倫鐵諾 帕拉梅拉",
                )
                submit = gr.Button("開始處理", variant="primary")
            with gr.Column():
                summary = gr.Textbox(label="結果摘要", interactive=False)
                preview = gr.Textbox(label="SRT 預覽", lines=18, interactive=False)
                downloads = gr.File(label="下載字幕檔", file_count="multiple")

        submit.click(
            run,
            inputs=[file_input, speaker_names, hotword, show_speaker],
            outputs=[summary, preview, downloads],
        )
    return demo


def main() -> None:
    demo = build_app()
    demo.queue(max_size=8).launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
    )


if __name__ == "__main__":
    main()
