#!/usr/bin/env bash
# 環境檢查腳本:確認 Docker、NVIDIA 驅動、GPU passthrough 是否就緒
set -u

ok()   { echo "✅ $1"; }
fail() { echo "❌ $1"; FAILED=1; }
FAILED=0

echo "=== 語者分離字幕生成系統 環境檢查 ==="

if command -v docker >/dev/null 2>&1; then
    ok "Docker 已安裝:$(docker --version)"
else
    fail "找不到 Docker,請安裝 Docker Desktop(含 WSL2 後端)"
fi

if docker compose version >/dev/null 2>&1; then
    ok "Docker Compose 可用"
else
    fail "Docker Compose 不可用,請更新 Docker Desktop"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
    ok "NVIDIA 驅動:$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1)"
else
    fail "找不到 nvidia-smi,請安裝 NVIDIA 驅動(Windows 主機驅動即可,WSL2 會自動帶入)"
fi

if docker run --rm --gpus all ubuntu:22.04 true >/dev/null 2>&1; then
    ok "Docker GPU passthrough 正常"
else
    fail "Docker 無法存取 GPU:請確認 Docker Desktop 設定啟用 WSL2 整合與 GPU 支援"
fi

if [ "$FAILED" -eq 0 ]; then
    echo ""
    echo "🎉 環境就緒,執行:docker compose up --build"
else
    echo ""
    echo "請先排除上述問題,詳見 README 的常見問題章節。"
    exit 1
fi
