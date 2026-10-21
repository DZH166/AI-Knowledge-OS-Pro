from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterator

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402


class MigrationPreflightError(RuntimeError):
    pass


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _sqlite_path(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise MigrationPreflightError(
            "V5 migration CLI intentionally supports SQLite only; no external database was contacted."
        )
    database = url.database
    if not database or database == ":memory:":
        raise MigrationPreflightError("V5 migration CLI requires a file-backed SQLite database.")
    path = Path(database).expanduser().resolve()
    if not path.is_file():
        raise MigrationPreflightError(f"SQLite database does not exist: {path}")
    return path


@contextmanager
def _read_only_connection(database_url: str) -> Iterator[sqlite3.Connection]:
    path = _sqlite_path(database_url)
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    }


def _count(connection: sqlite3.Connection, table_name: str) -> int | None:
    if table_name not in _table_names(connection):
        return None
    # All names are hard-coded call-site constants, never user input.
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])


def inspect_database(database_url: str) -> dict[str, Any]:
    config = _alembic_config(database_url)
    script = ScriptDirectory.from_config(config)
    heads = sorted(script.get_heads())
    known_revisions = {revision.revision for revision in script.walk_revisions()}

    with _read_only_connection(database_url) as connection:
        tables = _table_names(connection)
        current_revisions = (
            sorted(str(row[0]) for row in connection.execute("SELECT version_num FROM alembic_version"))
            if "alembic_version" in tables
            else []
        )
        counts = {
            table_name: _count(connection, table_name)
            for table_name in (
                "knowledge_spaces",
                "documents",
                "chunks",
                "sources",
                "source_revisions",
                "multimodal_chunks",
                "index_revisions",
                "index_operations",
                "vector_point_manifests",
                "outbox_messages",
                "agent_runs",
            )
        }

    errors: list[str] = []
    if len(heads) != 1:
        errors.append(f"Expected one Alembic head, found {heads!r}.")
    if len(current_revisions) > 1:
        errors.append(f"Database has multiple current revisions: {current_revisions!r}.")
    unknown = [revision for revision in current_revisions if revision not in known_revisions]
    if unknown:
        errors.append(f"Database contains unknown Alembic revisions: {unknown!r}.")

    target = heads[0] if len(heads) == 1 else None
    return {
        "database_path": str(_sqlite_path(database_url)),
        "heads": heads,
        "single_head": len(heads) == 1,
        "target_revision": target,
        "current_revisions": current_revisions,
        "at_head": bool(target and current_revisions == [target]),
        "table_counts": counts,
        "errors": errors,
    }


def run(*, database_url: str, apply: bool = False) -> dict[str, Any]:
    before = inspect_database(database_url)
    if before["errors"]:
        raise MigrationPreflightError("; ".join(before["errors"]))

    should_upgrade = not before["at_head"]
    if apply and should_upgrade:
        # env.py reads the shared settings object, so keep it aligned with the
        # explicit CLI target. No provider, Redis, or Qdrant object is created.
        previous_database_url = settings.database_url
        settings.database_url = database_url
        try:
            command.upgrade(_alembic_config(database_url), "head")
        finally:
            settings.database_url = previous_database_url
        after = inspect_database(database_url)
        if not after["at_head"]:
            raise MigrationPreflightError(
                f"Alembic upgrade did not reach the single head: {after['current_revisions']!r}."
            )
    else:
        after = before

    return {
        "mode": "apply" if apply else "dry-run",
        "changed": bool(apply and should_upgrade),
        "planned_action": "upgrade_to_head" if should_upgrade else "none",
        "external_access": False,
        "before": before,
        "after": after,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight or apply the offline V5 SQL evidence migration. "
            "Dry-run is the default and never contacts Qdrant, Redis, or providers."
        )
    )
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--apply", action="store_true", help="Apply Alembic upgrade to the single head.")
    args = parser.parse_args(argv)
    try:
        report = run(database_url=args.database_url, apply=args.apply)
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
