"""Gradio Web 介面:上傳影片/音檔 → 進度顯示 → 下載 SRT/VTT/TXT。

處理完成後會顯示「語者一覽」(每位語者的首次發言時間與例句),
可在下方填入語者名稱後重新輸出字幕,不需要重跑辨識。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import gradio as gr

from .cli import parse_speaker_names
from .convert import to_traditional
from .engine import DiarizationEngine
from .media import is_video
from .pipeline import process_file, speaker_overview, write_outputs
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


def _build_result_views(result, file_path: str):
    """把 PipelineResult 轉成 UI 輸出(摘要、預覽、下載、播放器)。"""
    preview = result.srt_path.read_text(encoding="utf-8")
    if len(preview) > 4000:
        preview = preview[:4000] + "\n…(僅顯示前段,完整內容請下載檔案)"
    summary = (
        f"✅ 完成:{result.num_segments} 條字幕、{result.num_speakers} 位語者、"
        f"耗時 {result.elapsed_sec:.1f} 秒"
    )
    files = [str(result.srt_path), str(result.vtt_path), str(result.txt_path)]
    # 輸入是影片時,提供「影片 + 字幕」預覽播放。
    # 注意:Gradio 6 的 Video.postprocess 不接受 (video, subtitle) tuple
    # (文件寫可以但實作是壞的),必須用元件更新的方式帶 subtitles
    if file_path and is_video(file_path):
        player = gr.Video(value=file_path, subtitles=str(result.vtt_path))
    else:
        player = gr.Video(value=None)
    return summary, preview, files, player


def _overview_rows(sentence_info: list[dict], traditional: bool) -> list[list]:
    rows = speaker_overview(sentence_info)
    if traditional:
        for row in rows:
            row[2] = to_traditional(row[2])
    return rows


def run(
    file_path: str | None,
    hotword: str,
    show_speaker: bool,
    traditional: bool,
    num_speakers: float | None,
    progress: gr.Progress = gr.Progress(),
):
    if not file_path:
        raise gr.Error("請先上傳影片或音檔")

    options = SubtitleOptions(show_speaker=show_speaker, traditional=traditional)

    def on_progress(pct: float, msg: str) -> None:
        progress(pct, desc=msg)

    try:
        result = process_file(
            file_path,
            OUTPUT_DIR,
            engine=get_engine(),
            options=options,
            hotword=hotword or "",
            num_speakers=int(num_speakers) if num_speakers else None,
            progress=on_progress,
        )
    except Exception as exc:  # noqa: BLE001
        logging.exception("處理失敗")
        raise gr.Error(f"處理失敗:{exc}") from exc

    summary, preview, files, player = _build_result_views(result, file_path)
    # 快取辨識結果,供「套用語者名稱」重新輸出使用(不需重跑 ASR)
    state = {"sentence_info": result.sentence_info, "file_path": file_path}
    overview = _overview_rows(result.sentence_info, traditional)
    return summary, preview, files, player, state, overview


def apply_names(
    state: dict | None,
    names_raw: str,
    show_speaker: bool,
    traditional: bool,
):
    if not state or not state.get("sentence_info"):
        raise gr.Error("請先完成一次辨識,才能套用語者名稱")
    try:
        speaker_names = parse_speaker_names(names_raw or None)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"語者名稱格式錯誤:{exc}(範例:1=主持人,2=來賓)") from exc

    options = SubtitleOptions(
        speaker_names=speaker_names, show_speaker=show_speaker, traditional=traditional
    )
    file_path = state["file_path"]
    result = write_outputs(
        state["sentence_info"], Path(file_path).stem, OUTPUT_DIR, options
    )
    summary, preview, files, player = _build_result_views(result, file_path)
    return summary, preview, files, player


def build_app() -> gr.Blocks:
    with gr.Blocks(title="語者分離字幕生成") as demo:
        gr.Markdown(
            "# 🎙️ 語者分離字幕生成系統\n"
            "上傳影片或音檔,自動進行中文語音辨識(FunASR Paraformer)與語者分離(cam++),"
            "輸出帶語者標籤的 SRT / VTT / 逐字稿。首次執行需下載模型,請耐心等候。"
        )
        result_state = gr.State(None)
        with gr.Row():
            with gr.Column():
                file_input = gr.File(
                    label="影片 / 音檔(mp4、mp3、wav…)",
                    file_types=["video", "audio"],
                    type="filepath",
                )
                show_speaker = gr.Checkbox(value=True, label="字幕加上語者標籤")
                traditional = gr.Checkbox(value=True, label="轉為繁體中文(台灣用語)")
                num_speakers = gr.Number(
                    label="語者人數(選填)",
                    value=None,
                    precision=0,
                    minimum=0,
                    info="已知影片中有幾個人說話時填入,可提升分離準度;留空為自動偵測",
                )
                hotword = gr.Textbox(
                    label="熱詞(選填,空白分隔)",
                    placeholder="例:范倫鐵諾 帕拉梅拉",
                )
                submit = gr.Button("開始處理", variant="primary")

                gr.Markdown("### 語者命名(處理完成後)")
                overview = gr.Dataframe(
                    headers=["語者", "首次發言", "例句"],
                    label="語者一覽",
                    interactive=False,
                )
                speaker_names = gr.Textbox(
                    label="語者名稱",
                    placeholder="例:1=主持人,2=來賓(對照上方一覽表填寫)",
                )
                rename = gr.Button("套用名稱重新輸出")
            with gr.Column():
                summary = gr.Textbox(label="結果摘要", interactive=False)
                player = gr.Video(label="字幕預覽播放(影片輸入時)", interactive=False)
                preview = gr.Textbox(label="SRT 預覽", lines=12, interactive=False)
                downloads = gr.File(label="下載字幕檔", file_count="multiple")

        submit.click(
            run,
            inputs=[file_input, hotword, show_speaker, traditional, num_speakers],
            outputs=[summary, preview, downloads, player, result_state, overview],
        )
        rename.click(
            apply_names,
            inputs=[result_state, speaker_names, show_speaker, traditional],
            outputs=[summary, preview, downloads, player],
        )
    return demo


def main() -> None:
    demo = build_app()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    demo.queue(max_size=8).launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        # 字幕檔寫在 OUTPUT_DIR,必須加入允許清單 Gradio 才肯提供下載
        allowed_paths=[str(OUTPUT_DIR.resolve())],
    )


if __name__ == "__main__":
    main()
