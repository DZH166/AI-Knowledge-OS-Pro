from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
APP_DIR = FRONTEND / "app"
APP_SHELL = FRONTEND / "components" / "AppShell.tsx"

REQUIRED_ROUTES = (
    "/",
    "/dashboard",
    "/upload",
    "/tasks",
    "/chat",
    "/chat/history",
    "/documents",
    "/knowledge",
    "/media",
    "/code",
    "/media/sources/[id]",
    "/errors",
    "/learning",
    "/learning/roadmap",
    "/learning/project-structure",
    "/learning/knowledge-graph",
    "/learning/cards",
    "/learning/knowledge-points",
    "/learning/knowledge-points/[id]",
    "/learning/quizzes",
    "/learning/notes",
    "/portfolio",
    "/portfolio/resume",
    "/portfolio/interview",
    "/portfolio/project-review",
    "/system",
    "/system/observability",
    "/system/settings",
)

REQUIRED_TEXT = {
    "frontend/app/system/page.tsx": ("能力配置向导", "NOT_CONFIGURED"),
    "frontend/app/system/settings/page.tsx": ("安全边界", "Provider 诊断文档"),
    "frontend/app/system/observability/page.tsx": ("request_id", "retrieval_trace_id"),
    "frontend/app/portfolio/page.tsx": ("真实项目概览", "NOT_CONFIGURED"),
    "frontend/app/code/page.tsx": ("代码仓库接入", "EMBEDDING_NOT_CONFIGURED"),
    "frontend/app/learning/roadmap/page.tsx": ("学习路线", "existing_knowledge_points_cards_quizzes_notes"),
    "frontend/app/learning/project-structure/page.tsx": ("项目构造讲解", "RAG 证据流", "多模态处理流", "release dry-run"),
    "frontend/app/learning/knowledge-graph/page.tsx": ("知识关系", "used_by_project"),
    "frontend/app/media/sources/[id]/page.tsx": ("元数据摘要", "处理详情"),
    "frontend/app/tasks/page.tsx": ("恢复建议", "事件时间线"),
    "frontend/components/ui.tsx": (
        "DemoModeBanner",
        "CapabilityWarning",
        "ProviderMissingWarning",
        "LoadingState",
        "TaskStatusBadge",
        "LearningActionBar",
        "SourceLocatorButton",
        "TaskLogDrawer",
        "\\u53ef\\u80fd\\u539f\\u56e0",
        "\\u4e0b\\u4e00\\u6b65",
    ),
    "frontend/services/api.ts": (
        "queued: \"\\u6392\\u961f\\u4e2d\"",
        "running: \"\\u5904\\u7406\\u4e2d\"",
        "completed: \"\\u5df2\\u5b8c\\u6210\"",
        "failed: \"\\u5931\\u8d25\"",
        "cancelled: \"\\u5df2\\u53d6\\u6d88\"",
        "retrying: \"\\u91cd\\u8bd5\\u4e2d\"",
        "not_configured: \"\\u672a\\u914d\\u7f6e\"",
        "demo: \"\\u6f14\\u793a\\u6a21\\u5f0f\"",
        "real: \"\\u771f\\u5b9e\\u6a21\\u5f0f\"",
    ),
}

FORBIDDEN_UI_PATTERNS = (
    "Metadata JSON",
    "raw JSON",
    "debug payload",
    "Failed to fetch",
    "JSON.stringify(",
)

ALLOWED_PRE_FILES = {
    "frontend/app/errors/page.tsx",
    "frontend/app/media/sources/[id]/page.tsx",
    "frontend/components/ui.tsx",
}


@dataclass
class SmokeResult:
    checked_routes: int
    nav_targets: int
    warnings: list[str]
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def route_to_page(route: str) -> Path:
    if route == "/":
        return APP_DIR / "page.tsx"
    return APP_DIR.joinpath(*route.strip("/").split("/")) / "page.tsx"


def app_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def extract_nav_targets() -> list[str]:
    text = APP_SHELL.read_text(encoding="utf-8")
    return re.findall(r'href:\s*"([^"]+)"', text)


def scan_forbidden_ui_patterns() -> list[str]:
    failures: list[str] = []
    for path in sorted([*APP_DIR.rglob("*.tsx"), *(FRONTEND / "components").rglob("*.tsx")]):
        relative = app_relative(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_UI_PATTERNS:
            if pattern in text:
                failures.append(f"{relative} contains forbidden UI pattern: {pattern}")
        if "<pre" in text and relative not in ALLOWED_PRE_FILES:
            failures.append(f"{relative} contains <pre> outside the approved evidence/code views")
    return failures


def scan_required_text() -> list[str]:
    failures: list[str] = []
    for relative, snippets in REQUIRED_TEXT.items():
        path = ROOT / relative
        if not path.exists():
            failures.append(f"Missing file for required text scan: {relative}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for snippet in snippets:
            if snippet not in text:
                failures.append(f"{relative} is missing required UI text: {snippet}")
    return failures


def evaluate_frontend() -> SmokeResult:
    warnings: list[str] = []
    failures: list[str] = []

    for route in REQUIRED_ROUTES:
        page = route_to_page(route)
        if not page.exists():
            failures.append(f"Missing required page for {route}: {app_relative(page)}")

    nav_targets = extract_nav_targets()
    if not nav_targets:
        failures.append("No navigation targets found in AppShell.")

    for href in sorted(set(nav_targets)):
        page = route_to_page(href)
        if not page.exists():
            failures.append(f"Navigation target {href} has no page file: {app_relative(page)}")

    duplicates = sorted({href for href in nav_targets if nav_targets.count(href) > 1})
    for href in duplicates:
        failures.append(f"Navigation target {href} is reused by multiple labels")

    failures.extend(scan_forbidden_ui_patterns())
    failures.extend(scan_required_text())

    return SmokeResult(
        checked_routes=len(REQUIRED_ROUTES),
        nav_targets=len(nav_targets),
        warnings=warnings,
        failures=failures,
    )


def main() -> None:
    result = evaluate_frontend()
    print("frontend_smoke=checked")
    print(f"required_routes={result.checked_routes}")
    print(f"nav_targets={result.nav_targets}")
    print(f"warnings={len(result.warnings)}")
    for warning in result.warnings:
        print(f"warning: {warning}")
    if result.failures:
        print("result=failed")
        for failure in result.failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
