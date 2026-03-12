<<<<<<< HEAD
# HangClaw

> 基于 OpenClaw 架构的双引擎（Node.js Gateway + Python Runner）多渠道 AI Agent 基础设施。

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Multi-Channel Input                    │
│         QQ Bot  ·  Feishu  ·  DingTalk  ·  ...          │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP / WebHook
┌────────────────────────▼─────────────────────────────────┐
│              Node.js Gateway (gateway/)                   │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Channel │  │  Middleware   │  │  JSON-RPC Server │    │
│  │ Adapter │  │ (Auth/Rate)  │  │   (WebSocket)    │    │
│  └─────────┘  └──────────────┘  └────────┬─────────┘    │
└──────────────────────────────────────────┬───────────────┘
                         │ WebSocket + JSON-RPC
┌────────────────────────▼─────────────────────────────────┐
│              Python Runner (runner/)                      │
│  ┌──────┐  ┌─────────┐  ┌───────┐  ┌──────────────┐    │
│  │ LLM  │  │ Memory  │  │ Tools │  │    Skills     │    │
│  │Router │  │ 3-Layer │  │System │  │ (Hot-Reload) │    │
│  └──────┘  └─────────┘  └───────┘  └──────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## Features

- **多端接入**：QQ 、飞书、钉钉，企业微信
- **多 LLM 路由**：DeepSeek, OpenAI, Claude, Ollama
- **三层记忆**：对话记忆 (JSONL) · 语义记忆 (ChromaDB) · 工作记忆 (TTL Cache)
- **工具系统**：继承 `BaseTool`，支持文件、Bash、网络请求、搜索等
- **技能系统**：基于 `SKILL.md` 定义，支持热重载、命令/关键词触发
- **内置服务**：PC 远程控制(持续增加)

## Quick Start

```bash
# 1. 安装依赖
cd gateway && npm install
cd ../runner && pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Keys

# 3. 启动服务
# 终端 1: Node.js Gateway
cd gateway && npm run dev
# 终端 2: Python Runner
cd runner && python main.py
```

## Project Structure

```
HangClaw/
├── gateway/          # Node.js 网关层
├── runner/           # Python Agent 引擎
├── shared/           # 共享的 Schema 定义
├── data/             # 运行时数据（记忆/日志）
├── scripts/          # 启动与运维脚本
├── config.yaml       # 全局配置
└── .env.example      # 环境变量模板
```

## License
 