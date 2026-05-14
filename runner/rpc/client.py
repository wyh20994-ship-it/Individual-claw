from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from rpc.handlers import dispatch
from utils.logger import logger


class RpcClient:
    def __init__(self, url: str, agent, reconnect_min_delay: float = 1.0, reconnect_max_delay: float = 30.0):
        self.url = url
        self.agent = agent
        self.reconnect_min_delay = reconnect_min_delay
        self.reconnect_max_delay = reconnect_max_delay
        self._ws: Any | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def connect(self):
        self._running = True
        self._task = asyncio.create_task(self._connect_loop())

    async def _connect_loop(self):
        delay = self.reconnect_min_delay
        while self._running:
            try:
                logger.info(f"[RPC] Connecting to Gateway: {self.url}")
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws = ws
                    delay = self.reconnect_min_delay
                    logger.info(f"[RPC] Connected to Gateway: {self.url}")
                    await self._listen(ws)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self._running:
                    logger.warning(f"[RPC] Gateway connection failed: {e}; retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.reconnect_max_delay)
            finally:
                self._ws = None

    async def _listen(self, ws):
        try:
            async for raw in ws:
                try:
                    request = json.loads(raw)
                    response = await dispatch(request, self.agent)
                    await ws.send(json.dumps(response, ensure_ascii=False))
                except json.JSONDecodeError:
                    logger.error("[RPC] Invalid JSON received")
                except Exception as e:
                    logger.exception(f"[RPC] Handler error: {e}")
        except ConnectionClosed:
            logger.warning("[RPC] Connection to Gateway closed")

    async def close(self):
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
