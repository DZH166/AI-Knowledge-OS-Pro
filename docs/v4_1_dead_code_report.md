# V4.1 Dead Code Report

This report is generated from a conservative static scan. It identifies review candidates, not automatic deletion instructions.

## Candidate Summary

- Suspected dead-code review candidates: `0`.
- Historical reports to preserve/archive instead of delete: `33`.
- Deprecated markers found in inventory recommendations/path scan: `0`.

## Review Candidates

No review candidates detected.

## Rules Used

- A-class deletion requires no static references, no tests, no docs dependency, no runtime entrypoint and not a historical archive.
- B-class migration applies to duplicated or scattered valuable logic.
- C-class deprecation applies when usage is uncertain or migration risk is high.
- D-class historical archives, including learning logs and version reports, must be preserved.
