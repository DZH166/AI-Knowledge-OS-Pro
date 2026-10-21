# V4.7 Cleanup Plan

## Completed In This Pass

- Reduced main navigation from 25 to 17 entries.
- Added UI performance and interaction feedback gates.
- Documented script and test sprawl without deleting active evidence tooling.
- Updated current version surfaces to V4.7.

## Deferred Cleanup

- Move low-frequency self-check helpers under `scripts/maintenance/` only after CI, docs and tests are updated in the same commit.
- Consider consolidating `check_*_report.py` validators behind a common report validation helper.
- Consider grouping V4.6 self-check tests by feature family.

## Deletion Rule

No script, test or report should be deleted unless a replacement command, CI reference and verification result are recorded.
