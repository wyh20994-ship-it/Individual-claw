import express, { Request, Response } from "express";
import { logger } from "./utils/logger";
import { qqWebhookHandler } from "./channels/qq";
import { feishuWebhookHandler } from "./channels/feishu";
import { dingtalkWebhookHandler } from "./channels/dingtalk";
import { authMiddleware } from "./middleware/auth";
import { rateLimitMiddleware } from "./middleware/rateLimit";

export async function startHttpServer(port: number, config: any): Promise<void> {
  const app = express();
  app.use(express.json());

  // --- 全局中间件 ---
  app.use(rateLimitMiddleware(config.gateway.middleware.rate_limit));
  app.use(authMiddleware(config.gateway.middleware.auth));

  // --- 健康检查 ---
  app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok", service: "hangclaw-gateway" });
  });

  // --- 渠道 Webhook 路由 ---
  if (config.gateway.channels.qq?.enabled) {
    app.post("/webhook/qq", qqWebhookHandler);
    logger.info("[Gateway] QQ channel enabled");
  }
  if (config.gateway.channels.feishu?.enabled) {
    app.post("/webhook/feishu", feishuWebhookHandler);
    logger.info("[Gateway] Feishu channel enabled");
  }
  if (config.gateway.channels.dingtalk?.enabled) {
    app.post("/webhook/dingtalk", dingtalkWebhookHandler);
    logger.info("[Gateway] DingTalk channel enabled");
  }

  return new Promise((resolve) => {
    app.listen(port, () => resolve());
  });
}
