---
name: tavily_daily
version: "1.0.0"
description: Tavily AI 资讯日报自动推送 — 每日定时搜索热点并推送摘要
triggers:
  - /daily
  - /news
  - 今日资讯
  - AI日报
---

# Tavily AI 资讯日报

## 使用说明

| 命令 | 功能 |
|------|------|
| `/daily` | 立即生成并推送今日 AI/Tech 资讯摘要 |
| `/news <关键词>` | 按关键词搜索最新资讯 |

## 自动推送
- 配置 `TAVILY_PUSH_CRON` 环境变量（默认 `0 8 * * *`，每天 08:00）
- 自动搜索 AI / 科技热点，生成摘要后推送到所有已启用的渠道

## 执行逻辑

1. 调用 Tavily Search API 搜索最新资讯
2. 将搜索结果交给 LLM 生成中文摘要
3. 格式化为日报推送

## 依赖
- `TAVILY_API_KEY` 环境变量
- APScheduler（定时推送）
