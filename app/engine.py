"""FunASR 推論引擎:Paraformer-large(中文 ASR)+ fsmn-vad + ct-punc + cam++(語者分離)。

模型會在第一次使用時從 ModelScope 自動下載並快取(預設 ~/.cache/modelscope,
Docker 版透過 volume 掛載持久化)。
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# FunASR 模型別名(FunASR 會解析為 ModelScope 上的完整模型 ID)
ASR_MODEL = os.environ.get("ASR_MODEL", "paraformer-zh")   # Paraformer-large 中文
VAD_MODEL = os.environ.get("VAD_MODEL", "fsmn-vad")        # 語音活動偵測(長音檔分段)
PUNC_MODEL = os.environ.get("PUNC_MODEL", "ct-punc")       # 標點恢復
SPK_MODEL = os.environ.get("SPK_MODEL", "cam++")           # 語者分離 (campplus)


def pick_device() -> str:
    """有 CUDA 用 GPU,否則退回 CPU。可用環境變數 DEVICE 強制指定。"""
    forced = os.environ.get("DEVICE")
    if forced:
        return forced
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


class DiarizationEngine:
    """封裝 FunASR AutoModel,提供「音檔 → 帶語者標籤的句子列表」。"""

    def __init__(self, device: str | None = None, enable_speaker: bool = True):
        self.device = device or pick_device()
        self.enable_speaker = enable_speaker
        self._model: Any = None

    def load(self) -> None:
        """載入(或下載)模型,第一次呼叫較慢。"""
        if self._model is not None:
            return
        from funasr import AutoModel

        logger.info("載入 FunASR 模型(device=%s, speaker=%s)…", self.device, self.enable_speaker)
        kwargs: dict[str, Any] = dict(
            model=ASR_MODEL,
            vad_model=VAD_MODEL,
            punc_model=PUNC_MODEL,
            device=self.device,
            disable_update=True,
        )
        if self.enable_speaker:
            kwargs["spk_model"] = SPK_MODEL
        self._model = AutoModel(**kwargs)
        logger.info("模型載入完成")

    def transcribe(self, wav_path: str, hotword: str = "") -> list[dict]:
        """辨識 16kHz mono WAV,回傳 sentence_info 列表。

        每個元素:{"text": str, "start": ms, "end": ms, "spk": int}
        """
        self.load()
        results = self._model.generate(
            input=wav_path,
            batch_size_s=300,
            hotword=hotword,
        )
        if not results:
            return []
        result = results[0]
        sentence_info = result.get("sentence_info")
        if sentence_info:
            return sentence_info
        # 未啟用 spk_model 時沒有 sentence_info,退化為單一片段
        text = (result.get("text") or "").strip()
        if not text:
            return []
        timestamps = result.get("timestamp") or []
        start = timestamps[0][0] if timestamps else 0
        end = timestamps[-1][1] if timestamps else 0
        return [{"text": text, "start": start, "end": end}]
