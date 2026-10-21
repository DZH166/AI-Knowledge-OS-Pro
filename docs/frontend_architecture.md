# Frontend Architecture

The frontend is a Next.js App Router application. It presents the knowledge OS as a product workspace rather than a landing page.

## Route Map

The current route scan reports 28 user-facing routes:

- Core workspace: `/`, `/dashboard`, `/knowledge`, `/upload`, `/documents`, `/documents/[id]`.
- AI assistant: `/chat`, `/chat/history`.
- Multimodal media: `/media`, `/media/sources/[id]`, `/errors`.
- Task and system operations: `/tasks`, `/system`, `/system/settings`, `/system/observability`.
- Learning system: `/learning`, `/learning/cards`, `/learning/knowledge-points`, `/learning/knowledge-points/[id]`, `/learning/knowledge-graph`, `/learning/notes`, `/learning/quizzes`, `/learning/roadmap`.
- Portfolio and interview: `/portfolio`, `/portfolio/resume`, `/portfolio/interview`, `/portfolio/project-review`.
- Code repository memory: `/code`.

## Shared Components

`frontend/components` currently contains 8 shared component files:

- `AppShell.tsx`: global navigation and layout shell.
- `ui.tsx`: shared feedback, loading, empty, status and page primitives.
- `CitationPanel.tsx`: citation display and media/document deep links.
- `KnowledgeChat.tsx`: chat session and grounded answer experience.
- `DocumentUploader.tsx`: document upload flow.
- `KnowledgeSpaceList.tsx`: knowledge space overview.
- `LearningLogPanel.tsx`: version learning panel.
- `AnswerModeSelector.tsx`: answer style control.

## API Client Boundary

`frontend/services/api.ts` is the single API client. Pages and components should call it instead of using ad hoc fetch wrappers. The file also owns date/size/duration/status formatting helpers used across UI surfaces.

## State And Feedback Boundary

The app currently uses local React state per page. Shared loading, error, empty and status UI should remain in `components/ui.tsx`. V4.1 removed all `react-hooks/exhaustive-deps` suppression comments by stabilizing page loaders with `useCallback`.

## Citation And Media Boundary

Document, image, audio and video citations must route through typed API payloads and shared URL helpers. Audio/video citations include timestamps; video pages seek the player and highlight matching transcript evidence.

## Current Frontend Debt

- Many pages are still large page-level components; future work can split repeated panels into `components/media`, `components/learning`, `components/portfolio` and `components/system`.
- There is no browser E2E suite yet; `scripts/check_frontend_smoke.py`, TypeScript and production build are the current quality gates.
