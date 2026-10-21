# V4.2.1 Mainline Diff Report

Generated at: 2026-07-04 Asia/Shanghai

## Compared Refs

- Base: `main` at `dbe20f2`
- Head: `feature/v4.2-full-regression-demo-release-readiness` at `6de400a`
- Ahead/behind: `main...feature/v4.2-full-regression-demo-release-readiness` = `0 15`

## Overall Diff

The V4.2 branch contains 157 changed paths compared with `main`, with 18,742 insertions and 311 deletions. The changes cover README, CI, demo scripts, RAG evaluation, full regression gates, V4.1/V4.2 documentation, portfolio/code-repository features, frontend routes and backend tests.

## Requested Key File Review

| File | Status versus `main` | Notes |
| --- | --- | --- |
| `README.md` | Modified | V4.2 portfolio/demo/release content is present on the feature branch, not on `main`. |
| `docs/quickstart.md` | Added | New quickstart documentation exists on V4.2 branch. |
| `docs/demo_mode.md` | Added | Demo/real-mode boundary documentation exists on V4.2 branch. |
| `docs/v4_2_acceptance_report.md` | Added | V4.2 acceptance evidence exists. |
| `docs/v4_2_regression_report.md` | Missing | Requested name does not exist. The actual V4.2 regression report is `docs/v4_2_full_regression_report.md`. |
| `docs/v4_2_quality_gate_report.md` | Missing | Requested name does not exist. Current V4.2 quality evidence is split across acceptance, full regression, RAG quality and test reports. |
| `scripts/check_all.py` | Missing | Not present in V4.2. It is a V4.3 hardening requirement. |
| `scripts/check_full_regression.py` | Added | Full regression gate introduced in V4.2. |
| `scripts/check_demo_ready.py` | Added | Demo readiness gate introduced/strengthened on the feature branch. |
| `scripts/release.py` | Modified | Release packaging was strengthened for V4.2. |
| `.github/workflows/ci.yml` | Modified | CI runs backend compile/pytest/demo/RAG/full regression, frontend typecheck/build and release safety checks. |
| `docker-compose.yml` | Tracked, unchanged in key diff | Present in repository; no V4.2 delta in the requested comparison. |
| `frontend/package.json` | Modified | Version and script metadata updated. |
| `backend/requirements.txt` | Tracked, unchanged in key diff | Present in repository; no V4.2 delta in the requested comparison. |

## Key Diff Evidence

For the requested file set, `git diff --stat` reports:

```text
.github/workflows/ci.yml         |  22 ++-
README.md                        | 370 ++++++++++++++++++++++-----------------
docs/demo_mode.md                |  45 +++++
docs/quickstart.md               |  93 ++++++++++
docs/v4_2_acceptance_report.md   |  53 ++++++
frontend/package.json            |   2 +-
scripts/check_demo_ready.py      | 100 +++++++++++
scripts/check_full_regression.py | 284 ++++++++++++++++++++++++++++++
scripts/release.py               | 102 ++++++++++-
```

## Mainline Risk

`main` is not dangerous by itself, but it is stale. A visitor opening GitHub's default branch currently sees an older V3.6-era project state instead of V4.2. This creates a presentation and release-readiness risk: README, CI gates, scripts and V4.2 reports are not visible by default until the V4.2 PR merges.

## Required Remediation

1. Preserve the V4.2 feature branch as the release candidate.
2. Open a PR into `main`.
3. Let GitHub Actions run on the PR.
4. Merge into `main` after checks pass.
5. Tag `v4.2.0`.
6. Add V4.3 `scripts/check_all.py`, docs link checks and README asset checks on a new branch after V4.2.1 governance is committed.
