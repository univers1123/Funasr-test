"""pipeline 純邏輯測試:輸出重建與語者一覽(不需要模型)。"""

from app.pipeline import speaker_overview, write_outputs
from app.subtitle import SubtitleOptions

SENTENCE_INFO = [
    {"text": "大家好,歡迎收看。", "start": 1000, "end": 3000, "spk": 0},
    {"text": "謝謝主持人。", "start": 4000, "end": 6000, "spk": 1},
    {"text": "我們開始吧。", "start": 7000, "end": 9000, "spk": 0},
]


class TestWriteOutputs:
    def test_writes_three_formats(self, tmp_path):
        result = write_outputs(
            SENTENCE_INFO, "demo", tmp_path, SubtitleOptions(traditional=False)
        )
        assert result.srt_path.read_text(encoding="utf-8").startswith("1\n")
        assert result.vtt_path.read_text(encoding="utf-8").startswith("WEBVTT")
        assert result.txt_path.exists()
        assert result.num_speakers == 2
        assert result.sentence_info == SENTENCE_INFO

    def test_rename_without_rerun(self, tmp_path):
        # 模擬「處理完成後套用語者名稱」:用同一份 sentence_info 重建輸出
        first = write_outputs(SENTENCE_INFO, "demo", tmp_path, SubtitleOptions(traditional=False))
        assert "[Speaker 1]" in first.srt_path.read_text(encoding="utf-8")

        renamed = write_outputs(
            first.sentence_info,
            "demo",
            tmp_path,
            SubtitleOptions(speaker_names={0: "主持人", 1: "來賓"}, traditional=False),
        )
        srt = renamed.srt_path.read_text(encoding="utf-8")
        assert "[主持人]" in srt
        assert "[來賓]" in srt
        assert "Speaker" not in srt


class TestSpeakerOverview:
    def test_first_utterance_per_speaker(self):
        rows = speaker_overview(SENTENCE_INFO)
        assert len(rows) == 2
        assert rows[0] == ["Speaker 1", "00:00:01", "大家好,歡迎收看。"]
        assert rows[1][0] == "Speaker 2"

    def test_truncates_long_text(self):
        info = [{"text": "很長" * 40, "start": 0, "end": 1000, "spk": 0}]
        rows = speaker_overview(info, max_chars=10)
        assert len(rows[0][2]) == 10

    def test_empty(self):
        assert speaker_overview([]) == []
