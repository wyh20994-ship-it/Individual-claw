"""
HangClaw Python Runner — 入口
启动 WebSocket JSON-RPC 客户端，连接 Node.js Gateway
"""

import asyncio
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agent.core import AgentCore
from rpc.client import RpcClient
from utils.logger import logger
from utils.config import load_config


async def main():
    config = load_config()

    agent = AgentCore(config)
    await agent.initialize()
    logger.info("[Runner] Agent core initialized")

    ws_url = config["runner"].get("ws_url") or "ws://127.0.0.1:3001"
    rpc = RpcClient(ws_url, agent)
    await rpc.connect() #连接 Gateway 的 WebSocket RPC Server
    logger.info(f"[Runner] Connected to Gateway at {ws_url}")

    stop_event = asyncio.Event()
    def _signal_handler():
        stop_event.set()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    await stop_event.wait()
    logger.info("[Runner] Shutting down...")
    await rpc.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
