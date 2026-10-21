# V4.2.1 Branch Governance

Generated at: 2026-07-04 Asia/Shanghai

## Current Branches

Local branches:

- `main` at `dbe20f2`
- `feature/v3.7-github-showcase-demo` at `58c56fa`
- `feature/v4.0-knowledge-portfolio-os` at local `18071b4`
- `feature/v4.1-codebase-cleanup-architecture-consolidation` at `3a43ab5`
- `feature/v4.2-full-regression-demo-release-readiness` at `6de400a`
- `feature/v4.2.1-mainline-sync-repo-governance` at `6de400a` before this documentation commit

Remote branches:

- `origin/main` at `dbe20f2`
- `origin/feature/v3.7-github-showcase-demo` at `58c56fa`
- `origin/feature/v4.0-knowledge-portfolio-os` at `829f69c`
- `origin/feature/v4.1-codebase-cleanup-architecture-consolidation` at `3a43ab5`
- `origin/feature/v4.2-full-regression-demo-release-readiness` at `6de400a`

## Merged into Main

Only `main` is merged into `main`. The feature branches are not merged into `main` because `main` remains at the V3.6-era commit `dbe20f2`.

## Keep

- Keep `feature/v4.2-full-regression-demo-release-readiness` until V4.2 is merged, tagged and released.
- Keep `feature/v4.2.1-mainline-sync-repo-governance` as the audit/governance record branch.
- Keep V4.1 and older feature branches until the V4.2 release is confirmed, because they provide historical context for the long-running project evolution.

## Can Be Considered for Later Cleanup

After V4.2 is merged into `main`, tagged as `v4.2.0`, and GitHub Release is created, older feature branches can be reviewed for archival. Do not delete remote branches automatically. Suggested later cleanup candidates:

- `feature/v3.7-github-showcase-demo`
- `feature/v4.0-knowledge-portfolio-os`
- `feature/v4.1-codebase-cleanup-architecture-consolidation`

## Do Not Delete Automatically

- Do not delete `feature/v4.2-full-regression-demo-release-readiness` before `main` is merged and tagged.
- Do not delete any remote branch without explicit user approval.
- Do not delete local branches that contain commits not present on their remote counterpart until they are audited. Notably, local `feature/v4.0-knowledge-portfolio-os` is ahead of `origin/feature/v4.0-knowledge-portfolio-os`.

## Naming Convention

Use:

- `feature/vX.Y-topic` for feature/release-readiness branches.
- `feature/vX.Y.Z-topic` for governance, patch and release-prep branches.
- `docs/vX_Y_topic.md` for versioned reports.
- Tags use lowercase semantic style: `vX.Y.Z`.

## Recommended Version Workflow

1. Create `feature/vX.Y-topic`.
2. Implement and validate locally.
3. Push branch.
4. Open PR to `main`.
5. Let CI pass.
6. Merge or squash via PR.
7. Pull updated `main`.
8. Create annotated tag.
9. Create GitHub Release.
10. Archive old branches only after release confirmation.

## Governance Decision

V4.2 should be merged to `main` through a PR. V4.3 should start from the newest V4.2 lineage after this governance checkpoint is committed, so the repository has a clean audit trail before new hardening work begins.
