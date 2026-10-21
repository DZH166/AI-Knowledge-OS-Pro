export type ApiRequestOptions = {
  timeoutMs?: number;
  ttlMs?: number;
  dedupeKey?: string;
  forceRefresh?: boolean;
  cachePrefix?: string;
};

export type RequestCacheMetric = {
  id: string;
  key: string;
  path: string;
  method: string;
  cache_status: "hit" | "miss" | "deduped" | "refresh" | "bypass" | "error";
  duration_ms: number;
  request_id: string | null;
  created_at: string;
};

export type RequestCacheSnapshot = {
  entries: number;
  in_flight: number;
  hits: number;
  misses: number;
  deduped: number;
  refreshes: number;
  bypassed: number;
  errors: number;
  recent: RequestCacheMetric[];
};

type CacheEntry<T> = {
  data: T;
  expiresAt: number;
  createdAt: number;
  requestId: string | null;
};

const responseCache = new Map<string, CacheEntry<unknown>>();
const inFlight = new Map<string, Promise<unknown>>();
const recentMetrics: RequestCacheMetric[] = [];
const counters = {
  hits: 0,
  misses: 0,
  deduped: 0,
  refreshes: 0,
  bypassed: 0,
  errors: 0
};

export function cacheKeyFor(method: string, path: string, options?: ApiRequestOptions) {
  return options?.dedupeKey || `${method.toUpperCase()} ${path}`;
}

export function readCachedResponse<T>(key: string): { data: T; requestId: string | null } | null {
  const entry = responseCache.get(key) as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    responseCache.delete(key);
    return null;
  }
  return { data: entry.data, requestId: entry.requestId };
}

export function writeCachedResponse<T>(key: string, data: T, ttlMs: number, requestId: string | null) {
  if (ttlMs <= 0) return;
  responseCache.set(key, { data, expiresAt: Date.now() + ttlMs, createdAt: Date.now(), requestId });
}

export function getInFlightRequest<T>(key: string): Promise<T> | null {
  return (inFlight.get(key) as Promise<T> | undefined) || null;
}

export function setInFlightRequest<T>(key: string, promise: Promise<T>) {
  inFlight.set(key, promise);
  promise.finally(() => {
    if (inFlight.get(key) === promise) inFlight.delete(key);
  });
}

export function clearCacheByPrefix(prefix = "") {
  for (const key of responseCache.keys()) {
    if (!prefix || key.includes(prefix)) responseCache.delete(key);
  }
}

export function clearAllRequestCache() {
  responseCache.clear();
}

export function recordRequestCacheMetric(metric: Omit<RequestCacheMetric, "id" | "created_at">) {
  if (metric.cache_status === "hit") counters.hits += 1;
  if (metric.cache_status === "miss") counters.misses += 1;
  if (metric.cache_status === "deduped") counters.deduped += 1;
  if (metric.cache_status === "refresh") counters.refreshes += 1;
  if (metric.cache_status === "bypass") counters.bypassed += 1;
  if (metric.cache_status === "error") counters.errors += 1;
  recentMetrics.unshift({
    ...metric,
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    created_at: new Date().toISOString()
  });
  recentMetrics.splice(50);
}

export function getRequestCacheSnapshot(): RequestCacheSnapshot {
  return {
    entries: responseCache.size,
    in_flight: inFlight.size,
    hits: counters.hits,
    misses: counters.misses,
    deduped: counters.deduped,
    refreshes: counters.refreshes,
    bypassed: counters.bypassed,
    errors: counters.errors,
    recent: [...recentMetrics]
  };
}
