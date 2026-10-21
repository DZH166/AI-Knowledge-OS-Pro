from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "screenshots"
DEFAULT_BROWSER_PATHS = (
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
)
ROUTES = {
    "dashboard.png": ("/dashboard", "V4.4: demo E2E contracts, citation jumps and runtime observability"),
    "upload-center.png": ("/upload", "Upload Center"),
    "knowledge-chat.png": ("/chat", "How does the system keep multimodal RAG answers traceable?"),
    "media-library.png": ("/media", "Multimodal RAG Walkthrough"),
    "video-detail.png": ("/media/sources/3?t=6", "Video transcript timeline"),
    "learning-archive.png": ("/learning", "Version Timeline"),
    "task-center.png": ("/tasks", "Full video pipeline"),
}


def default_browser() -> Path:
    for path in DEFAULT_BROWSER_PATHS:
        if path.exists():
            return path
    raise SystemExit("Chrome or Microsoft Edge was not found; pass --browser-path.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture synthetic V4.4 GitHub showcase screenshots.")
    parser.add_argument("--base-url", default="http://127.0.0.1:3010")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--browser-path", type=Path, default=default_browser())
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(args.browser_path))
        context = browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        page = context.new_page()
        for filename, (route, ready_text) in ROUTES.items():
            response = page.goto(f"{args.base_url.rstrip('/')}{route}", wait_until="domcontentloaded", timeout=45_000)
            if response is None or not response.ok:
                status = response.status if response else "no response"
                raise RuntimeError(f"Failed to load {route}: {status}")
            page.wait_for_selector("h1", timeout=30_000)
            page.get_by_text(ready_text, exact=False).first.wait_for(state="visible", timeout=30_000)
            page.wait_for_timeout(750)
            if filename == "video-detail.png":
                heading = page.get_by_role("heading", name="Keyframe timeline")
                box = heading.bounding_box()
                if box is None:
                    raise RuntimeError("Video keyframe timeline is not visible.")
                page.evaluate("position => window.scrollTo(0, position)", page.evaluate("window.scrollY") + box["y"] - 112)
                page.wait_for_timeout(500)
            if "Failed to fetch" in page.locator("body").inner_text():
                raise RuntimeError(f"Page {route} contains a failed API request.")
            page.add_style_tag(content="nextjs-portal { display: none !important; }")
            output_path = args.output / filename
            page.screenshot(path=str(output_path), full_page=False)
            with Image.open(output_path) as screenshot:
                variance = sum(ImageStat.Stat(screenshot.convert("RGB")).var)
            if variance < 20:
                raise RuntimeError(f"Screenshot {filename} is blank or has insufficient visual content.")
            print(f"captured={output_path.relative_to(ROOT).as_posix()}")
        browser.close()


if __name__ == "__main__":
    main()
