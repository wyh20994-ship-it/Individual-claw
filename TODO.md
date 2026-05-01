# Individual-claw TODO

## 阶段一：跑通代码 & 基础联调

- [ ] 安装依赖
  - [ ] `cd gateway && npm install`
  - [ ] `cd runner && pip install -r requirements.txt`
- [ ] 配置 `.env`（填入 DeepSeek API Key、ChromaDB 地址等）
- [ ] 启动 ChromaDB（`docker-compose up chromadb` 或本地运行）
- [ ] 启动 Python Runner（`python runner/main.py`）
- [ ] 启动 Node.js Gateway（`npm run dev`）
- [ ] 验证 Gateway ↔ Runner WebSocket 连接（`/admin/ping`）
- [ ] 打通第一个渠道（推荐先用飞书/钉钉，QQ 需要企业资质）
  - [ ] 配置 Webhook 回调地址（内网穿透工具：ngrok / frp）
  - [ ] 发一条消息验证 `agent.chat` 完整链路
- [ ] 验证三层记忆正常工作
  - [ ] `conv_memory`：多轮对话上下文连贯
  - [ ] `sem_memory`：ChromaDB 写入/检索正常
  - [ ] `work_memory`：工具调用后状态写入，下一轮 system prompt 中能看到

---

## 阶段二：功能完善

- [ ] 补全 `agent.clear_memory` 和 `ping` 的触发入口
  - [ ] `server.ts` 增加 `/admin/clear_memory` 路由
  - [ ] 渠道 handler 识别 `/清除记忆` 命令
- [ ] QQ 渠道 Webhook 验证签名（ed25519）
- [ ] Gateway `Dockerfile` + Runner `Dockerfile` 编写，完善 docker-compose 一键启动
- [ ] 错误重连：Runner 断线后自动重连 Gateway WebSocket
- [ ] 日志完善：区分 info/warn/error，接入日志轮转
- [ ] 上下文与记忆管理：用户偏好等自动更新到AGENT.md，历史记忆放置在./runner/agent/memory/conversation/,用户偏好自动更新到AGENT.md，大模型将历史记忆压缩存储为MEMORY.md
- [ ] 异步锁：一次性发送多条信息时逐条处理
- [ ] 记忆更新：自动更新MEMORY.md和AGENT.md
- [ ] sandbox配置：外接沙盒或者本地开辟沙盒路径
- [ ] 定时任务：sqlalchemy操控数据库存储定时任务，并写入磁盘
- [ ] 自我进化
---

## 阶段三：AI 最新消息推荐 & 内容推送

- [ ] **Tavily AI 资讯日报**（`tavily_daily` 技能）
  - [ ] 接通 `TavilyDailyService`，APScheduler 定时触发
  - [ ] 日报内容交给 LLM 生成中文摘要
  - [ ] 推送到指定渠道群组
- [ ] **自定义订阅**：用户可订阅感兴趣的话题关键词，每日推送专属摘要
- [ ] **热点榜单推送**：接入微博/知乎/GitHub trending 等数据源
- [ ] **主动推送能力**：Runner 主动向 Gateway 发消息（目前是被动响应），实现定时播报

---

## 阶段四：更多功能扩展

- [ ] 高德地图服务（`amap_life` 技能）接通
- [ ] PC 远程控制（`pc_remote` 技能）启用与测试
- [ ] 多模态支持：接收图片输入，调用视觉模型
- [ ] 插件市场：支持外部 SKILL.md + Python 文件热加载
- [ ] 管理后台 Web UI：查看对话记录、记忆内容、工具调用日志
