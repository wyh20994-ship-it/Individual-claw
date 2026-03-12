import { Request, Response } from "express";
import { ChannelMessage, WebhookHandler } from "./base";
import { sendToRunner } from "../rpc";
import { logger } from "../utils/logger";

/**
 * 飞书机器人 Webhook 处理
 * 文档: https://open.feishu.cn/document/
 */
export const feishuWebhookHandler: WebhookHandler = async (req: Request, res: Response) => {
  try {
    const body = req.body;

    // 飞书 URL 验证
    if (body.type === "url_verification") {
      res.json({ challenge: body.challenge });
      return;
    }

    const event = body.event;
    if (!event || !event.message) {
      res.json({ code: 0 });
      return;
    }

    // 仅处理文本消息
    const msgContent = JSON.parse(event.message.content || "{}");

    const message: ChannelMessage = {
      channel: "feishu",
      userId: event.sender?.sender_id?.open_id ?? "",
      userName: event.sender?.sender_id?.user_id,
      groupId: event.message.chat_id,
      content: msgContent.text ?? "",
      messageId: event.message.message_id ?? "",
      timestamp: Number(event.message.create_time) || Date.now(),
      raw: body,
    };

    logger.info(`[Feishu] Message from ${message.userId}: ${message.content}`);

    sendToRunner("agent.chat", {
      channel: message.channel,
      userId: message.userId,
      content: message.content,
      messageId: message.messageId,
      raw: message.raw,
    });

    res.json({ code: 0 });
  } catch (err) {
    logger.error("[Feishu] Webhook error", err);
    res.status(500).json({ code: -1 });
  }
};
