import dotenv from "dotenv";
dotenv.config({ path: "../.env" });

import { startHttpServer } from "./server";
import { startRpcServer } from "./rpc";
import { loadConfig } from "./utils/config";
import { logger } from "./utils/logger";

async function main() {
  const config = loadConfig();
  const port = Number(process.env.GATEWAY_PORT) || config.gateway.port;
  const wsPort = Number(process.env.GATEWAY_WS_PORT) || config.gateway.ws_port;

  // 启动 HTTP 服务（接收各渠道 Webhook）
  await startHttpServer(port, config);
  logger.info(`[Gateway] HTTP server listening on :${port}`);

  // 启动 WebSocket JSON-RPC 服务（与 Python Runner 通信）
  await startRpcServer(wsPort);
  logger.info(`[Gateway] WebSocket RPC server listening on :${wsPort}`);
}

main().catch((err) => {
  logger.error("Gateway failed to start", err);
  process.exit(1);
});
