# V5.1 Runtime and Strict E2E Acceptance Report

Date: 2026-08-26

Branch: `codex/v5.1-integration-control`

## Overall Status

**Passed（通过）.** The canonical runtime completed two consecutive Docker-backed runs with real
Redis/RQ and Qdrant infrastructure. Each run used isolated resources, executed the full 32-scenario
Playwright suite and cleaned only resources it owned.

## Runtime Contract

- Redis, Qdrant, SQLite, FastAPI, the named RQ worker and Next.js are started by one command.
- The caller does not need to provide `NEXT_PUBLIC_API_BASE_URL`; the orchestrator supplies one exact
  backend origin to both Next.js and Playwright.
- Every manifest declares `provider_mode=demo`; no model credential or real-provider result is implied.
- Frontend routes are prewarmed before four parallel browser workers start, removing development-build
  compilation noise without reducing product coverage.
- Failure and success paths use exact child PIDs, container names and run-scoped database paths for cleanup.
- Completion emits `runtime_manifest_final` with the same infrastructure identity plus a machine-readable
  `final_test_result.status` and `exit_code`.

## Consecutive Canonical Runs

Command, executed twice:

```powershell
python scripts/run_demo_e2e.py --strict
```

| Evidence | Run 1 | Run 2 |
|---|---|---|
| Token | `46296-bd464280` | `29968-5960400f` |
| Frontend/backend | `62078 / 62079` | `51015 / 51016` |
| Redis/Qdrant | `62080 / 62081` | `51017 / 51018` |
| Browser verdict | `32 passed (34.1s)` | `32 passed (33.0s)` |
| Live worker | passed | passed |
| Owned-resource cleanup | passed | passed |

The queue, Qdrant collection, worker and container identifiers were derived from each unique token,
so the two runs could not reuse one another's state.

## Defects Found and Closed

1. RQ rejected colon-delimited Agent job IDs. The dispatcher now emits hyphen-delimited, RQ-safe IDs.
2. The old Qdrant container was older than the Python client. The default image is now pinned to 1.18.0.
3. Parallel cold compilation caused false browser timeouts. The harness now prewarms 21 route groups,
   runs four parallel workers and derives assertion limits from the 60-second test budget.
4. A 24-repeat code-viewer stress regression passed after the harness fix.

## Supporting Gates

- Runtime/worker/outbox focused regression: `31 passed`.
- Frontend typecheck: passed.
- Static E2E contract: passed.
- Real worker logs showed outbox publish success and Agent jobs completing through retrieval and synthesis.
- Post-review strict rerun: token `45556-58d8dcf9`, `32 passed (35.9s)`, final manifest status `passed`.
- Forced failure with `--startup-timeout 0.001` stopped both owned containers, left no matching
  container and created no run database.

## Provider Boundary

This report validates orchestration, persistence, retrieval infrastructure and browser behavior in
deterministic demo mode. Real LLM, embedding and rerank configuration was intentionally not changed.
