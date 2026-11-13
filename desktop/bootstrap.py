from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from desktop.runtime_paths import (
    DATABASE_NAME,
    DATABASE_PORT,
    DATABASE_URL,
    RuntimePaths,
    migration_files,
    needs_database_initialization,
    resolve_runtime_paths,
)


CREATE_NO_WINDOW = 0x08000000


def _log(message: str) -> None:
    print(message, flush=True)


def _run(
    command: list[str | Path],
    *,
    cwd: Path,
    log_path: Path,
    check: bool = True,
) -> subprocess.CompletedProcess:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = [str(item) for item in command]
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n$ " + " ".join(rendered) + "\n")
        log.flush()
        completed = subprocess.run(
            rendered,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"COMMAND_FAILED:{completed.returncode}:{rendered[0]}"
        )
    return completed


def _pg_status(paths: RuntimePaths) -> bool:
    result = _run(
        [
            paths.pgsql_exe("pg_ctl.exe"),
            "-D",
            paths.pgdata,
            "status",
        ],
        cwd=paths.app_root,
        log_path=paths.logs / "postgres.log",
        check=False,
    )
    return result.returncode == 0


def _pg_ready(paths: RuntimePaths) -> bool:
    result = _run(
        [
            paths.pgsql_exe("pg_isready.exe"),
            "-h",
            "127.0.0.1",
            "-p",
            str(DATABASE_PORT),
        ],
        cwd=paths.app_root,
        log_path=paths.logs / "postgres.log",
        check=False,
    )
    return result.returncode == 0


def _ensure_postgres(paths: RuntimePaths) -> None:
    paths.pgdata.parent.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)
    if needs_database_initialization(paths.pgdata):
        if paths.pgdata.exists() and any(paths.pgdata.iterdir()):
            raise RuntimeError("PGDATA_NOT_EMPTY_WITHOUT_PG_VERSION")
        _log("Initializing PostgreSQL data directory")
        _run(
            [
                paths.pgsql_exe("initdb.exe"),
                "-D",
                paths.pgdata,
                "-U",
                "postgres",
                "--encoding=UTF8",
                "--locale=C",
                "--auth=trust",
            ],
            cwd=paths.app_root,
            log_path=paths.logs / "postgres.log",
        )

    owned_server_running = _pg_status(paths)
    if not owned_server_running:
        if _pg_ready(paths):
            raise RuntimeError("POSTGRES_PORT_CONFLICT:15432")
        _log("Starting PostgreSQL")
        _run(
            [
                paths.pgsql_exe("pg_ctl.exe"),
                "-D",
                paths.pgdata,
                "-l",
                paths.logs / "postgres-server.log",
                "-o",
                f"-p {DATABASE_PORT}",
                "-w",
                "-t",
                "30",
                "start",
            ],
            cwd=paths.app_root,
            log_path=paths.logs / "postgres.log",
        )

def _psql(paths: RuntimePaths, *arguments: str, database: str = DATABASE_NAME) -> None:
    _run(
        [
            paths.pgsql_exe("psql.exe"),
            "-h",
            "127.0.0.1",
            "-p",
            str(DATABASE_PORT),
            "-U",
            "postgres",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            *arguments,
        ],
        cwd=paths.app_root,
        log_path=paths.logs / "postgres.log",
    )


def _ensure_database_and_migrations(paths: RuntimePaths) -> None:
    with psycopg.connect(
        f"postgresql://postgres@127.0.0.1:{DATABASE_PORT}/postgres",
        autocommit=True,
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s",
            (DATABASE_NAME,),
        ).fetchone()
        if not exists:
            connection.execute(f'CREATE DATABASE "{DATABASE_NAME}"')

    _psql(
        paths,
        "-c",
        """
        CREATE TABLE IF NOT EXISTS desktop_schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
    )
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT filename FROM desktop_schema_migrations"
            ).fetchall()
        }
    for migration in migration_files(paths.migrations_dir):
        if migration.name in applied:
            continue
        _log(f"Applying migration {migration.name}")
        _psql(paths, "-f", str(migration))
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(
                "INSERT INTO desktop_schema_migrations (filename) VALUES (%s)",
                (migration.name,),
            )


def _seed_if_needed(paths: RuntimePaths) -> dict | None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        active = connection.execute(
            """
            SELECT active_bank_id::text AS id
            FROM bank_active_state
            WHERE singleton=TRUE
            """
        ).fetchone()
    if active and active[0]:
        return None
    if not paths.seed_file.is_file():
        raise RuntimeError("BANK_SEED_MISSING")
    from backend.app.bank_transfer import import_bank

    package = json.loads(paths.seed_file.read_text(encoding="utf-8"))
    with psycopg.connect(DATABASE_URL, autocommit=False) as connection:
        result = import_bank(
            connection,
            package,
            strict_validation=False,
        )
        connection.commit()
    _log(
        "Imported seed bank "
        f"{result['summary']['questions']} questions / "
        f"{result['summary']['passages']} passages"
    )
    return result


def ensure_database(paths: RuntimePaths | None = None) -> dict:
    resolved = paths or resolve_runtime_paths()
    resolved.data_root.mkdir(parents=True, exist_ok=True)
    resolved.logs.mkdir(parents=True, exist_ok=True)
    resolved.runtime.mkdir(parents=True, exist_ok=True)
    _ensure_postgres(resolved)
    _ensure_database_and_migrations(resolved)
    seeded = _seed_if_needed(resolved)
    return {
        "database_url": DATABASE_URL,
        "pgdata": str(resolved.pgdata),
        "seeded": seeded,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root")
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    environment = os.environ.copy()
    if args.data_dir:
        environment["GAOER_ENGLISH_DATA_DIR"] = args.data_dir
    paths = resolve_runtime_paths(args.app_root, environment)
    print(json.dumps(ensure_database(paths), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
