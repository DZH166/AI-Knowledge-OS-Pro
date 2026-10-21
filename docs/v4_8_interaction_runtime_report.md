# V4.8 Interaction Runtime Report

V4.8 extends the V4.7 static interaction scan with runtime timing for shared async actions.

## Implemented

- `PendingButton` starts an interaction metric before running its async `onClick`.
- Completed and failed actions record `duration_ms`.
- Failed actions record a short error name/message without storing user input.
- Slow-action copy changes after 800 ms, 3 seconds and 10 seconds.
- `SlowActionNotice`, `InteractionTimeline` and `RecentActionsPanel` expose recent action state.
- `/system/performance` reads the recent-action snapshot and shows it beside backend request timing.

## Privacy Boundary

- Metrics store button/action labels and timing only.
- Full prompts, uploaded files, API keys and provider payloads are not recorded.
- The in-browser metric list is capped and session-local.

## Current Coverage

The shared `PendingButton` captures runtime timing wherever it wraps async work. V4.8 uses it for the performance refresh path and keeps V4.7 pending/disabled coverage for task retry/cancel, upload, chat, portfolio and provider-like actions.

## Verification

- `python scripts/check_interaction_feedback.py`: passed with `high_risk=0`.
- `python scripts/check_frontend_interactions.py`: passed with `buttons=79`, `high_risk=0`.
- `python scripts/check_ui_performance_budget.py`: passed with the performance panel snippets.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_8.json`: passed.

## Limitations

- Local buttons such as seek, copy, close, tab and menu actions are not forced through `PendingButton`; they rely on immediate selected/copied/active UI state instead.
- Metrics reset when the browser page reloads.

