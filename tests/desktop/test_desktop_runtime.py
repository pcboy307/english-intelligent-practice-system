from __future__ import annotations

from pathlib import Path

from desktop.runtime_paths import (
    DATABASE_URL,
    migration_files,
    needs_database_initialization,
    resolve_runtime_paths,
)
from desktop.static_server import resolve_static_path


def test_default_paths_use_local_app_data_and_external_data_directory(
    tmp_path: Path,
) -> None:
    paths = resolve_runtime_paths(
        tmp_path / "app",
        {"LOCALAPPDATA": str(tmp_path / "local")},
    )

    assert paths.app_root == tmp_path / "app"
    assert paths.data_root == (
        tmp_path / "local" / "GaoerEnglishPractice" / "data"
    )
    assert paths.pgdata == paths.data_root / "pgdata"
    assert paths.python_exe == paths.app_root / "runtime" / "python" / "python.exe"
    assert paths.pythonw_exe == paths.app_root / "runtime" / "python" / "pythonw.exe"
    assert paths.pgsql_exe("pg_ctl.exe") == (
        paths.app_root / "runtime" / "pgsql" / "bin" / "pg_ctl.exe"
    )


def test_data_directory_override_changes_only_data_paths(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    override = tmp_path / "portable-data"

    paths = resolve_runtime_paths(
        app_root,
        {
            "LOCALAPPDATA": str(tmp_path / "ignored"),
            "GAOER_ENGLISH_DATA_DIR": str(override),
        },
    )

    assert paths.app_root == app_root
    assert paths.data_root == override
    assert paths.web_root == app_root / "web"


def test_database_url_is_fixed_to_runtime_contract() -> None:
    assert DATABASE_URL == (
        "postgresql://postgres@127.0.0.1:15432/english_practice"
    )


def test_migration_files_are_ordered_and_limited_to_sql(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (migrations / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations / "README.md").write_text("ignored", encoding="utf-8")

    assert [path.name for path in migration_files(migrations)] == [
        "001_first.sql",
        "002_second.sql",
    ]


def test_database_initialization_requires_pg_version_file(tmp_path: Path) -> None:
    pgdata = tmp_path / "pgdata"
    assert needs_database_initialization(pgdata) is True

    pgdata.mkdir()
    assert needs_database_initialization(pgdata) is True

    (pgdata / "PG_VERSION").write_text("16\n", encoding="utf-8")
    assert needs_database_initialization(pgdata) is False


def test_spa_static_resolution_falls_back_only_for_frontend_routes(
    tmp_path: Path,
) -> None:
    web_root = tmp_path / "web"
    (web_root / "assets").mkdir(parents=True)
    (web_root / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_root / "assets" / "app.js").write_text("app", encoding="utf-8")

    assert resolve_static_path(web_root, "/") == web_root / "index.html"
    assert resolve_static_path(web_root, "/practice") == web_root / "index.html"
    assert (
        resolve_static_path(web_root, "/assets/app.js")
        == web_root / "assets" / "app.js"
    )
    assert resolve_static_path(web_root, "/assets/missing.js") is None
    assert resolve_static_path(web_root, "/../../outside.txt") is None
