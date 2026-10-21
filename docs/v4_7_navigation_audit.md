# V4.7 Navigation Audit

## Before

The AppShell exposed 25 main navigation targets. This made the sidebar behave like a site map and made it harder for a beginner to choose the next action.

## After

The AppShell now exposes 17 core targets:

- Start: Dashboard.
- Knowledge management: Knowledge base, upload center, media library, task center.
- AI assistant: Knowledge chat, conversation history.
- Learning growth: Learning roadmap, project structure, learning assets, version archive.
- Portfolio: Project review, resume expression, mock interview.
- System: Models and services, observability, settings.

## Preserved Routes

The following routes remain implemented and smoke-checked, but are no longer all first-level nav entries: documents, code repositories, error archive, knowledge graph, knowledge points, quizzes, notes and portfolio project-review.

## Verification

- `python scripts/check_frontend_smoke.py`: passed with `required_routes=28` and `nav_targets=17`.
- `python scripts/check_ui_performance_budget.py`: passed with nav budget 18.
