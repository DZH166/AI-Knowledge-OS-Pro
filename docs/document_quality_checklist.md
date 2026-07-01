# Document Quality Checklist

Use this checklist before publishing a portfolio release.

## Accuracy

- Implemented features are separated from planned features.
- Provider-backed features mention required configuration.
- Demo mode is clearly labelled as synthetic.
- Limitations are stated plainly.

## Safety

- No `.env` content.
- No API keys.
- No private paths in screenshots when avoidable.
- No databases, uploads, logs or caches in release archives.

## Usability

- Quickstart works.
- Demo reset/check commands work.
- Screenshots match current UI.
- README links point to existing docs.

## Learning Archive

- `docs/learning_log.md` is append-only.
- `docs/stage_delivery_log.md` is append-only.
- Acceptance reports cite real verification commands.

## Release

- Backend compile passes.
- Pytest passes or limitations are documented.
- Frontend typecheck/build pass.
- Encoding, secret, repo clean and release checks pass.
