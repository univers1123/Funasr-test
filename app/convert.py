"""簡體 → 繁體(台灣用語)轉換,使用 OpenCC s2twp。

Paraformer 的輸出是簡體中文;s2twp 除了轉字形也會轉換常見用語
(例如「软件 → 軟體」、「视频 → 影片」)。
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _get_converter():
    from opencc import OpenCC

    return OpenCC("s2twp")


def to_traditional(text: str) -> str:
    """簡體轉繁體(台灣正體 + 台灣用語)。"""
    if not text:
        return text
    return _get_converter().convert(text)
