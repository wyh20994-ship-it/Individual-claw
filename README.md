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

## Docker 部署

### 前提条件

- 已安装 [Docker](https://docs.docker.com/get-docker/) 和 Docker Compose

### 步骤

**1. 复制并配置环境变量**

```bash
cp .env.example .env
# 编辑 .env，填入至少一个 LLM 的 API Key（如 DEEPSEEK_API_KEY）
```

> Docker 环境下 `.env` 中的服务地址已预设为容器服务名，无需手动修改。

**2. 构建并启动所有服务**

```bash
docker compose up --build
```

启动顺序：`chromadb` → `runner` → `gateway`

**3. 后台运行**

```bash
docker compose up -d --build
```

### 服务端口

| 服务 | 地址 |
|------|------|
| Gateway HTTP | `http://localhost:3000` |
| Gateway WebSocket (RPC) | `ws://localhost:3001` |
| ChromaDB | `http://localhost:8000` |

### 常用命令

```bash
# 查看实时日志
docker compose logs -f

# 只查看某个服务的日志
docker compose logs -f runner

# 停止所有容器
docker compose down

# 停止并清除持久化数据（⚠️ 会删除记忆数据）
docker compose down -v

# 修改代码后只重建某个服务
docker compose up -d --build gateway
docker compose up -d --build runner
```

### 注意事项

- `runner/agent/skills` 已挂载为本地 volume，直接修改技能文件**无需重启容器**即可热重载。
- `./data` 目录挂载到容器，日志、对话记忆、沙箱文件均持久化在本地。
- 如需**本地非 Docker 方式运行**，将 `.env` 中的 `RUNNER_WS_URL` 改回 `ws://127.0.0.1:3001`，`CHROMA_HOST` 改回 `127.0.0.1`。

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
 