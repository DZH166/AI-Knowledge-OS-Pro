# V5.7 Integration Workbench — Checklist

- [x] Missing/mismatched policy fingerprints cannot complete or qualify a Trial.
- [x] Expired Trial recovery requeues dead-lettered or published non-cancelled Outbox work atomically.
- [x] Candidate budget is cumulative; base/observed policies do not repeat; round request replay is durable.
- [x] Real evaluation latency and exact 60-case facts survive validation, storage and comparison.
- [x] Every specified Study event is reachable and cursor pagination cannot skip later timestamps.
- [x] Template request/response and comparison report match the strict V5.7 contract.
- [x] Run sharing uses a typed dedicated interface and identical sanitized trace projection.
- [x] Optimizer module interface is typed and cohesive; no route/recovery private-session access.
- [x] Optimizer catalog/detail user workflows have strict no-fallback frontend parsing.
- [x] Action availability comes from backend facts; no client-invented lifecycle rules.
- [x] Keyboard-only and 390px optimizer/share workflows are operable.
- [x] Backend/frontend/full migration/fixed evaluation/security/release gates pass.
- [x] Standards and Spec reviews have 0 remaining findings.
- [x] Strict E2E passes twice and exact owned resources are removed.
- [x] V5.7 archive and GitHub branch match final local source.
