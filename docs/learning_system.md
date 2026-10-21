# Learning System

The learning system turns project versions into reviewable learning assets.

## Core Entities
- `LearningLog`: append-only version archive used by `docs/learning_log.md`.
- `VersionLearningPackage`: draft or confirmed learning package for a project version.
- `KnowledgePoint`: one concept with explanation, project usage, code locations, review advice and interview expression.
- `LearningCard`: front/back review card generated from a knowledge point.
- `QuizQuestion`: simple practice question.
- `LearningProgress`: timestamped mastery record.

## V4.0 Derived Roadmap And Relations

V4.0 adds a lightweight derived learning graph without introducing a new migration in this pass.

- `GET /api/learning/roadmap` returns a learning sequence from existing knowledge points, cards, quizzes, notes and packages.
- `GET /api/learning/knowledge-graph` returns derived `prerequisite`, `related`, `used_by_project` and `next_to_learn` relations.
- `/learning/roadmap` shows the next learning actions by mastery status.
- `/learning/knowledge-graph` shows relation evidence and reasons.

Current boundary:

- Relations are derived at request time from existing learning assets.
- This is not yet a persistent graph database.
- No fake LLM relationship generation is used.
- Future work can persist `KnowledgeRelation` records and add provider-backed roadmap generation when a real LLM is configured.

## V2 Flow
1. Generate a V2 learning package draft.
2. Review package contents in the Learning page.
3. Confirm the package.
4. Confirmation appends Markdown to `docs/learning_log.md`.
5. Confirmation appends a delivery entry to `docs/stage_delivery_log.md`.
6. Use cards, quizzes, notes and mastery status for later review.

The service never overwrites an existing learning log slug. Future versions should append new slug blocks.
