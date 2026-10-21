# V4.1 Dead Code Cleanup Plan

## Execution Order

1. Archive historical reports into `docs/archive/v3` and `docs/archive/v4` without deleting learning archives.
2. Remove or merge only low-risk assets with no references and no runtime entrypoint.
3. Defer service/provider/API-client candidates until route and test coverage prove they are unused.
4. After each cleanup batch, run the narrow relevant gate, then the full final gate.

## Candidate Actions

No cleanup candidates detected.

## Safety Invariants

- Do not delete `docs/learning_log.md` or `docs/stage_delivery_log.md`.
- Do not delete user databases, uploads, logs, caches, `.env`, `.next` or `node_modules`.
- Do not replace NOT_CONFIGURED provider refusals with fake OCR, fake transcription or fake answers.
- Keep database migrations and release safety scripts unless a stronger replacement exists.
