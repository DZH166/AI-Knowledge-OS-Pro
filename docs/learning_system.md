# Learning System

The learning system turns project versions into reviewable learning assets.

## Core Entities
- `LearningLog`: append-only version archive used by `docs/learning_log.md`.
- `VersionLearningPackage`: draft or confirmed learning package for a project version.
- `KnowledgePoint`: one concept with explanation, project usage, code locations, review advice and interview expression.
- `LearningCard`: front/back review card generated from a knowledge point.
- `QuizQuestion`: simple practice question.
- `LearningProgress`: timestamped mastery record.

## V2 Flow
1. Generate a V2 learning package draft.
2. Review package contents in the Learning page.
3. Confirm the package.
4. Confirmation appends Markdown to `docs/learning_log.md`.
5. Confirmation appends a delivery entry to `docs/stage_delivery_log.md`.
6. Use cards, quizzes, notes and mastery status for later review.

The service never overwrites an existing learning log slug. Future versions should append new slug blocks.
