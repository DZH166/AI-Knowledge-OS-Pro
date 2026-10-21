from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SNIPPETS = {
    "frontend/services/request-cache.ts": (
        "responseCache",
        "inFlight",
        "ttlMs",
        "forceRefresh",
        "cacheKeyFor",
        "readCachedResponse",
        "writeCachedResponse",
        "getInFlightRequest",
        "setInFlightRequest",
        "clearAllRequestCache",
        "recordRequestCacheMetric",
        "getRequestCacheSnapshot",
    ),
    "frontend/services/api.ts": (
        "REQUEST_TIMEOUT_MS",
        "x-request-id",
        "x-client-cache-status",
        "AbortError",
        "ttlMs: 10000",
        "ttlMs: 5000",
        "ttlMs: 30000",
        "forceRefresh",
        "clearAllRequestCache",
        "performance: (options?: ApiRequestOptions)",
        "performanceRecent: (options?: ApiRequestOptions)",
        "performanceSlow: (options?: ApiRequestOptions)",
        "performanceSummary: (options?: ApiRequestOptions)",
    ),
    "frontend/app/system/performance/page.tsx": (
        "getRequestCacheSnapshot",
        "performance-cache-panel",
        "performance-summary-panel",
        "performance-slow-panel",
        "performance-path-panel",
        "RecentActionsPanel",
    ),
    "frontend/types/api.ts": (
        "PerformanceRequestRecord",
        "PerformancePathStats",
        "PerformanceSummary",
        "PerformanceSnapshot",
    ),
}

GET_TTL_METHODS = (
    "dashboard",
    "systemStatus",
    "observability",
    "performance",
    "learningDashboard",
    "portfolioSummary",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def main() -> None:
    failures: list[str] = []
    for relative, snippets in REQUIRED_SNIPPETS.items():
        path = ROOT / relative
        if not path.exists():
            failures.append(f"missing required file: {relative}")
            continue
        text = read(relative)
        for snippet in snippets:
            if snippet not in text:
                failures.append(f"{relative} missing request-cache snippet: {snippet}")

    api_text = read("frontend/services/api.ts")
    for method in GET_TTL_METHODS:
        if f"{method}: (options?: ApiRequestOptions)" not in api_text:
            failures.append(f"api.{method} does not expose ApiRequestOptions for cache control")

    if "method === \"GET\"" not in api_text or "Boolean(options.ttlMs && options.ttlMs > 0)" not in api_text:
        failures.append("api request layer does not restrict cache/dedupe to GET requests with ttlMs")
    if "if (meta.method !== \"GET\")" not in api_text:
        failures.append("api request layer does not clear request cache after mutations")

    print("request_cache=checked")
    print(f"ttl_methods={len(GET_TTL_METHODS)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
