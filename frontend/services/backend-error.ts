import { z } from "zod";

const BackendErrorSchema = z.object({
  error: z.object({
    code: z.string().min(1).optional(),
    user_message: z.string().trim().min(1).optional(),
    retryable: z.boolean().optional()
  }).passthrough()
}).passthrough();

export function backendErrorDetails(payload: unknown): {
  code: string | null;
  userMessage: string | null;
  retryable: boolean;
} {
  const parsed = BackendErrorSchema.safeParse(payload);
  if (!parsed.success) return { code: null, userMessage: null, retryable: false };
  return {
    code: parsed.data.error.code ?? null,
    userMessage: parsed.data.error.user_message ?? null,
    retryable: parsed.data.error.retryable ?? false
  };
}

export function backendErrorMessage(payload: unknown, fallback: string): string {
  const { code, userMessage, retryable } = backendErrorDetails(payload);
  if (!userMessage) return fallback;
  if (!code) return userMessage;
  return `${userMessage}（代码：${code}；${retryable ? "可重试" : "不可重试"}）`;
}
