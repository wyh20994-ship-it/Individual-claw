import express, { Request, Response } from "express";
import { logger } from "./utils/logger";
import { qqWebhookHandler } from "./channels/qq";
import { feishuWebhookHandler } from "./channels/feishu";
import { dingtalkWebhookHandler } from "./channels/dingtalk";
import { authMiddleware } from "./middleware/auth";
import { rateLimitMiddleware } from "./middleware/rateLimit";
import { sendToRunnerAndWait } from "./rpc";

export async function startHttpServer(port: number, config: any): Promise<void> {
  const app = express();
  app.use(
    express.json({
      verify: (req: Request, _res: Response, buf: Buffer) => {
        (req as Request & { rawBody?: string }).rawBody = buf.toString("utf8");
      },
    }),
  );

  app.use(rateLimitMiddleware(config.gateway.middleware.rate_limit));
  app.use(authMiddleware(config.gateway.middleware.auth));

  app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok", service: "hangclaw-gateway" });
  });

  app.get("/admin/ping", async (_req: Request, res: Response) => {
    try {
      const result = await sendToRunnerAndWait("ping", {});
      res.json({ status: "ok", result });
    } catch (err) {
      logger.error("[Admin] ping failed", err);
      res.status(503).json({ status: "error", message: err instanceof Error ? err.message : "ping failed" });
    }
  });

  app.post("/admin/clear_memory", async (req: Request, res: Response) => {
    const userId = String(req.body?.userId ?? req.query?.userId ?? "").trim();
    if (!userId) {
      res.status(400).json({ status: "error", message: "userId is required" });
      return;
    }

    try {
      const result = await sendToRunnerAndWait("agent.clear_memory", { userId });
      res.json({ status: "ok", result });
    } catch (err) {
      logger.error("[Admin] clear_memory failed", err);
      res.status(503).json({ status: "error", message: err instanceof Error ? err.message : "clear_memory failed" });
    }
  });

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
