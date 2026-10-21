from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCLUDED_PARTS = {"archive"}
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
IMAGE_PATTERN = re.compile(r"!\[[^\]\n]*\]\(([^)\n]+)\)")
FENCE_PATTERN = re.compile(r"^```(\w+)?\s*$")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


@dataclass
class LinkCheckResult:
    files_checked: int
    links_checked: int
    images_checked: int
    mermaid_blocks: int
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def iter_markdown_files(include_archive: bool = False) -> list[Path]:
    files = [ROOT / "README.md"]
    for path in sorted((ROOT / "docs").rglob("*.md")):
        relative = path.relative_to(ROOT)
        if not include_archive and any(part in DEFAULT_EXCLUDED_PARTS for part in relative.parts):
            continue
        files.append(path)
    return sorted(dict.fromkeys(files))


def clean_target(raw_target: str) -> str:
    target = raw_target.strip()
    if not target or target.startswith("<"):
        return target
    target = target.split("#", 1)[0].split("?", 1)[0].strip()
    return unquote(target)


def is_external(raw_target: str) -> bool:
    stripped = raw_target.strip().lower()
    return stripped.startswith(EXTERNAL_PREFIXES)


def validate_target(source: Path, raw_target: str, failures: list[str], *, kind: str) -> bool:
    if is_external(raw_target):
        return False
    target = clean_target(raw_target)
    if not target:
        return False
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target_path = (source.parent / target).resolve()
    try:
        target_path.relative_to(ROOT.resolve())
    except ValueError:
        failures.append(f"{source.relative_to(ROOT).as_posix()}: {kind} escapes repository: {raw_target}")
        return True
    if not target_path.exists():
        failures.append(f"{source.relative_to(ROOT).as_posix()}: missing {kind} target: {raw_target}")
    return True


def validate_mermaid(source: Path, text: str, failures: list[str]) -> int:
    mermaid_blocks = 0
    in_fence = False
    in_mermaid = False
    mermaid_has_body = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_PATTERN.match(line)
        if not match:
            if in_mermaid and line.strip():
                mermaid_has_body = True
            continue
        language = (match.group(1) or "").lower()
        if not in_fence:
            in_fence = True
            in_mermaid = language == "mermaid"
            mermaid_has_body = False
            if in_mermaid:
                mermaid_blocks += 1
        else:
            if in_mermaid and not mermaid_has_body:
                failures.append(f"{source.relative_to(ROOT).as_posix()}:{line_number}: empty mermaid block")
            in_fence = False
            in_mermaid = False
            mermaid_has_body = False
    if in_fence:
        failures.append(f"{source.relative_to(ROOT).as_posix()}: unclosed markdown code fence")
    return mermaid_blocks


def check_docs_links(include_archive: bool = False) -> LinkCheckResult:
    failures: list[str] = []
    links_checked = 0
    images_checked = 0
    mermaid_blocks = 0
    files = iter_markdown_files(include_archive=include_archive)
    for path in files:
        text = path.read_text(encoding="utf-8")
        image_targets = IMAGE_PATTERN.findall(text)
        link_targets = LINK_PATTERN.findall(text)
        for target in image_targets:
            if validate_target(path, target, failures, kind="image"):
                images_checked += 1
        for target in link_targets:
            if validate_target(path, target, failures, kind="link"):
                links_checked += 1
        mermaid_blocks += validate_mermaid(path, text, failures)
    return LinkCheckResult(
        files_checked=len(files),
        links_checked=links_checked,
        images_checked=images_checked,
        mermaid_blocks=mermaid_blocks,
        failures=failures,
    )


def print_result(result: LinkCheckResult) -> None:
    print("docs_links=checked")
    print(f"files={result.files_checked}")
    print(f"local_links={result.links_checked}")
    print(f"local_images={result.images_checked}")
    print(f"mermaid_blocks={result.mermaid_blocks}")
    if result.failures:
        print("result=failed")
        for failure in result.failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check README and docs markdown links without calling the network.")
    parser.add_argument("--include-archive", action="store_true", help="Also scan archived historical reports.")
    args = parser.parse_args()
    print_result(check_docs_links(include_archive=args.include_archive))


if __name__ == "__main__":
    main()
