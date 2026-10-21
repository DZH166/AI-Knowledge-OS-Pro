import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SAFE_COMMAND = (
    "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check "
    "--compare-latest --write-index --write-plan --fail-on-regression"
)


def repo_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_manifest_dir() -> Path:
    base = ROOT / ".pytest_tmp" / "self_check_manifest_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base


def base_artifacts(base: Path, *, mode: str = "quick") -> list[dict[str, object]]:
    quality_json = base / f"check_all_{mode}.json"
    quality_summary = base / f"check_all_{mode}_summary.md"
    quality_json.write_text(json.dumps({"mode": mode, "status": "passed"}), encoding="utf-8")
    quality_summary.write_text("# Summary", encoding="utf-8")
    return [
        {"name": "quality_json", "path": repo_path(quality_json), "exists": True},
        {"name": "quality_summary", "path": repo_path(quality_summary), "exists": True},
        {"name": "comparison_json", "path": repo_path(base / "missing_comparison.json"), "exists": False},
    ]


def write_manifest(
    base: Path,
    artifacts: list[dict[str, object]],
    *,
    mode: str = "quick",
    next_command: dict[str, str] | None = None,
) -> Path:
    manifest = base / "self_check_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "passed",
                "mode": mode,
                "compare_state": "latest",
                "artifact_count": len(artifacts),
                "artifacts": artifacts,
                "next_command": next_command
                or {
                    "priority": "P2",
                    "title": "Add a comparison baseline",
                    "command": SAFE_COMMAND,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


def run_validator(manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/check_self_check_manifest.py", "--manifest-json", str(manifest)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_self_check_manifest_validator_accepts_valid_manifest() -> None:
    base = build_manifest_dir()
    manifest = write_manifest(base, base_artifacts(base))

    completed = run_validator(manifest)

    assert completed.returncode == 0
    assert "self_check_manifest=checked" in completed.stdout
    assert "failures=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_self_check_manifest_validator_accepts_full_manifest() -> None:
    base = build_manifest_dir()
    manifest = write_manifest(
        base,
        base_artifacts(base, mode="full"),
        mode="full",
        next_command={
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": (
                "python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full "
                "--compare-latest --write-index --write-plan --fail-on-regression"
            ),
        },
    )

    completed = run_validator(manifest)

    assert completed.returncode == 0
    assert "failures=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_self_check_manifest_validator_rejects_artifact_path_outside_pytest_tmp() -> None:
    base = build_manifest_dir()
    artifacts = base_artifacts(base)
    artifacts.append({"name": "unsafe_path", "path": "docs/check_all_quick.json", "exists": False})
    manifest = write_manifest(base, artifacts)

    completed = run_validator(manifest)

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "Artifact unsafe_path has invalid path" in completed.stdout


def test_self_check_manifest_validator_rejects_declared_exists_mismatch() -> None:
    base = build_manifest_dir()
    artifacts = base_artifacts(base)
    missing = base / "declared_existing.json"
    artifacts.append({"name": "declared_existing", "path": repo_path(missing), "exists": True})
    manifest = write_manifest(base, artifacts)

    completed = run_validator(manifest)

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "filesystem existence is False" in completed.stdout


def test_self_check_manifest_validator_rejects_unsafe_next_command() -> None:
    base = build_manifest_dir()
    manifest = write_manifest(
        base,
        base_artifacts(base),
        next_command={
            "priority": "P0",
            "title": "Unsafe command",
            "command": "python scripts/seed_demo_data.py --reset",
        },
    )

    completed = run_validator(manifest)

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "next_command.command is unsafe" in completed.stdout
