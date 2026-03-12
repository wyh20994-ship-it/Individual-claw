import { Request, Response, NextFunction } from "express";
import { logger } from "../utils/logger";

interface RateLimitConfig {
  window_ms: number;
  max_requests: number;
}

const counters = new Map<string, { count: number; resetAt: number }>();

/**
 * 基于内存的简易限流中间件
 */
export function rateLimitMiddleware(config: RateLimitConfig) {
  return (req: Request, res: Response, next: NextFunction) => {
    const key = req.ip ?? "unknown";
    const now = Date.now();
    let entry = counters.get(key);

    if (!entry || now > entry.resetAt) {
      entry = { count: 0, resetAt: now + config.window_ms };
      counters.set(key, entry);
    }

    entry.count++;

    if (entry.count > config.max_requests) {
      logger.warn(`[RateLimit] Too many requests from ${key}`);
      res.status(429).json({ error: "Too many requests" });
      return;
    }

    next();
  };
}
