from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
APP_DIR = FRONTEND / "app"
APP_SHELL = FRONTEND / "components" / "AppShell.tsx"
NAVIGATION_CONFIG = FRONTEND / "components" / "product-navigation.ts"

PRIMARY_NAV_TARGETS = ("/workbench", "/runs", "/library", "/artifacts")
MAX_DEVELOPER_NAV_TARGETS = 8
MAX_MAIN_NAV_TARGETS = len(PRIMARY_NAV_TARGETS) + MAX_DEVELOPER_NAV_TARGETS
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
        "<strong>溯知</strong>",
        "证据研究工作台",
        "navigationGroups.flatMap",
        "developer-nav",
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


def nav_targets() -> tuple[list[str], list[str]]:
    text = NAVIGATION_CONFIG.read_text(encoding="utf-8")
    primary_marker = 'kind: "primary"'
    developer_marker = 'kind: "developer"'
    primary_start = text.find(primary_marker)
    developer_start = text.find(developer_marker)
    if primary_start < 0 or developer_start <= primary_start:
        return [], []
    primary = re.findall(r'href:\s*"([^"]+)"', text[primary_start:developer_start])
    developer = re.findall(r'href:\s*"([^"]+)"', text[developer_start:])
    return primary, developer


def count_panels(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.count('className="panel') + text.count("className='panel")


def main() -> None:
    failures: list[str] = []
    primary_targets, developer_targets = nav_targets()
    targets = [*primary_targets, *developer_targets]
    unique_targets = set(targets)
    if tuple(primary_targets) != PRIMARY_NAV_TARGETS:
        failures.append(
            "Primary navigation must contain exactly: " + ", ".join(PRIMARY_NAV_TARGETS) + "."
        )
    if len(developer_targets) > MAX_DEVELOPER_NAV_TARGETS:
        failures.append(
            f"Developer navigation has {len(developer_targets)} targets; "
            f"budget is {MAX_DEVELOPER_NAV_TARGETS}."
        )
    navigation_text = NAVIGATION_CONFIG.read_text(encoding="utf-8")
    if 'kind: "developer"' not in navigation_text or "collapsedByDefault: true" not in navigation_text:
        failures.append("Developer navigation must remain an explicitly collapsed group.")
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
    print(f"primary_nav_targets={len(primary_targets)}")
    print(f"developer_nav_targets={len(developer_targets)}")
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
