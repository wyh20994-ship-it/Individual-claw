import { Request, Response } from "express";
import axios from "axios";
import nacl from "tweetnacl";
import { ChannelMessage, WebhookHandler } from "./base";
import { dispatchChannelMessage } from "./commands";
import { logger } from "../utils/logger";

let qqAccessTokenCache: { token: string; expireAt: number } | null = null;

type QQRequest = Request & { rawBody?: string };

function seedFromSecret(botSecret: string): Uint8Array {
  let seed = botSecret;
  while (Buffer.byteLength(seed, "utf8") < 32) {
    seed += seed;
  }
  return new Uint8Array(Buffer.from(seed, "utf8").subarray(0, 32));
}

function verifyQQEd25519Signature(req: QQRequest, botSecret: string): boolean {
  if (!botSecret) return false;

  const signatureHex = req.header("X-Signature-Ed25519") || "";
  const timestamp = req.header("X-Signature-Timestamp") || "";
  const rawBody = req.rawBody;

  if (!signatureHex || !timestamp || typeof rawBody !== "string") {
    return false;
  }

  let signature: Buffer;
  try {
    signature = Buffer.from(signatureHex, "hex");
  } catch {
    return false;
  }

  if (signature.length !== 64 || (signature[63] & 224) !== 0) {
    return false;
  }

  const keyPair = nacl.sign.keyPair.fromSeed(seedFromSecret(botSecret));
  const message = Buffer.concat([Buffer.from(timestamp, "utf8"), Buffer.from(rawBody, "utf8")]);
  return nacl.sign.detached.verify(new Uint8Array(message), new Uint8Array(signature), keyPair.publicKey);
}

function signQQVerifyPayload(eventTs: string, plainToken: string, botSecret: string): string {
  const keyPair = nacl.sign.keyPair.fromSeed(seedFromSecret(botSecret));
  const payload = Buffer.from(`${eventTs}${plainToken}`, "utf8");
  const sig = nacl.sign.detached(new Uint8Array(payload), keyPair.secretKey);
  return Buffer.from(sig).toString("hex");
}

async function getQQAccessToken(appId: string, appSecret: string): Promise<string> {
  const now = Date.now();
  if (qqAccessTokenCache && qqAccessTokenCache.expireAt > now + 60_000) {
    return qqAccessTokenCache.token;
  }

  const resp = await axios.post(
    "https://bots.qq.com/app/getAppAccessToken",
    { appId, clientSecret: appSecret },
    { timeout: 10_000 },
  );

  const token = String(resp.data?.access_token ?? "");
  const expiresIn = Number(resp.data?.expires_in ?? 0);
  if (!token || !expiresIn) {
    throw new Error("QQ access token response invalid");
  }

  qqAccessTokenCache = {
    token,
    expireAt: now + expiresIn * 1000,
  };
  return token;
}

async function sendQQReply(opts: {
  appId: string;
  appSecret: string;
  groupOpenId?: string;
  userOpenId?: string;
  msgId: string;
  content: string;
}) {
  const { appId, appSecret, groupOpenId, userOpenId, msgId, content } = opts;
  const token = await getQQAccessToken(appId, appSecret);

  let url = "";
  if (groupOpenId) {
    url = `https://api.sgroup.qq.com/v2/groups/${groupOpenId}/messages`;
  } else if (userOpenId) {
    url = `https://api.sgroup.qq.com/v2/users/${userOpenId}/messages`;
  } else {
    throw new Error("QQ reply target not found (group_openid/user_openid)");
  }

  await axios.post(
    url,
    {
      content,
      msg_type: 0,
      msg_id: msgId,
    },
    {
      timeout: 10_000,
      headers: {
        Authorization: `QQBot ${token}`,
        "X-Union-Appid": appId,
      },
    },
  );
}

export const qqWebhookHandler: WebhookHandler = async (req: Request, res: Response) => {
  try {
    const qqReq = req as QQRequest;
    const appId = process.env.QQ_APP_ID || "";
    const appSecret = process.env.QQ_APP_SECRET || "";
    const qqToken = process.env.QQ_TOKEN || "";

    if (!appId || !appSecret) {
      logger.error("[QQ] Missing QQ_APP_ID or QQ_APP_SECRET");
      res.status(500).json({ code: -1, message: "QQ credentials not configured" });
      return;
    }

    const body = qqReq.body;

    if (body.op === 13) {
      if (qqToken && body.d?.token && body.d.token !== qqToken) {
        res.status(401).json({ code: -1, message: "invalid qq token" });
        return;
      }

      const plainToken = String(body.d?.plain_token ?? "");
      const eventTs = String(body.d?.event_ts ?? "");
      const signature = signQQVerifyPayload(eventTs, plainToken, appSecret);
      res.json({ plain_token: plainToken, signature });
      return;
    }

    if (!verifyQQEd25519Signature(qqReq, appSecret)) {
      logger.warn("[QQ] Invalid Ed25519 signature");
      res.status(401).json({ code: -1, message: "invalid signature" });
      return;
    }

    const message: ChannelMessage = {
      channel: "qq",
      userId: body.author?.id ?? body.author?.user_openid ?? "",
      userName: body.author?.username,
      groupId: body.group_openid,
      content: String(body.content ?? "").trim(),
      messageId: body.id ?? "",
      timestamp: Date.now(),
      raw: body,
    };

    logger.info(`[QQ] Message from ${message.userId}: ${message.content}`);

    const reply = await dispatchChannelMessage(message);
    await sendQQReply({
      appId,
      appSecret,
      groupOpenId: body.group_openid,
      userOpenId: body.author?.id ?? body.author?.user_openid,
      msgId: message.messageId,
      content: reply,
    });

    res.json({ code: 0 });
  } catch (err) {
    logger.error("[QQ] Webhook error", err);
    res.status(500).json({ code: -1 });
  }
};
