# V4.7 Learning Package Draft

This draft is for learning how the V4.7 optimization layer was built on top of the existing multimodal RAG product. It focuses on product experience, frontend feedback, quality gates and cleanup governance.

## 1. Interaction Feedback

- Beginner explanation: A slow button feels broken if it gives no visible response.
- Project usage: V4.7 adds pending and disabled states to task, learning, system and chat actions.
- Related files: `frontend/components/ui.tsx`, `frontend/app/tasks/page.tsx`, `frontend/components/KnowledgeChat.tsx`.
- Common mistake: Only optimizing backend speed while the UI still looks frozen.
- Debug method: Click each async action and confirm the button changes state before the request finishes.
- Interview expression: I improved perceived performance by making async actions visible and idempotent.

## 2. Duplicate-Click Protection

- Beginner explanation: A user may click twice when nothing appears to happen.
- Project usage: Pending state now blocks retry, cancel, quiz, review and favorite actions from firing duplicate requests.
- Related files: `frontend/app/tasks/page.tsx`, `frontend/app/learning/cards/page.tsx`, `frontend/app/learning/quizzes/page.tsx`.
- Common mistake: Showing loading text but leaving the button clickable.
- Debug method: Rapid-click an action and inspect whether only one API request is made.
- Interview expression: I protected state-changing operations from accidental duplicate execution.

## 3. API Timeout Boundary

- Beginner explanation: Long network waits need a clear ending instead of an infinite spinner.
- Project usage: The frontend API client aborts long requests and shows a Chinese user-facing timeout message.
- Related files: `frontend/services/api.ts`.
- Common mistake: Letting fetch calls wait forever.
- Debug method: Point the API URL to a slow endpoint and confirm timeout feedback appears.
- Interview expression: I treated latency as part of the product contract, not only an infrastructure problem.

## 4. Skeleton And Loading States

- Beginner explanation: Skeletons tell the user what kind of content is coming.
- Project usage: Reusable skeleton, overlay and async-boundary primitives are available for data-heavy screens.
- Related files: `frontend/components/ui.tsx`, `frontend/app/dashboard/page.tsx`.
- Common mistake: Replacing every load with a generic spinner.
- Debug method: Open a page with the API stopped and check empty, loading and error states separately.
- Interview expression: I improved perceived speed by making page state explicit.

## 5. Dashboard Command Center

- Beginner explanation: A dashboard should answer "what is happening and what should I do next?"
- Project usage: The Dashboard now shows mode, capability bars, next actions and task distribution instead of plain status blocks.
- Related files: `frontend/app/dashboard/page.tsx`, `frontend/app/globals.css`.
- Common mistake: Turning the dashboard into a long index of every feature.
- Debug method: Check that the first screen explains status and next action without scrolling through raw data.
- Interview expression: I redesigned the dashboard around decision-making rather than feature listing.

## 6. Visual Information Architecture

- Beginner explanation: Complex systems are easier to learn as relationships and flows.
- Project usage: `/learning/project-structure` now contains loops, module maps, evidence chains and learning steps.
- Related files: `frontend/app/learning/project-structure/page.tsx`, `frontend/app/globals.css`.
- Common mistake: Describing architecture only with paragraphs.
- Debug method: Confirm the page contains `structure-map`, `flow-diagram`, `evidence-chain` and `learning-stepper` sections.
- Interview expression: I turned architecture learning into an in-product visual guide for beginners and reviewers.

## 7. RAG Evidence Flow

- Beginner explanation: RAG is not just asking an LLM; it is upload, parse, chunk, embed, retrieve, cite and answer.
- Project usage: The project-structure page explains this chain without making provider calls.
- Related files: `backend/app/services/rag_service.py`, `frontend/app/learning/project-structure/page.tsx`.
- Common mistake: Claiming an answer is grounded without showing citations.
- Debug method: Use chat history and citation locators to trace the answer back to a source.
- Interview expression: I model RAG as an evidence pipeline with refusal boundaries.

## 8. Multimodal Processing Flow

- Beginner explanation: Image, audio and video sources need different extraction paths before they become searchable evidence.
- Project usage: V4.7 keeps the visual explanation aligned with existing OCR, transcription, keyframe and citation concepts.
- Related files: `backend/app/services/media_service.py`, `backend/app/services/video_service.py`, `frontend/app/media/sources/[id]/page.tsx`.
- Common mistake: Presenting missing OCR or transcription as if it were real content.
- Debug method: Disable providers and confirm NOT_CONFIGURED-style boundaries remain explicit.
- Interview expression: I preserved real provider boundaries while making the multimodal pipeline easier to understand.

## 9. Navigation Governance

- Beginner explanation: Too many menu entries slow the user before they even start.
- Project usage: The AppShell main navigation was reduced from 25 to 17 targets while preserving routes.
- Related files: `frontend/components/AppShell.tsx`, `scripts/check_frontend_smoke.py`.
- Common mistake: Putting every route into the sidebar.
- Debug method: Run frontend smoke and confirm required routes still exist while nav count stays within budget.
- Interview expression: I kept functionality but reduced cognitive load by separating primary workflow from deep links.

## 10. UI Performance Budget

- Beginner explanation: A budget is a guardrail that stops pages and navigation from growing forever.
- Project usage: `scripts/check_ui_performance_budget.py` checks route existence, nav count and visual-page markers.
- Related files: `scripts/check_ui_performance_budget.py`, `backend/tests/test_v4_7_ui_quality_gates.py`.
- Common mistake: Letting quality rules exist only as advice in documentation.
- Debug method: Run the script before and after changing navigation or visual pages.
- Interview expression: I added executable UI governance so product complexity does not silently return.

## 11. Interaction Feedback Gate

- Beginner explanation: A gate turns "buttons should feel fast" into a repeatable check.
- Project usage: `scripts/check_interaction_feedback.py` scans for high-risk async buttons without pending feedback.
- Related files: `scripts/check_interaction_feedback.py`, `scripts/check_frontend_interactions.py`.
- Common mistake: Counting buttons but not prioritizing API-like actions.
- Debug method: Review `docs/v4_7_button_latency_map.md` after changing important pages.
- Interview expression: I made frontend interaction quality measurable.

## 12. Button Latency Map

- Beginner explanation: A latency map lists where users may feel waiting or uncertainty.
- Project usage: `scripts/check_frontend_interactions.py` generates the V4.7 button inventory and high-risk count.
- Related files: `docs/v4_7_button_latency_map.md`.
- Common mistake: Auditing only the page you just edited.
- Debug method: Re-run the script and compare the button count and high-risk count.
- Interview expression: I used static analysis to guide targeted UX fixes.

## 13. Script Sprawl Governance

- Beginner explanation: Too many scripts can become their own maintenance problem.
- Project usage: V4.7 documents which scripts stay in the main flow and which should move to maintenance later.
- Related files: `docs/v4_7_script_sprawl_audit.md`, `docs/v4_7_cleanup_plan.md`, `docs/scripts_reference.md`.
- Common mistake: Deleting scripts before checking CI and documentation references.
- Debug method: Use `rg` to find references before moving or deleting any script.
- Interview expression: I balanced quality automation with maintainable tooling.

## 14. Test Sprawl Governance

- Beginner explanation: More tests are not automatically better if they duplicate weak checks.
- Project usage: V4.7 keeps meaningful regression coverage and documents consolidation candidates.
- Related files: `docs/v4_7_test_sprawl_audit.md`, `backend/tests/test_v4_7_ui_quality_gates.py`.
- Common mistake: Testing only that a report file exists.
- Debug method: Prefer tests that execute the behavior or gate being claimed.
- Interview expression: I reviewed test value, overlap and release relevance instead of blindly adding more tests.

## 15. Version Consistency

- Beginner explanation: A portfolio project looks unreliable when README, app chrome and release scripts show different versions.
- Project usage: V4.7 unifies backend settings, frontend package metadata, AppShell, scripts and documentation.
- Related files: `backend/app/core/config.py`, `frontend/package.json`, `frontend/components/AppShell.tsx`, `scripts/check_version.py`.
- Common mistake: Updating README but forgetting package metadata or system status.
- Debug method: Run `python scripts/check_version.py`.
- Interview expression: I made release identity executable and consistent across backend, frontend and docs.

## 16. Release Safety

- Beginner explanation: A release zip must not contain secrets, databases, uploads, logs or caches.
- Project usage: `scripts/release.py` builds from Git-tracked files and `scripts/check_release.py` verifies required entries and forbidden paths.
- Related files: `scripts/release.py`, `scripts/check_release.py`, `docs/release_checklist.md`.
- Common mistake: Zipping the whole folder manually.
- Debug method: Run release dry-run first, then inspect the generated `.sha256` after the final zip.
- Interview expression: I treated packaging safety as part of the application boundary.

## 17. Real-Mode Boundary

- Beginner explanation: A missing provider key must produce a clear refusal, not fake AI output.
- Project usage: V4.7 preserves existing NOT_CONFIGURED-style behavior while improving the UI around it.
- Related files: `backend/tests/test_provider_boundaries.py`, `backend/tests/test_v3_5_video_transcription.py`, `frontend/app/system/page.tsx`.
- Common mistake: Filling demos with fake OCR, fake transcripts or fake citations.
- Debug method: Run provider dry-run and missing-provider tests.
- Interview expression: I kept demo usability separate from real provider truth.

## 18. Interview Story

- Beginner explanation: A project release should be explainable as a product and engineering decision.
- Project usage: V4.7 can be described as "performance perception, visual learning and quality governance cleanup."
- Related files: `README.md`, `docs/v4_7_release_notes.md`, `docs/v4_7_acceptance_report.md`.
- Common mistake: Listing features without explaining the engineering tradeoff.
- Debug method: Practice a 60-second summary using Dashboard, project-structure page and quality gates as evidence.
- Interview expression: I improved a feature-rich AI application by reducing friction, making flows visible and adding executable quality budgets.
