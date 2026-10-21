# V4.8 Medium-Risk Interaction Cleanup Report

V4.7 reduced high-risk async button issues to zero. V4.8 re-ran the inventory after adding runtime timing and request-cache work.

## Current Scan

- Command: `python scripts/check_frontend_interactions.py`
- Total button interactions: 79.
- High duplicate-click risk: 0.
- Medium local-feedback risk: 24.
- Generated map: `docs/v4_8_button_latency_map.md`.

## Interpretation

The remaining medium-risk items are not unguarded API calls. They are local UI actions such as:

- AppShell menu open/collapse.
- Answer mode selection.
- Learning archive active item switching.
- Transcript seek and chunk selection.
- Copy-to-clipboard.
- Close drawer/modal/toast.
- Task row selection.

These actions should respond instantly rather than show network loading. For V4.8 they are retained with clear rationale instead of forcing inappropriate pending spinners.

## Cleanup Completed

- High-risk async-looking actions remain guarded by pending/disabled or explicit feedback.
- Runtime timing was added to the shared async button primitive.
- The V4.8 performance panel can show recent async action durations.
- Destructive flows continue to use confirmation dialogs instead of one-click destructive actions.
- The new V4.8 button latency map replaces the V4.7 map for current analysis.

## Retained Work

Medium-risk count did not materially decrease because the scan intentionally flags local feedback actions conservatively. The next real reduction should come from improving the scanner to recognize selected/copied/active UI states, not by hiding useful local controls behind artificial loading states.

## Verification

- `python scripts/check_frontend_interactions.py`: passed.
- `python scripts/check_interaction_feedback.py`: passed with `high_risk=0`.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_8.json`: passed.

