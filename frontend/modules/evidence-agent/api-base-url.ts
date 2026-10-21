const LOCAL_API_BASE_URL = "http://localhost:8000";

export function resolveEvidenceApiBaseUrl(explicitBaseUrl: string | undefined, hasCustomFetch: boolean): string {
  const defaultBaseUrl = hasCustomFetch
    ? ""
    : process.env.NEXT_PUBLIC_API_BASE_URL || LOCAL_API_BASE_URL;
  return (explicitBaseUrl ?? defaultBaseUrl).replace(/\/$/, "");
}
