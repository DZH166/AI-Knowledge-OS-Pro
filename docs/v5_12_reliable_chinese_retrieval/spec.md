# V5.12 Reliable Chinese Retrieval — bounded implementation scope

Date: 2026-10-20 (Asia/Shanghai). Baseline: `a4dfc42f1d9b0e99ce01792177e78895f0b0dd1c`. Branch: `codex/v5.12-reliable-chinese-retrieval`.

The user authorized autonomous implementation in this order: repair the observed backend stream exception, then improve Chinese retrieval, with tests and independent reviews at each step. Push and merge main only after phase acceptance. Product/release version remains V5.8 / 5.8.0; this phase is not a real-model quality claim.

## Public boundaries and acceptance

Tests use the already established public seams: HTTP Agent detail/stream routes with a real SQL Agent and isolated SQLite, `EvidenceIndex.search` in active and pinned modes, and `HybridRetriever.search`. Boundary substitutes are permitted only for external vector/embedding/rerank services. Do not test private tokenization helpers or mock the project's own search implementation. The user's standing autonomous authorization applies to these routine test choices; no additional approval is required.

1. **Backend stream reliability first.** Reproduce the observed `response already started` failure through the public HTTP interface. A missing task must return the same structured 404 error as task detail, with request identity, before a successful event-stream response begins. Preserve valid event framing, durable cursor/resume/reset behavior and successful empty-stream behavior. Open-stream resource cleanup and cancellation must remain correct; never replace a failing request with fabricated task events, expose internal exception text, or return success for a request rejected before streaming starts. Review the fix before changing retrieval production code.

   This guarantee concerns a task already missing when the request is validated. External hard deletion after that check, database failure and errors after a stream is open can still interrupt the connection; an already started stream cannot be changed into a fresh JSON response. No pre-read should delay valid idle connections until a heartbeat arrives.
2. **Chinese lexical matching.** Natural Chinese questions without spaces, punctuation variants and mixed Chinese/English identifiers must retrieve relevant evidence when meaningful literal terms overlap. Use one shared, bounded text analysis/ranking implementation across SQL active/pinned evidence search and hybrid keyword candidates. Retain existing English/numeric retrieval behavior. State explicitly that lexical matching is not semantic understanding, synonym inference or universal Chinese word segmentation.
3. **Useful ranking.** Relevant specific evidence should rank above distractors that merely repeat generic query words. Incorporate term coverage, term discriminative value and bounded term-frequency/length effects as appropriate; keep hybrid fusion, optional reranker and final threshold contracts intact. No new vector database, model provider, schema migration or large framework replacement.
4. **Evidence isolation.** Preserve knowledge-space, explicit source and pinned revision restrictions; active search must exclude retired evidence. Pinned results retain immutable source/revision/index/chunk/hash/locator identity even after a newer active revision appears. No cross-scope text may influence returned evidence or ranking statistics.
5. **Measured retrieval-only acceptance.** Add a small, versioned, manually labeled Chinese query/corpus set, including paraphrased word order, punctuation, mixed-language terms and repeated-generic distractors. Run baseline and final public retrieval paths on the same fixtures; report actual top-1/top-5 hit rate and reciprocal rank with scope-isolation controls. Retain raw reports locally outside source archives. Do not call real models, invent accuracy gains or treat these synthetic retrieval fixtures as real-user or real-model quality validation.

## Ownership and sequencing

- Root owns production stream repair, integration, documentation, all Git operations and final acceptance.
- Stream regression agent owns only `backend/tests/test_v5_12_agent_stream.py`, adding one reproducing public test at a time.
- Chinese retrieval agent starts read-only baseline preparation. Production ownership will be assigned only after the backend repair is reviewed; no overlapping edits.
- Independent Standards and Spec reviewers are read-only and must not author the implementation they approve.

## Verification and boundaries

Use a new unique `.pytest_tmp/v512_<label>_<uuid>` child for every pytest invocation, never the shared basetemp root. Preserve old logs, user source data, the dirty old D-drive copy and append-only learning/stage histories. Verify focused regressions, complete backend suite, compile/static/version/encoding checks, unchanged frontend quality gates, controlled browser regressions and cloud service E2E with the deterministic demo provider. Finish with separate Standards/Spec reviews, safe source archive verification, remote branch identity checks and a fast-forward merge after CI acceptance. Credentials, data, caches, logs and archives remain uncommitted.

Model configuration, real-model answer quality, pagination, worker heartbeat and unrelated UI redesign are outside this phase. Existing dependency advisory boundaries remain separately reported.

## Acceptance-discovered corrections

Full acceptance must preserve the old 60-case Agent matrix, not only the new Chinese corpus. A new partial lexical match must not turn an otherwise weak vector-only candidate into false two-path support and exhaust unchanged no-progress safeguards; repair this at the lexical boundary, preserving fusion, budgets, model policy and both datasets.

The first controlled browser run also demonstrated existing first-load input corruption: a native text fill raced server-rendered defaults and client draft initialization, producing the user's goal followed by the default goal before reload. This observed data-loss risk is included as a bounded corrective fix, not a UI redesign: block draft-changing controls until initialization is complete, then keep all normal editing, storage-denial and pending-run recovery behavior. Reproduce through delayed JavaScript loading in a public browser test; do not add retries, sleeps or weaker assertions to hide it. This is the only additional frontend behavior in the phase.
