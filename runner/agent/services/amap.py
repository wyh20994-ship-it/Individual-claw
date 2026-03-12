"""
高德地图生活服务 — 天气查询、POI 搜索、路线规划
需要配置 AMAP_API_KEY
"""

from __future__ import annotations
import os
from typing import Any

import httpx

from utils.logger import logger

AMAP_BASE = "https://restapi.amap.com/v3"


class AmapService:
    def __init__(self, config: dict = None):
        self.api_key = os.getenv("AMAP_API_KEY", "")

    async def weather(self, city: str) -> str:
        """查询天气"""
        if not self.api_key:
            return "错误: AMAP_API_KEY 未配置"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{AMAP_BASE}/weather/weatherInfo", params={
                "key": self.api_key,
                "city": city,
                "extensions": "all",
            })
            data = resp.json()
        forecasts = data.get("forecasts", [])
        if not forecasts:
            return f"未找到 {city} 的天气信息"
        fc = forecasts[0]
        lines = [f"📍 {fc['province']} {fc['city']} 天气预报:"]
        for cast in fc.get("casts", []):
            lines.append(
                f"  {cast['date']} | 白天: {cast['dayweather']} {cast['daytemp']}° | 夜间: {cast['nightweather']} {cast['nighttemp']}°"
            )
        return "\n".join(lines)

    async def poi_search(self, keywords: str, city: str = "") -> str:
        """POI 关键词搜索"""
        if not self.api_key:
            return "错误: AMAP_API_KEY 未配置"
        params: dict[str, Any] = {"key": self.api_key, "keywords": keywords, "offset": 5}
        if city:
            params["city"] = city
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{AMAP_BASE}/place/text", params=params)
            data = resp.json()
        pois = data.get("pois", [])
        if not pois:
            return f"未找到 '{keywords}' 相关地点"
        lines = []
        for i, p in enumerate(pois, 1):
            lines.append(f"{i}. {p['name']} | {p.get('address', '')} | ☎ {p.get('tel', 'N/A')}")
        return "\n".join(lines)

    async def route(self, origin: str, destination: str) -> str:
        """驾车路线规划 (origin/destination 为 "lng,lat" 格式)"""
        if not self.api_key:
            return "错误: AMAP_API_KEY 未配置"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{AMAP_BASE}/direction/driving", params={
                "key": self.api_key,
                "origin": origin,
                "destination": destination,
                "strategy": 0,
            })
            data = resp.json()
        paths = data.get("route", {}).get("paths", [])
        if not paths:
            return "未找到可用路线"
        p = paths[0]
        return f"🚗 驾车路线: {p.get('distance', '?')}m | 预计 {int(p.get('duration', 0)) // 60} 分钟 | 途经: {p.get('strategy', '')}"
