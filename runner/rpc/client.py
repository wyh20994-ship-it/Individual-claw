"""
WebSocket JSON-RPC Client — 连接 Node.js Gateway
"""

from __future__ import annotations
import json
import asyncio
from typing import Any

import websockets

from rpc.handlers import dispatch
from utils.logger import logger


class RpcClient:
    def __init__(self, url: str, agent):
        self.url = url
        self.agent = agent
        self._ws = None
        self._running = False

    async def connect(self):
        self._ws = await websockets.connect(self.url)
        self._running = True
        asyncio.create_task(self._listen())

    async def _listen(self):
        try:
            async for raw in self._ws:
                try:
                    request = json.loads(raw)
                    response = await dispatch(request, self.agent)
                    await self._ws.send(json.dumps(response, ensure_ascii=False))
                except json.JSONDecodeError:
                    logger.error("[RPC] Invalid JSON received")
                except Exception as e:
                    logger.error(f"[RPC] Handler error: {e}")
        except websockets.ConnectionClosed:
            logger.warning("[RPC] Connection to Gateway closed")
            self._running = False

    async def close(self):
        self._running = False
        if self._ws:
            await self._ws.close()
