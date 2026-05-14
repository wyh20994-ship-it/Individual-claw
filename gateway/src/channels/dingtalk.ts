import { Request, Response } from "express";
import { ChannelMessage, WebhookHandler } from "./base";
import { dispatchChannelMessage } from "./commands";
import { logger } from "../utils/logger";

export const dingtalkWebhookHandler: WebhookHandler = async (req: Request, res: Response) => {
  try {
    const body = req.body;
    const message: ChannelMessage = {
      channel: "dingtalk",
      userId: body.senderStaffId ?? body.senderId ?? "",
      userName: body.senderNick,
      groupId: body.conversationId,
      content: String(body.text?.content ?? "").trim(),
      messageId: body.msgId ?? "",
      timestamp: Number(body.createAt) || Date.now(),
      raw: body,
    };

    logger.info(`[DingTalk] Message from ${message.userId}: ${message.content}`);

    const reply = await dispatchChannelMessage(message);
    res.json({ code: 0, reply });
  } catch (err) {
    logger.error("[DingTalk] Webhook error", err);
    res.status(500).json({ code: -1 });
  }
};
