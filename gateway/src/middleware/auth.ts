import { Request, Response, NextFunction } from "express";
import { logger } from "../utils/logger";

/**
 * 简易认证中间件
 * 生产环境应替换为签名验证（各渠道有不同的签名机制）
 */
export function authMiddleware(config: { enabled: boolean }) {
  return (req: Request, _res: Response, next: NextFunction) => {
    if (!config.enabled) return next();

    // Webhook 路由跳过内部 token 校验（由各渠道 handler 自行验签）
    if (req.path.startsWith("/webhook/")) return next();

    // 其它管理接口可检查 Bearer Token
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      logger.warn(`[Auth] Missing authorization header: ${req.method} ${req.path}`);
    }

    next();
  };
}
