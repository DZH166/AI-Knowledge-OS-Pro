import sqlite3
import subprocess
import sys

from scripts import release
from scripts.check_demo_ready import REQUIRED_TABLE_COUNTS
from scripts.reset_demo_data import DEFAULT_DATABASE, ensure_demo_database_path
from scripts.seed_demo_data import main as seed_demo_main


def test_release_dry_run_analysis_uses_tracked_sources_and_blocks_risky_paths() -> None:
    analysis = release.analyze_release()
    included = {path.relative_to(release.ROOT).as_posix() for path in analysis.included}

    assert "README.md" in included
    assert "scripts/release.py" in included
    assert all(not name.startswith("sub2api/") for name in included)
    assert release.should_exclude(release.ROOT / ".env.production")
    assert release.should_exclude(release.ROOT / "qdrant_storage" / "collection" / "data.bin")
    assert release.should_exclude(release.ROOT / "media_cache" / "frame.png")
    assert not analysis.has_secret
    assert not analysis.has_database
    assert not analysis.has_upload
    assert not analysis.has_cache


def test_secret_and_repo_clean_checks_pass_on_tracked_files() -> None:
    commands = [
        [sys.executable, "scripts/check_secrets.py"],
        [sys.executable, "scripts/check_repo_clean.py"],
        [sys.executable, "scripts/release.py", "--version", "V3.8", "--dry-run"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=release.ROOT, text=True, capture_output=True, check=True)
        assert "passed" in completed.stdout.lower()


def test_demo_seed_creates_required_synthetic_records(tmp_path, monkeypatch) -> None:
    database = tmp_path / "demo_showcase.db"
    monkeypatch.setattr(sys, "argv", ["seed_demo_data.py", "--database-path", str(database), "--reset"])
    seed_demo_main()

    assert database.exists()
    with sqlite3.connect(database) as connection:
        counts = {
            table: int(connection.execute(f"select count(*) from {table}").fetchone()[0])
            for table in REQUIRED_TABLE_COUNTS
        }

    assert counts["knowledge_spaces"] >= 1
    assert counts["documents"] >= 1
    assert counts["sources"] >= 3
    assert counts["ingestion_jobs"] >= 3
    assert counts["qa_logs"] >= 1
    assert counts["learning_cards"] >= 1
    assert counts["learning_logs"] >= 1


def test_demo_reset_refuses_non_demo_database(tmp_path) -> None:
    assert ensure_demo_database_path(DEFAULT_DATABASE) == DEFAULT_DATABASE.resolve()

    unsafe_database = tmp_path / "user_data.db"
    try:
        ensure_demo_database_path(unsafe_database)
    except SystemExit as exc:
        assert "outside backend/data" in str(exc)
    else:
        raise AssertionError("reset_demo_data accepted a non-demo database path")


def test_learning_package_generator_can_write_markdown(tmp_path) -> None:
    output = tmp_path / "v3_8_learning_package_draft.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/generate_learning_package.py",
            "--version",
            "V3.8",
            "--goal",
            "GitHub portfolio demo docs and reset workflow",
            "--output",
            str(output),
        ],
        cwd=release.ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert str(output) in completed.stdout
    markdown = output.read_text(encoding="utf-8")
    assert "## V3.8 Learning Package Draft" in markdown
    assert "GitHub portfolio demo docs and reset workflow" in markdown
