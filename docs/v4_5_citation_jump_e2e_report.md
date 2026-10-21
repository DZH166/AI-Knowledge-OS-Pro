# V4.5 Citation Jump E2E Report

## Scope

V4.5 strengthens citation jump evidence from API contracts to real browser navigation.

## Covered Locators

- Document source locator through the document detail route.
- Image source locator through the media source route.
- Audio timestamp locator through `/media/sources/{id}?t=...&chunk=...`.
- Video timestamp locator through `/media/sources/{id}?t=...&chunk=...`.
- Code repository locator through `/code?file=...&line=...&line_end=...`.

## Browser Assertions

- Citation panel renders source links with stable test IDs.
- Chat can ask a seeded question and display a grounded answer with citations.
- Audio/video pages render the media player, transcript timeline and active transcript segment.
- Video page renders multiple keyframes and supports timestamp-focused navigation.
- Pages do not show `Failed to fetch`, raw API key variable names, tracebacks or fake OCR/transcript text.

## Verification Status

- API citation contract tests: passed through full pytest and `python scripts/check_all.py --observability`.
- Browser citation jump spec: passed through `python scripts/run_demo_e2e.py --strict`.
- `check_all --e2e`: passed and reran the browser citation spec successfully.

## Remaining Limits

Page-number and heading-level document anchors still depend on parser metadata quality. The V4.5 gate verifies route-level navigation and timestamp highlighting for seeded evidence.
