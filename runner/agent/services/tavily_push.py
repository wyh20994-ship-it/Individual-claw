"""
Tavily 资讯日报推送服务
定时搜索 AI/科技热点，生成摘要后推送到各渠道
"""

from __future__ import annotations
import os
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.logger import logger


class TavilyDailyService:
    def __init__(self, config: dict = None):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        self.cron = os.getenv("TAVILY_PUSH_CRON", "0 8 * * *")
        self.scheduler: AsyncIOScheduler | None = None

    async def search_news(self, query: str = "AI technology news today", max_results: int = 8) -> list[dict]:
        """搜索最新资讯"""
        if not self.api_key:
            logger.warning("[TavilyDaily] TAVILY_API_KEY not set")
            return []

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "topic": "news",
                },
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    async def generate_daily(self) -> str:
        """生成日报文本"""
        results = await self.search_news()
        if not results:
            return "今日暂无资讯"

        lines = ["📰 **HangClaw AI 日报**\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"**{i}. {r.get('title', '')}**")
            lines.append(f"   {r.get('content', '')[:200]}")
            lines.append(f"   🔗 {r.get('url', '')}\n")
        return "\n".join(lines)

    def start_scheduler(self, push_callback):
        """启动定时推送"""
        parts = self.cron.split()
        if len(parts) != 5:
            logger.error(f"[TavilyDaily] Invalid cron: {self.cron}")
            return

        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            push_callback,
            "cron",
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        self.scheduler.start()
        logger.info(f"[TavilyDaily] Scheduler started: {self.cron}")
