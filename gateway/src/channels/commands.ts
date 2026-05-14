import { ChannelMessage } from "./base";
import { sendToRunnerAndWait } from "../rpc";

export type ChannelCommandResult = {
  handled: boolean;
  reply?: string;
};

const userQueues = new Map<string, Promise<string>>();

function normalizeCommand(content: string): string {
  return content.trim().replace(/\s+/g, " ").toLowerCase();
}

export async function handleChannelCommand(message: ChannelMessage): Promise<ChannelCommandResult> {
  const command = normalizeCommand(message.content);

  if (command === "/ping") {
    const result = await sendToRunnerAndWait("ping", {
      channel: message.channel,
      userId: message.userId,
      messageId: message.messageId,
      raw: message.raw,
    });
    return { handled: true, reply: String(result) };
  }

  if (command === "/清除记忆" || command === "/clear_memory" || command === "/clear memory") {
    await sendToRunnerAndWait("agent.clear_memory", {
      channel: message.channel,
      userId: message.userId,
      messageId: message.messageId,
      raw: message.raw,
    });
    return { handled: true, reply: "记忆已清除。" };
  }

  return { handled: false };
}

export async function dispatchChannelMessage(message: ChannelMessage): Promise<string> {
  const queueKey = `${message.channel}:${message.userId || "unknown"}`;
  const previous = userQueues.get(queueKey) || Promise.resolve("");
  const current = previous
    .catch(() => "")
    .then(() => dispatchChannelMessageNow(message))
    .finally(() => {
      if (userQueues.get(queueKey) === current) {
        userQueues.delete(queueKey);
      }
    });

  userQueues.set(queueKey, current);
  return current;
}

async function dispatchChannelMessageNow(message: ChannelMessage): Promise<string> {
  const commandResult = await handleChannelCommand(message);
  if (commandResult.handled) {
    return commandResult.reply || "OK";
  }

  const rpcResult = await sendToRunnerAndWait("agent.chat", {
    channel: message.channel,
    userId: message.userId,
    content: message.content,
    messageId: message.messageId,
    raw: message.raw,
  });

  if (rpcResult && typeof rpcResult === "object") {
    const result = rpcResult as { reply?: unknown };
    if (typeof result.reply === "string" && result.reply.trim()) {
      return result.reply;
    }
  }

  return "已收到消息，但暂时没有生成回复。";
}
