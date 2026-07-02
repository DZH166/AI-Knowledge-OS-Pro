# Version Learning Package

Version learning packages turn real project changes into study material. They are not generated from a fixed story template; the generator reads Git changes, route snapshots and optional verification reports.

## Current Workflow

1. Run `python scripts/generate_learning_package.py --version <VERSION>`.
2. Review the generated draft and confirm that every claim is backed by current code, docs or command output.
3. Keep historical package drafts under `docs/archive/<major-version>/` when they are no longer active release documents.
4. Append confirmed learning records to `docs/learning_log.md` and `docs/stage_delivery_log.md`.

## Historical V2.5 Draft

The preserved V2.5 draft now lives at:

- `docs/archive/v2/v2_5_learning_package_draft.json`

The append-only learning and stage delivery logs still preserve their original historical references.
