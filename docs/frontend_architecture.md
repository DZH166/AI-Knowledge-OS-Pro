# Frontend Architecture

The frontend is a Next.js App Router application. It presents the knowledge OS as a product workspace rather than a landing page.

## Route Map

The current route scan reports 43 user-facing routes:

- Core workspace: `/`, `/workbench`, `/dashboard`, `/knowledge`, `/library`, `/upload`, `/documents`, `/documents/[id]`.
- AI assistant and Agent execution: `/chat`, `/chat/history`, `/runs`, `/runs/[runId]`, `/runs/[runId]/trace`.
- Multimodal media: `/media`, `/media/sources/[id]`, `/errors`.
- Evidence products: `/artifacts`, `/artifacts/[artifactId]`.
- Evaluation and retrieval policy: `/evaluations`, `/evaluations/[evaluationId]`, `/policies`, `/policies/[policyId]`, `/policies/optimizer`, `/policies/optimizer/[studyId]`.
- Task and system operations: `/tasks`, `/system`, `/system/settings`, `/system/observability`, `/system/performance`.
- Learning system: `/learning`, `/learning/cards`, `/learning/knowledge-points`, `/learning/knowledge-points/[id]`, `/learning/knowledge-graph`, `/learning/notes`, `/learning/quizzes`, `/learning/roadmap`, `/learning/project-structure`.
- Portfolio and interview: `/portfolio`, `/portfolio/resume`, `/portfolio/interview`, `/portfolio/project-review`.
- Code repository memory: `/code`.

## Shared Components

The shared layer is split by product responsibility:

- `AppShell.tsx`: global navigation and layout shell.
- `ui.tsx`: shared feedback, loading, empty, status and page primitives.
- `CitationPanel.tsx`: citation display and media/document deep links.
- `KnowledgeChat.tsx`: chat session and grounded answer experience.
- `DocumentUploader.tsx`: document upload flow.
- `KnowledgeSpaceList.tsx`: knowledge space overview.
- `LearningLogPanel.tsx`: version learning panel.
- `AnswerModeSelector.tsx`: answer style control.
- `components/agent-policy/*`: policy catalog, immutable detail, comparison, simulation, evaluation, activation and rollback UI.
- `components/optimizer/*`: offline Study creation, Trial metrics, Pareto/observation-guided rounds, recommendation and report UI.
- `components/agent-runs/*`: Run list/detail and evidence-aware trace UI.
- `components/evaluations/*`: fixed evaluation control and report inspection UI.
- `components/artifacts/*`: Artifact → Claim → Evidence navigation.

## API Client Boundary

`frontend/services/api.ts` remains the legacy product API boundary. V5 feature modules own narrow typed clients under
`frontend/modules/*/client.ts`; pages and components use these clients instead of ad hoc fetch wrappers. Strict
runtime payloads are parsed before presentation so malformed server responses fail visibly rather than falling back
to demo data.

Feature ownership remains narrow: `modules/optimizer/*` owns only optimizer contracts and requests, while
`modules/agent-run-share/*` owns expiring Run Trace share creation and revocation. Agent Control UI may compose both
features, but neither client reaches across the other's API boundary.

V5.8 `modules/feedback/*` owns source-pinned feedback, terminal human review and reviewed-sample export.
The Artifact page composes a feedback form; `/evaluations/feedback` presents persisted snapshots and review state.
Mutation busy state must not trigger detail reload or discard unsaved inputs. Review failures preserve the intent
identifier; exports verify selected IDs, mode, split and content digest before a local download. These samples
are not automatically verified truth and do not activate policies or enter the knowledge index.

## State And Feedback Boundary

The app currently uses local React state per page. Shared loading, error, empty and status UI should remain in `components/ui.tsx`. V4.1 removed all `react-hooks/exhaustive-deps` suppression comments by stabilizing page loaders with `useCallback`.

## Citation And Media Boundary

Document, image, audio and video citations must route through typed API payloads and shared URL helpers. Audio/video citations include timestamps; video pages seek the player and highlight matching transcript evidence.

## Quality Boundary

- Vitest protects typed clients, presenters and UI state transitions.
- Playwright drives the Next.js development server against real FastAPI, Redis/RQ and Qdrant services.
- The production bundle is checked separately by Next.js build; development-server E2E does not claim production-runtime validation.
- The canonical strict runner owns isolated ports, processes, containers and databases, then proves exact cleanup.
- Lint, TypeScript, production build, dependency audit and static smoke checks remain required gates.
