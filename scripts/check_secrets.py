from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml", ".ini", ".txt", ".example"}
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?(?!<|your-|example|demo|fake|not_configured|$)[A-Za-z0-9_\-]{24,}"),
)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / item for item in output.decode("utf-8").split("\0") if item]


def should_scan(path: Path) -> bool:
    if path.name.endswith(".example"):
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def main() -> None:
    findings: list[str] = []
    scanned = 0
    for path in tracked_files():
        if not path.is_file() or not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(path.relative_to(ROOT).as_posix())
                break

    if findings:
        print("Potential secrets found in tracked files:")
        for item in findings:
            print(f"- {item}")
        raise SystemExit(1)
    print(f"Secret check passed: scanned={scanned} findings=0")


if __name__ == "__main__":
    main()
