import { Request, Response } from "express";
import { ChannelMessage, WebhookHandler } from "./base";
import { dispatchChannelMessage } from "./commands";
import { logger } from "../utils/logger";

export const feishuWebhookHandler: WebhookHandler = async (req: Request, res: Response) => {
  try {
    const body = req.body;

    if (body.type === "url_verification") {
      res.json({ challenge: body.challenge });
      return;
    }

    const event = body.event;
    if (!event || !event.message) {
      res.json({ code: 0 });
      return;
    }

    const msgContent = JSON.parse(event.message.content || "{}");
    const message: ChannelMessage = {
      channel: "feishu",
      userId: event.sender?.sender_id?.open_id ?? "",
      userName: event.sender?.sender_id?.user_id,
      groupId: event.message.chat_id,
      content: String(msgContent.text ?? "").trim(),
      messageId: event.message.message_id ?? "",
      timestamp: Number(event.message.create_time) || Date.now(),
      raw: body,
    };

    logger.info(`[Feishu] Message from ${message.userId}: ${message.content}`);

    const reply = await dispatchChannelMessage(message);
    res.json({ code: 0, reply });
  } catch (err) {
    logger.error("[Feishu] Webhook error", err);
    res.status(500).json({ code: -1 });
  }
};
