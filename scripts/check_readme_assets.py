from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SCREENSHOTS = ROOT / "docs" / "assets" / "screenshots"
DEMO_ASSETS = ROOT / "docs" / "assets" / "demo"
IMAGE_PATTERN = re.compile(r"!\[[^\]\n]*\]\(([^)\n]+)\)")
LOCAL_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
REQUIRED_SCREENSHOTS = {
    "dashboard.png",
    "upload-center.png",
    "knowledge-chat.png",
    "media-library.png",
    "video-detail.png",
    "learning-archive.png",
    "task-center.png",
}


@dataclass
class ReadmeAssetResult:
    local_images: int
    external_images: int
    screenshots_found: int
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def is_external(target: str) -> bool:
    return target.lower().startswith(("http://", "https://"))


def target_without_anchor(target: str) -> str:
    return target.strip().split("#", 1)[0].split("?", 1)[0]


def check_readme_assets() -> ReadmeAssetResult:
    failures: list[str] = []
    text = README.read_text(encoding="utf-8")
    local_images = 0
    external_images = 0

    for raw_target in IMAGE_PATTERN.findall(text):
        target = target_without_anchor(raw_target)
        if is_external(target):
            external_images += 1
            continue
        path = (README.parent / target).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError:
            failures.append(f"README image escapes repository: {raw_target}")
            continue
        if path.suffix.lower() not in LOCAL_IMAGE_SUFFIXES:
            failures.append(f"README image has unexpected extension: {raw_target}")
        if not path.exists():
            failures.append(f"README image is missing: {raw_target}")
        local_images += 1

    for screenshot in sorted(REQUIRED_SCREENSHOTS):
        path = SCREENSHOTS / screenshot
        if not path.exists():
            failures.append(f"Required screenshot placeholder/file is missing: docs/assets/screenshots/{screenshot}")

    missing_demo_gifs = [
        target
        for target in re.findall(r"docs/assets/demo/[^`\s)]+\.gif", text)
        if f"![" in text[max(0, text.find(target) - 20) : text.find(target)]
        and not (ROOT / target).exists()
    ]
    for target in missing_demo_gifs:
        failures.append(f"README embeds a missing demo GIF: {target}")

    if "docs/assets/demo/v4_5_demo_walkthrough.gif" in text and not (DEMO_ASSETS / "v4_5_demo_walkthrough.gif").exists():
        if "![Demo" in text or "![AI Knowledge OS Pro Demo" in text:
            failures.append("README embeds v4_5_demo_walkthrough.gif before the file exists.")

    return ReadmeAssetResult(
        local_images=local_images,
        external_images=external_images,
        screenshots_found=sum(1 for item in REQUIRED_SCREENSHOTS if (SCREENSHOTS / item).exists()),
        failures=failures,
    )


def main() -> None:
    result = check_readme_assets()
    print("readme_assets=checked")
    print(f"local_images={result.local_images}")
    print(f"external_images={result.external_images}")
    print(f"screenshots_found={result.screenshots_found}")
    if result.failures:
        print("result=failed")
        for failure in result.failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
