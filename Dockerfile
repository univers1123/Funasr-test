# 語者分離字幕生成系統 — GPU 推論 image
# base image 已含 PyTorch + CUDA runtime,免去使用者處理 CUDA 依賴
# 注意:RTX 50 系列(Blackwell, sm_120)需要 CUDA 12.8 以上,勿降版
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    OUTPUT_DIR=/data/output

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# torch/torchaudio 已由 base image 提供,避免 pip 重抓 CUDA wheel
COPY requirements.txt .
RUN grep -vE '^(torch|torchaudio)' requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY app ./app

EXPOSE 7860

# 模型快取掛載點(docker-compose 會掛 volume,避免每次重下載)
VOLUME ["/root/.cache/modelscope", "/data/output"]

CMD ["python", "-m", "app.webui"]
