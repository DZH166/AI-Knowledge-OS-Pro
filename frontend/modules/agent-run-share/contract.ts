import { z } from "zod";


const Sha256Schema = z.string().regex(/^[a-fA-F0-9]{64}$/);

export const ShareLinkReceiptSchema = z.object({
  token: Sha256Schema,
  url_path: z.string().startsWith("/api/v1/agent-runs/shared/"),
  expires_at: z.iso.datetime()
}).strict();

export const RevokeShareReceiptSchema = z.object({
  success: z.literal(true),
  revoked: z.literal(true)
}).strict();

export type ShareLinkReceipt = z.infer<typeof ShareLinkReceiptSchema>;

