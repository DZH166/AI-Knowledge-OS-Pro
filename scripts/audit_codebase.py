from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".pytest_tmp",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "node_modules",
    "out",
    "releases",
    "storage",
    "sub2api",
    "venv",
}

TEXT_SUFFIXES = {
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

GENERATED_AUDIT_GLOBS = (
    "docs/v4_1_*.md",
    "docs/v4_1_*.json",
)

COMMON_REFERENCE_TOKENS = {
    "__init__",
    "api",
    "app",
    "config",
    "index",
    "layout",
    "main",
    "page",
    "readme",
    "route",
    "schema",
    "service",
    "types",
    "utils",
}

HISTORICAL_DOC_PATTERNS = (
    re.compile(r"docs/v\d+(?:_\d+)?_.*\.(?:md|json)$"),
    re.compile(r"docs/v\d+.*report\.md$"),
    re.compile(r"docs/archive/v\d+/v\d+(?:_\d+)?_.*\.(?:md|json)$"),
    re.compile(r"docs/archive/v\d+/v\d+.*report\.md$"),
)

MOJIBAKE_TOKENS = (
    "\ufffd",
    "鍥",
    "瑙",
    "闊",
    "瀛",
    "璇",
    "鎴",
)


@dataclass
class Endpoint:
    file: str
    method: str
    path: str
    function: str


@dataclass
class Asset:
    path: str
    area: str
    kind: str
    purpose: str
    referenced: bool
    references: list[str]
    has_test_coverage: bool
    suspected_dead: bool
    recommendation: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_excluded(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return True
    return any(part in EXCLUDED_PARTS for part in relative.parts)


def iter_files(*roots: Path) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not is_excluded(path):
                files.append(path)
    return sorted(files)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_file() and not is_excluded(path) and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return sorted(files)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def is_generated_audit_file(path: Path) -> bool:
    r = rel(path)
    return any(Path(r).match(pattern) for pattern in GENERATED_AUDIT_GLOBS)


def git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return ""
    return result.stdout.strip()


def classify(path: Path) -> tuple[str, str, str]:
    r = rel(path)
    name = path.name
    suffix = path.suffix.lower()
    parts = path.relative_to(ROOT).parts

    if r.startswith("backend/app/api/routes_"):
        return "backend", "FastAPI route", "HTTP API endpoints and request orchestration."
    if r == "backend/app/api/router.py":
        return "backend", "FastAPI router", "Top-level API router composition."
    if r.startswith("backend/app/services/"):
        return "backend", "service", "Domain business logic and integration boundary."
    if r.startswith("backend/app/models/"):
        return "backend", "model", "SQLAlchemy persistence model."
    if r.startswith("backend/app/schemas/"):
        return "backend", "schema", "Pydantic request/response contract."
    if r.startswith("backend/app/providers/"):
        return "backend", "provider", "External provider adapter or client."
    if r.startswith("backend/app/tasks/") or r.startswith("backend/app/workers/"):
        return "backend", "task/worker", "Background task processing."
    if r.startswith("backend/app/db/") or r.startswith("backend/alembic/") or r.startswith("alembic/"):
        return "backend", "database/migration", "Database setup or migration."
    if r.startswith("backend/tests/"):
        return "backend", "test", "Backend regression or service test."
    if r.startswith("backend/app/"):
        return "backend", "utility/helper", "Backend support module."

    if r.startswith("frontend/app/") and name in {"page.tsx", "layout.tsx", "loading.tsx", "error.tsx", "not-found.tsx"}:
        return "frontend", "app route/page", "Next.js app route or route state."
    if r.startswith("frontend/components/"):
        return "frontend", "component", "Reusable React UI component."
    if r.startswith("frontend/hooks/"):
        return "frontend", "hook", "Reusable React hook."
    if r.startswith("frontend/services/"):
        return "frontend", "API client", "Frontend service or API wrapper."
    if r.startswith("frontend/types/"):
        return "frontend", "type definition", "Shared TypeScript type contract."
    if r.startswith("frontend/app/") and suffix in {".css", ".scss"}:
        return "frontend", "style", "Frontend styling."
    if r.startswith("frontend/") and name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
        return "frontend", "test", "Frontend test."
    if r.startswith("frontend/"):
        return "frontend", "utility/config", "Frontend utility or configuration."

    if r.startswith("scripts/"):
        if name.startswith("check_"):
            return "scripts", "check script", "Quality gate or repository check."
        if "seed" in name:
            return "scripts", "seed script", "Synthetic data or showcase seeding."
        if "demo" in name or "showcase" in name:
            return "scripts", "demo script", "Demo preparation or showcase support."
        if "release" in name:
            return "scripts", "release script", "Release packaging or safety verification."
        if "learning" in name:
            return "scripts", "learning package script", "Learning package generation."
        if "evaluate" in name:
            return "scripts", "evaluation script", "Evaluation or benchmark helper."
        return "scripts", "maintenance script", "Repository maintenance helper."

    if r.startswith(".github/workflows/"):
        return "ci/config", "GitHub Actions workflow", "CI automation."
    if r.startswith(".github/"):
        return "ci/config", "GitHub config", "GitHub project metadata."
    if name in {"docker-compose.yml", ".gitignore", "pytest.ini", "alembic.ini"}:
        return "ci/config", "project config", "Repository configuration."
    if name in {"package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "tsconfig.json"}:
        return "ci/config", "frontend config", "Frontend dependency or compiler configuration."
    if name.startswith("requirements"):
        return "ci/config", "backend dependency config", "Backend dependency declaration."
    if name.endswith(".example"):
        return "ci/config", "environment example", "Safe environment variable template."

    if r == "README.md":
        return "docs", "README", "Project landing documentation."
    if r.startswith("docs/"):
        if any(pattern.match(r) for pattern in HISTORICAL_DOC_PATTERNS):
            return "docs", "historical report", "Versioned historical report or learning artifact."
        if "learning" in name:
            return "docs", "learning doc", "Learning archive or learning system documentation."
        if "release" in name:
            return "docs", "release doc", "Release or checklist documentation."
        if "architecture" in name:
            return "docs", "architecture doc", "Architecture documentation."
        return "docs", "documentation", "Project documentation."

    return "other", "other", "Repository asset."


def collect_text_index(files: Iterable[Path]) -> dict[str, str]:
    index: dict[str, str] = {}
    for path in files:
        if is_generated_audit_file(path):
            continue
        text = read_text(path)
        if text:
            index[rel(path)] = text
    return index


def reference_tokens(path: Path) -> set[str]:
    r = rel(path)
    name = Path(r).name
    stem = Path(r).stem
    tokens = {r}
    if name.lower() not in COMMON_REFERENCE_TOKENS:
        tokens.add(name)
    if stem.lower() not in COMMON_REFERENCE_TOKENS:
        tokens.add(stem)
    if path.suffix in {".py", ".ts", ".tsx", ".js"}:
        tokens.add(Path(r).with_suffix("").as_posix())
        kebab = stem.replace("_", "-")
        snake = stem.replace("-", "_")
        if kebab.lower() not in COMMON_REFERENCE_TOKENS:
            tokens.add(kebab)
        if snake.lower() not in COMMON_REFERENCE_TOKENS:
            tokens.add(snake)
    return {token for token in tokens if len(token) >= 4 and token.lower() not in COMMON_REFERENCE_TOKENS}


def find_references(path: Path, text_index: dict[str, str]) -> list[str]:
    r = rel(path)
    tokens = reference_tokens(path)
    references: list[str] = []
    for other, text in text_index.items():
        if other == r:
            continue
        if any(token in text for token in tokens):
            references.append(other)
    return references[:40]


def has_tests(path: Path, references: list[str], text_index: dict[str, str]) -> bool:
    r = rel(path)
    stem = path.stem
    if "/tests/" in r or r.startswith("backend/tests/"):
        return True
    if any("/tests/" in item or item.startswith("backend/tests/") for item in references):
        return True
    for other, text in text_index.items():
        if ("/tests/" in other or other.startswith("backend/tests/")) and stem in text:
            return True
    return False


def is_entrypoint(path: Path, kind: str) -> bool:
    r = rel(path)
    if kind in {"README", "project config", "frontend config", "backend dependency config", "GitHub Actions workflow"}:
        return True
    if kind in {"FastAPI route", "FastAPI router", "app route/page"}:
        return True
    if r in {
        "backend/app/main.py",
        "frontend/app/layout.tsx",
        "frontend/app/page.tsx",
        "scripts/audit_codebase.py",
    }:
        return True
    return False


def recommendation_for(path: Path, area: str, kind: str, references: list[str], covered: bool) -> tuple[bool, str]:
    r = rel(path)
    if r in {"docs/learning_log.md", "docs/stage_delivery_log.md"}:
        return False, "Keep append-only historical archive."
    if kind == "historical report":
        return False, "Keep, but consider moving to docs/archive by version."
    if is_entrypoint(path, kind):
        return False, "Keep entrypoint; verify route/config remains documented."
    if kind in {"test", "schema", "model"} and covered:
        return False, "Keep; participates in tests or API/data contracts."
    if not references and kind in {"component", "hook", "utility/helper", "maintenance script", "documentation"}:
        return True, "Candidate for review: no static references found. Verify runtime/manual usage before deleting."
    if not references and kind in {"service", "provider", "API client", "type definition"}:
        return True, "Candidate for deeper review: contract-like file with no static references found."
    if kind == "historical report":
        return False, "Archive candidate, not deletion candidate."
    return False, "Keep for now; static references or entrypoint semantics found."


def extract_endpoints(route_file: Path) -> list[Endpoint]:
    text = read_text(route_file)
    if not text:
        return []
    prefix = ""
    prefix_match = re.search(r"APIRouter\([^)]*prefix=[\"']([^\"']+)[\"']", text, re.S)
    if prefix_match:
        prefix = prefix_match.group(1)
    endpoints: list[Endpoint] = []
    pattern = re.compile(
        r"@router\.(get|post|put|patch|delete)\([\"']([^\"']*)[\"'][^\n]*\)\s*\ndef\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.M,
    )
    for method, path, function in pattern.findall(text):
        full_path = f"/api{prefix}{path}".replace("//", "/")
        endpoints.append(Endpoint(file=rel(route_file), method=method.upper(), path=full_path, function=function))
    return endpoints


def frontend_routes() -> list[str]:
    routes: list[str] = []
    app_dir = ROOT / "frontend" / "app"
    if not app_dir.exists():
        return routes
    for page in app_dir.rglob("page.tsx"):
        route_dir = page.parent.relative_to(app_dir)
        parts = [part for part in route_dir.parts if not part.startswith("(")]
        route = "/" + "/".join(parts)
        routes.append(route if route != "/" else "/")
    return sorted(routes)


def count_dependencies() -> dict[str, int]:
    counts: dict[str, int] = {}
    requirements = ROOT / "backend" / "requirements.txt"
    if requirements.exists():
        counts["backend_requirements"] = sum(
            1 for line in read_text(requirements).splitlines() if line.strip() and not line.strip().startswith("#")
        )
    package_json = ROOT / "frontend" / "package.json"
    if package_json.exists():
        data = json.loads(read_text(package_json))
        counts["frontend_dependencies"] = len(data.get("dependencies", {}))
        counts["frontend_dev_dependencies"] = len(data.get("devDependencies", {}))
    return counts


def scan_todos(text_index: dict[str, str]) -> list[str]:
    matches: list[str] = []
    pattern = re.compile(r"\b(TODO|FIXME|DEPRECATED)\b", re.I)
    for path, text in text_index.items():
        if path == "scripts/audit_codebase.py" or path.startswith("docs/v4_1_"):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                matches.append(f"{path}:{line_number}: {line.strip()[:160]}")
    return matches[:200]


def scan_mojibake_docs() -> list[str]:
    matches: list[str] = []
    for path in iter_files(DOCS):
        text = read_text(path)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(token in line for token in MOJIBAKE_TOKENS):
                matches.append(f"{rel(path)}:{line_number}")
                break
    return matches


def duplicate_names(files: list[Path]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for path in files:
        grouped[path.name].append(rel(path))
    return {name: paths for name, paths in sorted(grouped.items()) if len(paths) > 1}


def build_inventory() -> dict[str, object]:
    source_roots = [
        ROOT / "backend",
        ROOT / "frontend" / "app",
        ROOT / "frontend" / "components",
        ROOT / "frontend" / "services",
        ROOT / "frontend" / "types",
        ROOT / "frontend" / "hooks",
        ROOT / "scripts",
        ROOT / "docs",
        ROOT / ".github",
    ]
    files = iter_files(*source_roots)
    config_files = [
        ROOT / "README.md",
        ROOT / ".env.example",
        ROOT / ".gitignore",
        ROOT / "docker-compose.yml",
        ROOT / "pytest.ini",
        ROOT / "alembic.ini",
        ROOT / "backend" / "requirements.txt",
        ROOT / "frontend" / "package.json",
        ROOT / "frontend" / "package-lock.json",
        ROOT / "frontend" / "pnpm-lock.yaml",
        ROOT / "frontend" / "pnpm-workspace.yaml",
        ROOT / "frontend" / "tsconfig.json",
    ]
    files = sorted(set(files + [path for path in config_files if path.exists()]))
    text_index = collect_text_index(iter_text_files())

    assets: list[Asset] = []
    for path in files:
        area, kind, purpose = classify(path)
        references = find_references(path, text_index)
        covered = has_tests(path, references, text_index)
        suspected, recommendation = recommendation_for(path, area, kind, references, covered)
        assets.append(
            Asset(
                path=rel(path),
                area=area,
                kind=kind,
                purpose=purpose,
                referenced=bool(references) or is_entrypoint(path, kind),
                references=references,
                has_test_coverage=covered,
                suspected_dead=suspected,
                recommendation=recommendation,
            )
        )

    route_files = sorted((ROOT / "backend" / "app" / "api").glob("routes_*.py"))
    endpoints = [endpoint for route_file in route_files for endpoint in extract_endpoints(route_file)]
    counter = Counter((asset.area, asset.kind) for asset in assets)
    dependency_counts = count_dependencies()
    text_files = iter_text_files()
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git("rev-parse", "HEAD"),
            "remote": git("remote", "get-url", "origin"),
            "tags_at_head": git("tag", "--points-at", "HEAD").splitlines(),
        },
        "stats": {
            "assets": len(assets),
            "backend_modules": len(iter_files(ROOT / "backend" / "app")),
            "frontend_routes": len(frontend_routes()),
            "frontend_components": len(iter_files(ROOT / "frontend" / "components")),
            "scripts": len(iter_files(ROOT / "scripts")),
            "tests": len(iter_files(ROOT / "backend" / "tests")),
            "docs": len(iter_files(ROOT / "docs")),
            "workflows": len(iter_files(ROOT / ".github" / "workflows")),
            "text_files": len(text_files),
            **dependency_counts,
        },
        "frontend_routes": frontend_routes(),
        "endpoints": [asdict(endpoint) for endpoint in endpoints],
        "areas": {f"{area}/{kind}": count for (area, kind), count in sorted(counter.items())},
        "duplicates": duplicate_names(files),
        "todos": scan_todos(text_index),
        "mojibake_docs": scan_mojibake_docs(),
        "assets": [asdict(asset) for asset in assets],
    }


def write_json(inventory: dict[str, object]) -> None:
    path = DOCS / "v4_1_code_inventory.json"
    path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def write_inventory_md(inventory: dict[str, object]) -> None:
    stats = inventory["stats"]
    assert isinstance(stats, dict)
    assets = inventory["assets"]
    assert isinstance(assets, list)
    endpoints = inventory["endpoints"]
    assert isinstance(endpoints, list)
    suspected = [asset for asset in assets if asset["suspected_dead"]]

    rows = []
    for key, value in stats.items():
        rows.append([str(key), str(value)])

    endpoint_rows = [[item["method"], item["path"], item["function"], item["file"]] for item in endpoints]
    suspected_rows = [
        [
            item["path"],
            item["kind"],
            "yes" if item["has_test_coverage"] else "no",
            item["recommendation"],
        ]
        for item in suspected[:60]
    ]
    asset_rows = [
        [
            item["path"],
            item["area"],
            item["kind"],
            "yes" if item["referenced"] else "no",
            "yes" if item["has_test_coverage"] else "no",
            item["recommendation"],
        ]
        for item in assets[:120]
    ]
    content = [
        "# V4.1 Code Inventory",
        "",
        f"Generated at: `{inventory['generated_at']}`",
        "",
        "This inventory is generated by `python scripts/audit_codebase.py`. It is a conservative static scan: a file with no static references is a review candidate, not an automatic deletion target.",
        "",
        "## Summary",
        "",
        markdown_table(rows, ["Metric", "Value"]),
        "",
        "## API Endpoints",
        "",
        markdown_table(endpoint_rows, ["Method", "Path", "Function", "File"]) if endpoint_rows else "No endpoints detected.",
        "",
        "## Suspected Dead-Code Review Candidates",
        "",
        markdown_table(suspected_rows, ["Path", "Kind", "Test Coverage", "Recommendation"]) if suspected_rows else "No review candidates detected by the first static pass.",
        "",
        "## Asset Sample",
        "",
        markdown_table(asset_rows, ["Path", "Area", "Kind", "Referenced", "Tested", "Recommendation"]),
        "",
        "The full machine-readable inventory is stored in `docs/v4_1_code_inventory.json`.",
        "",
    ]
    (DOCS / "v4_1_code_inventory.md").write_text("\n".join(content), encoding="utf-8")


def write_predevelopment_audit(inventory: dict[str, object]) -> None:
    stats = inventory["stats"]
    assert isinstance(stats, dict)
    duplicates = inventory["duplicates"]
    assert isinstance(duplicates, dict)
    todos = inventory["todos"]
    assert isinstance(todos, list)
    mojibake_docs = inventory["mojibake_docs"]
    assert isinstance(mojibake_docs, list)
    git_info = inventory["git"]
    assert isinstance(git_info, dict)

    status = git("status", "--short", "--branch")
    tree_preview = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()
    top_level = sorted({line.split("/", 1)[0] for line in tree_preview if line})
    readme = ROOT / "README.md"
    readme_text = read_text(readme)
    version_lines = []
    for path in [ROOT / "backend" / "app" / "core" / "config.py", ROOT / "frontend" / "package.json", ROOT / "README.md"]:
        text = read_text(path)
        if "V3.8" in text or "3.8.0" in text:
            version_lines.append(rel(path))
    archive_dir = DOCS / "archive"
    archive_status = "`docs/archive` exists." if archive_dir.exists() else "`docs/archive` does not exist yet."
    scattered_reports = [
        rel(path)
        for path in DOCS.glob("*")
        if path.is_file() and re.match(r"^v\d+(?:_\d+)?_", path.name) and not path.name.startswith("v4_1_")
    ]

    duplicate_sample = [f"{name}: {', '.join(paths[:4])}" for name, paths in list(duplicates.items())[:15]]
    content = [
        "# V4.1 Predevelopment Audit",
        "",
        f"Generated at: `{inventory['generated_at']}`",
        "",
        "## Baseline",
        "",
        f"- Current branch before V4.1 work: `feature/v4.0-knowledge-portfolio-os`.",
        f"- Current V4.1 working branch: `{git_info.get('branch', '')}`.",
        f"- Current commit SHA: `{git_info.get('commit', '')}`.",
        f"- Remote repository: `{git_info.get('remote', '')}`.",
        f"- Tags at HEAD: `{', '.join(git_info.get('tags_at_head', [])) or 'none'}`.",
        "- Current Git status:",
        "",
        "```text",
        status,
        "```",
        "",
        "Untracked files were present before the V4.1 audit started and are preserved: `frontend/pnpm-lock.yaml`, `frontend/pnpm-workspace.yaml`.",
        "",
        "## Directory Tree Snapshot",
        "",
        f"- Top-level tracked entries: `{', '.join(top_level)}`.",
        f"- Tracked file count: `{len(tree_preview)}`.",
        "- Source tree counts are generated from the current working tree excluding `.git`, caches, databases, uploads, releases, `.next` and `node_modules`.",
        "",
        "## Required Audit Items",
        "",
        markdown_table(
            [
                ["1", "Current branch", str(git_info.get("branch", ""))],
                ["2", "Current commit SHA", str(git_info.get("commit", ""))],
                ["3", "Remote repository", str(git_info.get("remote", ""))],
                ["4", "Current tag", ", ".join(git_info.get("tags_at_head", [])) or "none at HEAD"],
                ["5", "Directory tree", f"Top-level: {', '.join(top_level)}"],
                ["6", "Backend module count", str(stats.get("backend_modules"))],
                ["7", "Frontend page count", str(stats.get("frontend_routes"))],
                ["8", "Frontend component count", str(stats.get("frontend_components"))],
                ["9", "Script count", str(stats.get("scripts"))],
                ["10", "Test file count", str(stats.get("tests"))],
                ["11", "Docs file count", str(stats.get("docs"))],
                ["12", "GitHub workflow count", str(stats.get("workflows"))],
                [
                    "13",
                    "Dependency count",
                    f"backend={stats.get('backend_requirements')}, frontend runtime={stats.get('frontend_dependencies')}, frontend dev={stats.get('frontend_dev_dependencies')}",
                ],
                [
                    "14",
                    "README status",
                    "Present; large portfolio README. Needs V4.1 review for current-scope accuracy, but not replaced in this first pass.",
                ],
                ["15", "System version", "Current tracked code reports V3.8 / 3.8.0 in config/package/README; V4.1 is a cleanup branch, not yet a released version."],
                ["16", "CI status", "Workflow files exist; GitHub Actions status is not verified locally because branch has not been pushed in this pass."],
                ["17", "Release script status", "`scripts/release.py` exists and is included in later dry-run validation."],
                ["18", "Uncommitted sensitive files", "No committed sensitive files checked yet in this first audit; `check_secrets.py` remains a required quality gate."],
                ["19", "Obvious mojibake docs", "None detected in docs by static token scan." if not mojibake_docs else "; ".join(mojibake_docs[:20])],
                ["20", "Duplicate named files", f"{len(duplicates)} duplicate basenames detected; many are expected Next.js route files such as `page.tsx`."],
                ["21", "Archive directory", archive_status],
                [
                    "22",
                    "Scattered outdated reports",
                    "None detected in docs root." if not scattered_reports else "; ".join(scattered_reports[:20]),
                ],
                ["23", "Pages without entry", "Requires frontend route/nav cross-check; first inventory generated route list."],
                ["24", "Unreferenced components", "Static inventory marks candidates; manual confirmation needed before deletion."],
                ["25", "Uncalled backend routes", "Endpoint list generated; frontend/API/test cross-check follows in cleanup plan."],
                ["26", "Unused scripts", "Static inventory marks candidates; scripts may be manual entrypoints and require conservative handling."],
                ["27", "Unused dependencies", "Dependency audit pending; do not delete before dynamic/provider/CI usage checks."],
                ["28", "TODO/FIXME/DEPRECATED", f"{len(todos)} matching lines found by static scan."],
                ["29", "Tests can pass", "Not yet rerun in this V4.1 first-pass audit; final gate must run `python -m pytest`."],
                ["30", "Build can pass", "Not yet rerun in this V4.1 first-pass audit; final gate must run frontend typecheck/build."],
                [
                    "31",
                    "Largest technical debt",
                    "The project has broad feature surface and many version reports in root docs; needs asset inventory, archive structure and single-source architecture boundaries before more feature work.",
                ],
            ],
            ["#", "Item", "Finding"],
        ),
        "",
        "## Duplicate Name Sample",
        "",
        "\n".join(f"- {item}" for item in duplicate_sample) if duplicate_sample else "No duplicate basenames detected.",
        "",
        "## TODO/FIXME/DEPRECATED Sample",
        "",
        "\n".join(f"- {item}" for item in todos[:30]) if todos else "No TODO/FIXME/DEPRECATED matches detected.",
        "",
        "## Version Evidence",
        "",
        "\n".join(f"- `{item}` contains V3.8 / 3.8.0 markers." for item in version_lines) if version_lines else "- No V3.8 markers found by simple scan.",
        "",
        "## Immediate Next Actions",
        "",
        "1. Use `scripts/audit_codebase.py` output as the source for dead-code and archive planning.",
        "2. Generate `docs/v4_1_dead_code_report.md` and `docs/v4_1_dead_code_plan.md` before deletion.",
        "3. Run quality gates after each meaningful cleanup batch.",
        "",
    ]
    (DOCS / "v4_1_predevelopment_audit.md").write_text("\n".join(content), encoding="utf-8")


def write_dead_code_reports(inventory: dict[str, object]) -> None:
    assets = inventory["assets"]
    assert isinstance(assets, list)
    suspected = [item for item in assets if item["suspected_dead"]]
    historical = [item for item in assets if item["kind"] == "historical report"]
    deprecated = [
        item
        for item in assets
        if any("deprecated" in str(value).lower() for value in [item["path"], item["recommendation"]])
    ]

    report_rows = [
        [
            item["path"],
            item["kind"],
            "No static references found" if not item["references"] else f"Referenced by {len(item['references'])} files",
            "medium" if item["kind"] in {"service", "provider", "API client"} else "low",
            item["recommendation"],
        ]
        for item in suspected[:120]
    ]
    report = [
        "# V4.1 Dead Code Report",
        "",
        "This report is generated from a conservative static scan. It identifies review candidates, not automatic deletion instructions.",
        "",
        "## Candidate Summary",
        "",
        f"- Suspected dead-code review candidates: `{len(suspected)}`.",
        f"- Historical reports to preserve/archive instead of delete: `{len(historical)}`.",
        f"- Deprecated markers found in inventory recommendations/path scan: `{len(deprecated)}`.",
        "",
        "## Review Candidates",
        "",
        markdown_table(report_rows, ["Path", "Type", "Reference Check", "Risk", "Suggested Action"]) if report_rows else "No review candidates detected.",
        "",
        "## Rules Used",
        "",
        "- A-class deletion requires no static references, no tests, no docs dependency, no runtime entrypoint and not a historical archive.",
        "- B-class migration applies to duplicated or scattered valuable logic.",
        "- C-class deprecation applies when usage is uncertain or migration risk is high.",
        "- D-class historical archives, including learning logs and version reports, must be preserved.",
        "",
    ]
    (DOCS / "v4_1_dead_code_report.md").write_text("\n".join(report), encoding="utf-8")

    plan_rows = [
        [
            item["path"],
            "C" if item["kind"] in {"service", "provider", "API client"} else "A-review",
            "Manual usage check, `rg` reference check and relevant tests before any deletion.",
            "Run compileall/pytest/typecheck/build after cleanup batch.",
        ]
        for item in suspected[:80]
    ]
    plan = [
        "# V4.1 Dead Code Cleanup Plan",
        "",
        "## Execution Order",
        "",
        "1. Archive historical reports into `docs/archive/v3` and `docs/archive/v4` without deleting learning archives.",
        "2. Remove or merge only low-risk assets with no references and no runtime entrypoint.",
        "3. Defer service/provider/API-client candidates until route and test coverage prove they are unused.",
        "4. After each cleanup batch, run the narrow relevant gate, then the full final gate.",
        "",
        "## Candidate Actions",
        "",
        markdown_table(plan_rows, ["Path", "Class", "Before Verification", "After Verification"]) if plan_rows else "No cleanup candidates detected.",
        "",
        "## Safety Invariants",
        "",
        "- Do not delete `docs/learning_log.md` or `docs/stage_delivery_log.md`.",
        "- Do not delete user databases, uploads, logs, caches, `.env`, `.next` or `node_modules`.",
        "- Do not replace NOT_CONFIGURED provider refusals with fake OCR, fake transcription or fake answers.",
        "- Keep database migrations and release safety scripts unless a stronger replacement exists.",
        "",
    ]
    (DOCS / "v4_1_dead_code_plan.md").write_text("\n".join(plan), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V4.1 codebase audit inventory and cleanup reports.")
    parser.add_argument("--inventory-only", action="store_true", help="Only generate code inventory files.")
    args = parser.parse_args()

    DOCS.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory()
    write_json(inventory)
    write_inventory_md(inventory)
    if not args.inventory_only:
        write_predevelopment_audit(inventory)
        write_dead_code_reports(inventory)
    print("Generated V4.1 audit artifacts:")
    print("- docs/v4_1_code_inventory.json")
    print("- docs/v4_1_code_inventory.md")
    if not args.inventory_only:
        print("- docs/v4_1_predevelopment_audit.md")
        print("- docs/v4_1_dead_code_report.md")
        print("- docs/v4_1_dead_code_plan.md")


if __name__ == "__main__":
    main()
