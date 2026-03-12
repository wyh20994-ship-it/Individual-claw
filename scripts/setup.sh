#!/usr/bin/env bash
# HangClaw 环境初始化脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== HangClaw Setup ==="

# 1. Node.js 依赖
echo "[1/3] Installing Node.js dependencies..."
cd "$ROOT_DIR/gateway"
npm install

# 2. Python 依赖
echo "[2/3] Installing Python dependencies..."
cd "$ROOT_DIR/runner"
pip install -r requirements.txt

# 3. 配置文件
echo "[3/3] Checking config..."
if [ ! -f "$ROOT_DIR/.env" ]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    echo "  Created .env from template — please edit it with your API keys!"
else
    echo "  .env already exists"
fi

echo ""
echo "=== Setup Complete ==="
echo "  Next: edit .env, then run: scripts/start.sh"
