from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_frontend_interactions import analyze  # noqa: E402


REQUIRED_SNIPPETS = {
    "frontend/components/ui.tsx": (
        "export function PendingButton",
        "export function ActionToast",
        "export function SkeletonCard",
        "export function LoadingOverlay",
        "export function ProgressivePanel",
    ),
    "frontend/services/api.ts": (
        "REQUEST_TIMEOUT_MS",
        "AbortError",
        "请求超时",
    ),
    "frontend/app/tasks/page.tsx": (
        "pendingJobId",
        "pendingAction",
        "ButtonLoading",
    ),
    "frontend/app/upload/page.tsx": (
        "ButtonLoading",
        "imageUploading",
        "audioUploading",
        "videoUploading",
    ),
    "frontend/components/KnowledgeChat.tsx": (
        "isAsking",
        "isRegenerating",
        "isSavingNote",
        "disabled={!spaceId || !question.trim() || isAsking}",
    ),
    "frontend/app/portfolio/page.tsx": (
        "loadingSummary",
        "exporting",
        "ButtonLoading",
    ),
}


def file_contains(path: str, snippets: tuple[str, ...]) -> list[str]:
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    return [snippet for snippet in snippets if snippet not in text]


def main() -> None:
    failures: list[str] = []
    for path, snippets in REQUIRED_SNIPPETS.items():
        missing = file_contains(path, snippets)
        failures.extend(f"{path} missing interaction feedback snippet: {snippet}" for snippet in missing)

    interactions = analyze()
    high_risk = [item for item in interactions if item.duplicate_click_risk == "high"]
    api_like = [item for item in interactions if item.likely_api_action]

    if len(high_risk) > 12:
        failures.append(f"Too many high-risk async-looking buttons without pending feedback: {len(high_risk)} > 12")

    print("interaction_feedback=checked")
    print(f"buttons={len(interactions)}")
    print(f"api_like_buttons={len(api_like)}")
    print(f"high_risk={len(high_risk)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
