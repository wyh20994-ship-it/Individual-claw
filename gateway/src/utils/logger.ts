import fs from "fs";
import path from "path";
import winston from "winston";

const logDir = path.resolve(process.env.LOG_DIR || path.join(process.cwd(), "..", "data", "logs"));
fs.mkdirSync(logDir, { recursive: true });

export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || "info",
  format: winston.format.combine(
    winston.format.timestamp({ format: "YYYY-MM-DD HH:mm:ss" }),
    winston.format.printf(({ timestamp, level, message }) => {
      return `${timestamp} [${level.toUpperCase()}] ${message}`;
    }),
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({
      filename: path.join(logDir, "gateway.log"),
      maxsize: 10_000_000,
      maxFiles: 5,
    }),
  ],
});
