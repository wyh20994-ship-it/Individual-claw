import { Request, Response } from "express";
import { ChannelMessage, WebhookHandler } from "./base";
import { sendToRunner } from "../rpc";
import { logger } from "../utils/logger";

/**
 * 钉钉机器人 Webhook 处理
 * 文档: https://open.dingtalk.com/document/
 */
export const dingtalkWebhookHandler: WebhookHandler = async (req: Request, res: Response) => {
  try {
    const body = req.body;

    const message: ChannelMessage = {
      channel: "dingtalk",
      userId: body.senderStaffId ?? body.senderId ?? "",
      userName: body.senderNick,
      groupId: body.conversationId,
      content: body.text?.content?.trim() ?? "",
      messageId: body.msgId ?? "",
      timestamp: Number(body.createAt) || Date.now(),
      raw: body,
    };

    logger.info(`[DingTalk] Message from ${message.userId}: ${message.content}`);

    sendToRunner("agent.chat", {
      channel: message.channel,
      userId: message.userId,
      content: message.content,
      messageId: message.messageId,
      raw: message.raw,
    });

    res.json({ code: 0 });
  } catch (err) {
    logger.error("[DingTalk] Webhook error", err);
    res.status(500).json({ code: -1 });
  }
};
