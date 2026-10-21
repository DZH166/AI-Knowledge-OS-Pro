# V5.11 Trusted Research Experience — implementation scope

Date: 2026-10-13 (Asia/Shanghai). Baseline: `ddb4f04291a221da60a74fa498a0cb81324fa64a`.

This is a bounded reliability and usability milestone, not a claim that real-model quality or production readiness has been established. Product/release version remains unchanged until release acceptance.

## Authorized public boundaries and acceptance

The user requested autonomous implementation following the reviewed priorities, with parallel windows and self-review. Verification uses existing public boundaries: `DeterministicClaimVerifier.verify`, public EvidenceAgent submission/inspection, RunController connection/observation, rendered upload/report interactions, and the owned-process browser runner. Do not add tests of private parsing details. Each behavioral fix starts with a reproducing failing test, then minimal implementation and regression review.

1. Evidence qualifiers: source statements with preceding load conditions, years, or plan headings cannot justify an unqualified numeric claim. Preserve necessary context, or conservatively reject rewriting and retain the original evidence. Existing valid literal/synonym/bounded-number behavior must remain correct. Verify through the public verifier and at least one complete Agent artifact flow. Do not claim general semantic proof or use live model calls.
2. Connection recovery: idle/connecting/disconnected/error must not masquerade as synchronized. Recover the same run from its last accepted event cursor, preserve deduplication/reset handling, provide explicit retry and last-sync information, and bound automatic retries. Unmount/disconnect must cancel retry timers and stale observers; terminal runs must not reconnect indefinitely. Never replay start/approval/cancel commands automatically.
3. Upload usability: keyboard-accessible file selection, functional drag/drop, real backend stage/status rather than percentage-based guesses, completed at 100%, and recoverable polling failure messages. File accept/validation and source readiness gates remain in place.
4. Readable artifacts: render Markdown headings/tables/lists/code safely using existing dependencies; no raw HTML execution or unsafe link protocols. Tables/code must remain usable at 390px width. Narrow-screen citations reveal their evidence immediately and support returning focus to the invoking citation; desktop references retain exact revision/chunk/hash/locator identity.
5. Owned runtime lifecycle: clean up children even when the parent exited first, without terminating unrelated processes. Windows ownership must be established before children can escape; Unix process groups must remain owned. Exercise failure/timeout/parent-first exits. Retained logs must live outside pytest's deletable basetemp, with sanitized console output and git-ignore protection.

## Ownership (shared worktree; no concurrent git operations)

- Agent 智能 window: claim verifier and dedicated backend claim/Agent regression tests only.
- 产品体验 window: DocumentUploader, ArtifactDetail, evidence detail presentation and dedicated UI/unit/browser tests; its own new stylesheet or EvidenceAgent stylesheet. Do not edit RunWorkspace or RunController.
- 集成总控 window: controlled browser runner, its owned process helper if needed, runtime tests, narrowly scoped log-path documentation/gitignore changes. No frontend or claim edits.
- Root: RunController/useEvidenceRun/RunWorkspace recovery, integration tests, stage documentation, global gates and Git delivery. Root coordinates any shared file ownership changes.

## Verification and exclusions

Run focused regressions per slice, then full backend tests using a new unique child `--basetemp` (never the shared `.pytest_tmp` root), frontend lint/typecheck/unit/build, compile/encoding/version checks, and controlled browser scenarios. Separate recorded/controlled browser evidence from unavailable real services. Preserve existing user changes, source data, migrations, and append-only learning/stage histories. No credentials, generated caches/logs/databases, or test artifacts committed.

Chinese retrieval improvements, per-source follow-up research, source-summary pagination, dependency locking, independent worker heartbeat, real provider configuration, and true answer-quality benchmarks are deferred to subsequent milestones. Do not silently expand this phase into architecture replacement or a new UI framework.
