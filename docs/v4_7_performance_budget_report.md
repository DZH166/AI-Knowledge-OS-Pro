# V4.7 Performance Budget Report

## Budgets

- Main AppShell navigation target budget: 18.
- Actual main navigation targets: 17.
- Required visual markers: Dashboard, project-structure page and AppShell brand.
- Forbidden main UI text: `raw JSON`, `Failed to fetch`, `debug payload`.

## Validation

```text
python scripts/check_ui_performance_budget.py
ui_performance_budget=checked
main_nav_targets=17
main_nav_budget=18
visual_pages=3
result=passed
```

## Boundary

This is a static UI budget. It prevents obvious product sprawl but does not replace Lighthouse, Web Vitals or browser trace profiling.
