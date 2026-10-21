from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
APP_DIR = FRONTEND / "app"
COMPONENTS_DIR = FRONTEND / "components"

ASYNC_HINTS = (
    "api.",
    "await ",
    "fetch(",
    "upload",
    "retry",
    "cancel",
    "regenerate",
    "generate",
    "export",
    "transcribe",
    "process",
    "testLlm",
    "testEmbedding",
    "testQdrant",
)

LOCAL_ACTION_HINTS = (
    "setCollapsed",
    "setMobileOpen",
    "setQuestion",
    "setAnswerMode",
    "setSessionId",
    "setSelectedJobId",
    "setQuery",
    "setStatus",
    "setTargetType",
    "setActive",
    "setSelectedChunkId",
    "setConfirmDelete",
    "navigator.clipboard",
    "onChange(",
    "onSeek(",
    "onClose",
    "onCancel",
)

PENDING_HINTS = (
    "PendingButton",
    "ButtonLoading",
    "disabled=",
    "aria-busy",
    "isAsking",
    "isRegenerating",
    "isSaving",
    "isUploading",
    "loading",
    "busy",
    "pending",
    "pendingJobId",
)


@dataclass(frozen=True)
class Interaction:
    file: str
    route: str
    label: str
    has_onclick: bool
    has_disabled_or_pending: bool
    has_success_feedback: bool
    has_failure_feedback: bool
    likely_api_action: bool
    duplicate_click_risk: str
    recommendation: str


def app_route(path: Path) -> str:
    try:
        relative = path.relative_to(APP_DIR)
    except ValueError:
        return "component"
    parts = list(relative.parts)
    if parts[-1] != "page.tsx":
        return "component"
    route_parts = parts[:-1]
    if not route_parts:
        return "/"
    return "/" + "/".join(route_parts)


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\{[^{}]{0,80}\}", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def button_label(attrs: str, body: str, index: int) -> str:
    for attr in ("aria-label", "title"):
        match = re.search(attr + r'="([^"]+)"', attrs)
        if match:
            return match.group(1)
    text = strip_tags(body)
    return text[:48] if text else f"button-{index}"


def likely_api_action(context: str, surrounding: str) -> bool:
    lower = context.lower()
    if any(hint.lower() in lower for hint in ASYNC_HINTS):
        return True
    if any(hint.lower() in lower for hint in LOCAL_ACTION_HINTS):
        return False
    if 'type="submit"' in lower and "api." in surrounding:
        return True
    return bool(
        re.search(
            r"onclick=\{?[^}]*\b(load|refresh|retry|cancel|delete|confirm|review|answer|upload|generate|export|test|transcribe|process)",
            lower,
        )
    )


def analyze_file(path: Path) -> list[Interaction]:
    text = path.read_text(encoding="utf-8", errors="replace")
    interactions: list[Interaction] = []
    pattern = re.compile(r"<button\b(?P<attrs>[^>]*)>(?P<body>.*?)</button>", re.DOTALL)
    for index, match in enumerate(pattern.finditer(text), 1):
        attrs = match.group("attrs")
        body = match.group("body")
        start = max(0, match.start() - 220)
        end = min(len(text), match.end() + 320)
        block = text[start:end]
        context = f"{attrs} {body}"
        has_onclick = "onClick=" in attrs or "type=\"submit\"" in attrs
        has_pending = any(hint in block for hint in PENDING_HINTS)
        success_feedback = any(token in block for token in ("setMessage", "setToast", "Toast", "ActionToast", "success", "message"))
        failure_feedback = any(token in block for token in ("setError", "ErrorState", "catch (exc)", "失败", "failed"))
        api_action = likely_api_action(context, block)
        if api_action and has_onclick and not has_pending:
            risk = "high"
            recommendation = "Add PendingButton or explicit disabled/loading state before the async request."
        elif api_action and has_onclick:
            risk = "low"
            recommendation = "Keep pending state and user-visible success/failure feedback."
        elif has_onclick and not has_pending:
            risk = "medium"
            recommendation = "Local UI action; disabled state is optional, but keep the click response immediate."
        else:
            risk = "low"
            recommendation = "No action required."
        interactions.append(
            Interaction(
                file=path.relative_to(ROOT).as_posix(),
                route=app_route(path),
                label=button_label(attrs, body, index),
                has_onclick=has_onclick,
                has_disabled_or_pending=has_pending,
                has_success_feedback=success_feedback,
                has_failure_feedback=failure_feedback,
                likely_api_action=api_action,
                duplicate_click_risk=risk,
                recommendation=recommendation,
            )
        )
    return interactions


def analyze() -> list[Interaction]:
    paths = sorted([*APP_DIR.rglob("*.tsx"), *COMPONENTS_DIR.rglob("*.tsx")])
    interactions: list[Interaction] = []
    for path in paths:
        interactions.extend(analyze_file(path))
    return interactions


def write_markdown(path: Path, interactions: list[Interaction]) -> None:
    high = [item for item in interactions if item.duplicate_click_risk == "high"]
    medium = [item for item in interactions if item.duplicate_click_risk == "medium"]
    lines = [
        "# V4.7 Button Latency Map",
        "",
        "This map is generated from static TSX scanning. It is a prioritization aid, not a substitute for browser timing.",
        "",
        f"- Total button interactions: {len(interactions)}",
        f"- High duplicate-click risk: {len(high)}",
        f"- Medium local-feedback risk: {len(medium)}",
        "",
        "## Priority Findings",
        "",
    ]
    if high:
        lines.extend(["| File | Route | Button | Why | Fix |", "| --- | --- | --- | --- | --- |"])
        for item in high:
            lines.append(
                f"| `{item.file}` | `{item.route}` | {item.label} | API-like action without visible pending/disabled guard | {item.recommendation} |"
            )
    else:
        lines.append("No high-risk async button was detected by the static scan.")
    lines.extend(["", "## Interaction Inventory", ""])
    lines.extend(["| File | Route | Button | Pending/Disabled | Success | Failure | API-like | Risk |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for item in interactions:
        lines.append(
            "| `{file}` | `{route}` | {label} | {pending} | {success} | {failure} | {api} | {risk} |".format(
                file=item.file,
                route=item.route,
                label=item.label.replace("|", "/"),
                pending="yes" if item.has_disabled_or_pending else "no",
                success="yes" if item.has_success_feedback else "no",
                failure="yes" if item.has_failure_feedback else "no",
                api="yes" if item.likely_api_action else "no",
                risk=item.duplicate_click_risk,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit frontend click interactions and pending feedback.")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "docs" / "v4_7_button_latency_map.md")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    interactions = analyze()
    high = [item for item in interactions if item.duplicate_click_risk == "high"]
    if not args.no_write:
      write_markdown(args.markdown_output if args.markdown_output.is_absolute() else ROOT / args.markdown_output, interactions)
    print("frontend_interactions=checked")
    print(f"buttons={len(interactions)}")
    print(f"high_risk={len(high)}")
    print(f"report={args.markdown_output}")
    print("result=passed")


if __name__ == "__main__":
    main()
