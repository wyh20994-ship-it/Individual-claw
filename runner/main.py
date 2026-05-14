import asyncio
import os
import signal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agent.core import AgentCore
from rpc.client import RpcClient
from utils.config import load_config
from utils.logger import logger


async def main():
    config = load_config()

    agent = AgentCore(config)
    await agent.initialize()
    logger.info("[Runner] Agent core initialized")

    ws_url = os.getenv("RUNNER_WS_URL") or config["runner"].get("ws_url") or "ws://127.0.0.1:3001"
    rpc = RpcClient(ws_url, agent)
    await rpc.connect()

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
