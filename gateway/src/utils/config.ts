import fs from "fs";
import path from "path";
import YAML from "yaml";

/**
 * 加载 config.yaml 全局配置
 */
export function loadConfig(): any {
  const configPath = path.resolve(__dirname, "../../../config.yaml");
  if (!fs.existsSync(configPath)) {
    throw new Error(`Config file not found: ${configPath}`);
  }
  const raw = fs.readFileSync(configPath, "utf-8");
  return YAML.parse(raw);
}
