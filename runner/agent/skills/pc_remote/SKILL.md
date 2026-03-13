---
name: pc_remote
version: "1.0.0"
description: PC 远程控制技能 — 支持锁屏、截图、进程管理、文件浏览
triggers:
  - /pc
  - 远程控制
  - 锁屏
  - 截图
  - 进程列表
---

# PC 远程控制

## 使用说明
当用户发送以下命令时触发本技能：

| 命令 | 功能 |
|------|------|
| `/pc lock` | 锁定当前电脑屏幕 |
| `/pc screenshot` | 截取当前屏幕截图并返回 |
| `/pc processes` | 列出当前运行的进程 (Top 20 by CPU) |
| `/pc files <path>` | 浏览指定路径的文件列表 |

## 执行逻辑

1. 解析用户命令，提取 `action` 和 `args`
2. 调用 `pc_remote` 服务对应方法
3. 返回执行结果（文本或图片 base64）

## 安全提醒
- 仅在受信任的局域网环境下启用
- `allowed_actions` 在 config.yaml 中配置白名单
- 文件浏览限制在指定根目录下
