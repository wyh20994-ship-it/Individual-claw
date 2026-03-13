import { Request, Response } from "express";

/**
 * 渠道适配器基础接口
 * 所有渠道需将收到的消息统一转换为 ChannelMessage 格式
 */
export interface ChannelMessage {
  channel: "qq" | "feishu" | "dingtalk";
  userId: string;
  userName?: string;
  groupId?: string;
  content: string;
  messageId: string;
  timestamp: number;
  raw: unknown;             // 原始渠道数据，留作回复时使用
}

export type WebhookHandler = (req: Request, res: Response) => void | Promise<void>;
