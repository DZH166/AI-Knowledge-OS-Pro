# Commit Convention

Use clear, small commits that explain the project stage.

## Recommended Format

```text
type(scope): short summary
```

Examples:

```text
docs(v3.8): add quickstart and demo mode guides
feat(v3.9): add RAG evaluation script
test(v4.0): cover portfolio summary API
chore(release): prepare V4.0 release safety report
```

## Types

- `feat`: user-visible capability.
- `fix`: bug fix.
- `docs`: documentation.
- `test`: automated tests or verification fixtures.
- `chore`: build, CI, release, tooling.
- `refactor`: internal change without behavior change.

## Project Rules

- Do not commit `.env`, databases, uploads, logs, caches, `node_modules`, `.next` or release zips.
- Do not rewrite learning history.
- Do not claim provider-backed behavior unless the provider path is actually implemented.
- Prefer one stage-focused commit over a large mixed commit when possible.
