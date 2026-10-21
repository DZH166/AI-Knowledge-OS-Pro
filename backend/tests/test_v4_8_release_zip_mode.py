import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v4_8_release_safety_scripts_work_without_git_metadata(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copyfile(ROOT / "scripts" / "check_secrets.py", scripts_dir / "check_secrets.py")
    shutil.copyfile(ROOT / "scripts" / "check_repo_clean.py", scripts_dir / "check_repo_clean.py")
    (tmp_path / "README.md").write_text("# extracted source\nNo secrets here.\n", encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text('{"version":"4.8.0"}\n', encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "data").mkdir()
    (tmp_path / "backend" / "data" / "demo.db").write_text("ignored demo database", encoding="utf-8")
    (tmp_path / "releases").mkdir()
    (tmp_path / "releases" / "old.zip").write_text("ignored release archive", encoding="utf-8")

    for script in ("check_secrets.py", "check_repo_clean.py"):
        completed = subprocess.run(
            [sys.executable, f"scripts/{script}"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=True,
        )
        assert "mode=filesystem" in completed.stdout
        assert "reason=no_git_metadata" in completed.stdout
        assert "Traceback" not in completed.stderr
