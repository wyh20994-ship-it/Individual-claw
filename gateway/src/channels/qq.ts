import { Request, Response } from "express";
import { ChannelMessage, WebhookHandler } from "./base";
import { sendToRunner } from "../rpc";
import { logger } from "../utils/logger";

/**
 * QQ 官方机器人 Webhook 处理
 * 文档: https://bot.q.qq.com/wiki/develop/api/
 */
export const qqWebhookHandler: WebhookHandler = async (req: Request, res: Response) => {
  try {
    const body = req.body;

    // QQ 平台验证回调（首次注册 Webhook 时）
    if (body.op === 13) {
      const plain = body.d?.event_ts + body.d?.plain_token;
      // 实际生产中需用 ed25519 签名，此处仅为框架示意
      res.json({ plain_token: body.d?.plain_token, signature: "" });
      return;
    }

    const message: ChannelMessage = {
      channel: "qq",
      userId: body.author?.id ?? "",
      userName: body.author?.username,
      groupId: body.group_openid,
      content: body.content ?? "",
      messageId: body.id ?? "",
      timestamp: Date.now(),
      raw: body,
    };

    logger.info(`[QQ] Message from ${message.userId}: ${message.content}`);

    // 转发给 Python Runner
    sendToRunner("agent.chat", {
      channel: message.channel,
      userId: message.userId,
      content: message.content,
      messageId: message.messageId,
      raw: message.raw,
    });

    res.json({ code: 0 });
  } catch (err) {
    logger.error("[QQ] Webhook error", err);
    res.status(500).json({ code: -1 });
  }
};
