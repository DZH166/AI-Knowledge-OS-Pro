from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
APP_DIR = FRONTEND / "app"
APP_SHELL = FRONTEND / "components" / "AppShell.tsx"

MAX_MAIN_NAV_TARGETS = 18
MAX_PAGE_PANELS = {
    "frontend/app/dashboard/page.tsx": 9,
    "frontend/app/tasks/page.tsx": 8,
    "frontend/app/learning/project-structure/page.tsx": 10,
    "frontend/app/portfolio/page.tsx": 8,
}

REQUIRED_VISUAL_SNIPPETS = {
    "frontend/app/dashboard/page.tsx": (
        "dashboard-hero",
        "capability-bars",
        "next-action-grid",
        "task-distribution",
    ),
    "frontend/app/learning/project-structure/page.tsx": (
        "structure-map",
        "flow-diagram",
        "evidence-chain",
        "learning-stepper",
        "interview-mode",
    ),
    "frontend/components/AppShell.tsx": (
        "V4.8 运行性能与 release 体验",
        "学习资产",
        "性能与体验",
    ),
    "frontend/app/system/performance/page.tsx": (
        "performance-cache-panel",
        "performance-summary-panel",
        "performance-slow-panel",
        "performance-path-panel",
        "RecentActionsPanel",
    ),
}

FORBIDDEN_MAIN_UI_TEXT = (
    "raw JSON",
    "Failed to fetch",
    "debug payload",
)


def nav_targets() -> list[str]:
    text = APP_SHELL.read_text(encoding="utf-8")
    return re.findall(r'href:\s*"([^"]+)"', text)


def count_panels(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.count('className="panel') + text.count("className='panel")


def main() -> None:
    failures: list[str] = []
    targets = nav_targets()
    unique_targets = set(targets)
    if len(targets) > MAX_MAIN_NAV_TARGETS:
        failures.append(f"Main navigation has {len(targets)} targets; budget is {MAX_MAIN_NAV_TARGETS}.")
    if len(targets) != len(unique_targets):
        failures.append("Main navigation contains duplicate href targets.")

    for relative, limit in MAX_PAGE_PANELS.items():
        path = ROOT / relative
        panels = count_panels(path)
        if panels > limit:
            failures.append(f"{relative} has {panels} panels; budget is {limit}.")

    for relative, snippets in REQUIRED_VISUAL_SNIPPETS.items():
        text = (ROOT / relative).read_text(encoding="utf-8", errors="replace")
        for snippet in snippets:
            if snippet not in text:
                failures.append(f"{relative} is missing V4.8 visual/performance snippet: {snippet}")

    for path in sorted([*APP_DIR.rglob("*.tsx"), *(FRONTEND / "components").rglob("*.tsx")]):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for forbidden in FORBIDDEN_MAIN_UI_TEXT:
            if forbidden in text:
                failures.append(f"{relative} contains forbidden main UI text: {forbidden}")

    print("ui_performance_budget=checked")
    print(f"main_nav_targets={len(targets)}")
    print(f"main_nav_budget={MAX_MAIN_NAV_TARGETS}")
    print(f"visual_pages={len(REQUIRED_VISUAL_SNIPPETS)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
