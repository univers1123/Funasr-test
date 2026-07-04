# 🎙️ 語者分離字幕生成系統(v0.1 — Phase 1~4 第一版)

在本地端運行的影片語者分離(Speaker Diarization)+ 中文語音辨識字幕生成系統。
上傳影片或音檔,自動輸出帶語者標籤的 SRT / VTT / 逐字稿:

```
1
00:00:00,000 --> 00:00:03,600
[Speaker 1] 大家好,歡迎收聽本集節目。

2
00:00:04,200 --> 00:00:06,000
[Speaker 2] 謝謝主持人邀請。
```

## 技術架構

| 模組 | 技術 |
|---|---|
| 中文語音辨識 | FunASR Paraformer-large(`paraformer-zh`,內建標點 `ct-punc` 與時間戳) |
| 語音活動偵測 | `fsmn-vad`(長音檔自動分段,避免顯存不足) |
| 語者分離 | `cam++`(campplus,與 ASR 同源整合) |
| 音軌抽取 | ffmpeg(16kHz mono WAV) |
| 繁體轉換 | OpenCC `s2twp`(簡體 → 台灣正體 + 台灣用語,預設開啟) |
| Web 介面 | Gradio(上傳 → 進度 → 字幕預覽播放 → 下載) |
| 部署 | Docker Compose + NVIDIA GPU |

**語者命名:** 處理完成後,Web UI 會顯示「語者一覽」(每位語者的首次發言
時間與例句),對照填入名稱(如 `1=主持人,2=來賓`)按「套用名稱重新輸出」
即可,不需重跑辨識,秒級完成。

## 快速開始(Docker,建議)

需求:Docker Desktop(WSL2 後端)、NVIDIA GPU(建議 RTX 4070 / 12GB 以上)與驅動。

```bash
# 1. 檢查環境
bash scripts/check_env.sh

# 2. 啟動(首次會 build image 並在第一次處理時下載約 1-2GB 模型)
docker compose up --build

# 3. 開啟瀏覽器
#    http://localhost:7860
```

模型會快取在 Docker volume(`modelscope-cache`),之後啟動不需重新下載。
輸出字幕檔同時會寫到宿主機的 `./output/`。

### 沒有 GPU?

改用 CPU(速度慢很多,僅供測試):把 `docker-compose.yml` 的
`DEVICE=cuda:0` 改為 `DEVICE=cpu`,並移除 `deploy.resources` 區塊。

## 本地開發(不用 Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # torch 請依 https://pytorch.org 選擇 CUDA 版本
sudo apt install ffmpeg

# 命令列
python -m app.cli input.mp4 -o output/ --speaker-names "1=主持人,2=來賓"

# Web 介面
python -m app.webui   # http://localhost:7860
```

### CLI 參數

| 參數 | 說明 |
|---|---|
| `-o / --output-dir` | 輸出目錄(預設 `output/`) |
| `--device` | `cuda:0` / `cpu`(預設自動偵測) |
| `--no-speaker` | 停用語者分離,只做 ASR |
| `--hotword` | 熱詞(空白分隔),提升專有名詞辨識率 |
| `--speaker-names` | 語者顯示名稱,如 `"1=主持人,2=來賓"` |
| `--merge-gap-ms` | 同語者相鄰句合併間隔上限(預設 800ms) |
| `--max-chars` | 單條字幕最大字元數(預設 42) |
| `--simplified` | 保留簡體輸出(預設轉繁體台灣用語) |
| `--num-speakers` | 實際語者人數(已知時指定可提升分離準度,預設自動偵測) |

## 播放字幕

- **Web 介面內直接看**:輸入是影片時,處理完成後右側會出現帶字幕的預覽播放器
- **影片播放器**:把下載的 `.srt` 改成與影片同名放同一資料夾
  (如 `訪談.mp4` + `訪談.srt`),VLC / PotPlayer / MPC-HC 會自動載入
- **YouTube / 剪輯軟體**:上傳 `.srt`(YouTube 字幕後台)或 `.vtt`(網頁播放器)皆可

## 執行測試

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

單元測試涵蓋字幕合併邏輯與輸出格式,不需要 GPU 或下載模型。
`samples/expected_output.srt` 為預期輸出格式範例。

## 專案結構

```
app/
  engine.py     # FunASR AutoModel 封裝(ASR + VAD + 標點 + 語者分離)
  media.py      # ffmpeg 音軌抽取(16kHz mono WAV)
  subtitle.py   # sentence_info → 合併 → SRT/VTT/TXT
  pipeline.py   # 端到端流程 + 進度回報
  cli.py        # 命令列介面
  webui.py      # Gradio Web 介面
tests/          # 單元測試(無需模型)
scripts/        # 環境檢查腳本
```

## 常見問題

**Q: 容器一直重啟 / 啟動就崩潰?**
先看崩潰原因:`docker compose logs --tail=50 subtitle`。
再用 CPU 模式排查是否為 GPU 掛載問題:
`docker compose -f docker-compose.cpu.yml up --build`
(能啟動就代表程式正常,問題出在 GPU passthrough 或驅動。)

**Q: RTX 50 系列(5060 Ti / 5070…)跑不起來?**
Blackwell 架構需要 CUDA 12.8 以上。本專案 base image 已用
`pytorch 2.7.1 + cu128`;若你改過 Dockerfile,請勿降到 cu121 以下,
並把 NVIDIA 驅動更新到 570 以上。

**Q: 容器啟動失敗,顯示 GPU 相關錯誤?**
先跑 `bash scripts/check_env.sh`。常見原因:Docker Desktop 未啟用 WSL2 整合、
NVIDIA 驅動太舊(需支援 CUDA 12.8)。

**Q: WSL2 / Docker Desktop 整個掛掉重啟?**
可能是記憶體不足(模型載入需 4GB 以上)。在 Windows 使用者目錄建立
`.wslconfig` 提高上限後執行 `wsl --shutdown` 再重開 Docker Desktop:
```ini
[wsl2]
memory=12GB
swap=8GB
```

**Q: 首次處理很久沒反應?**
第一次執行會從 ModelScope 下載約 1-2GB 模型,請看容器 log(`docker compose logs -f`)。

**Q: 長影片跑到一半中斷?**
`fsmn-vad` 已自動分段(`batch_size_s=300`);若仍不足,可先用 ffmpeg 把檔案切段處理。

**Q: 語者數量判斷錯誤?**
已知實際人數時,在 Web UI 填「語者人數」或 CLI 加 `--num-speakers N`,
會直接指定聚類數量,準度明顯提升。自動偵測時,重疊語音、笑聲、
背景音都可能被誤判成額外語者(已知限制,見計畫書風險評估)。

## 已知限制(MVP)

- 針對中文優化;其他語言準度未驗證
- 多人重疊說話時 diarization 可能誤判
- 尚無批次處理與時間軸微調介面(第二階段)
