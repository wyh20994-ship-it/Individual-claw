#!/usr/bin/env bash
# HangClaw 一键启动脚本 (Linux/macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== HangClaw Starting ==="

# 启动 Python Runner (后台)
echo "[1/2] Starting Python Runner..."
cd "$ROOT_DIR/runner"
python main.py &
RUNNER_PID=$!
echo "  Runner PID: $RUNNER_PID"

# 等 Runner 就绪
sleep 2

# 启动 Node.js Gateway
echo "[2/2] Starting Node.js Gateway..."
cd "$ROOT_DIR/gateway"
npm run dev &
GATEWAY_PID=$!
echo "  Gateway PID: $GATEWAY_PID"

echo ""
echo "=== HangClaw Running ==="
echo "  Gateway: http://localhost:3000"
echo "  Press Ctrl+C to stop"

trap "kill $RUNNER_PID $GATEWAY_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
