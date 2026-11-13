from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


APP_NAME = "GaoerEnglishPractice"
DATABASE_URL = (
    "postgresql://postgres@127.0.0.1:15432/english_practice"
)
DATABASE_PORT = 15432
DATABASE_NAME = "english_practice"
API_PORT = 8000
WEB_PORT = 8081


@dataclass(frozen=True)
class RuntimePaths:
    app_root: Path
    data_root: Path

    @property
    def pgdata(self) -> Path:
        return self.data_root / "pgdata"

    @property
    def logs(self) -> Path:
        return self.data_root / "logs"

    @property
    def runtime(self) -> Path:
        return self.data_root / "runtime"

    @property
    def web_root(self) -> Path:
        return self.app_root / "web"

    @property
    def migrations_dir(self) -> Path:
        return self.app_root / "db" / "migrations"

    @property
    def seed_file(self) -> Path:
        return self.app_root / "seed" / "bank.json"

    @property
    def python_root(self) -> Path:
        return self.app_root / "runtime" / "python"

    @property
    def python_exe(self) -> Path:
        return self.python_root / "python.exe"

    @property
    def pythonw_exe(self) -> Path:
        return self.python_root / "pythonw.exe"

    @property
    def pgsql_root(self) -> Path:
        return self.app_root / "runtime" / "pgsql"

    def pgsql_exe(self, name: str) -> Path:
        return self.pgsql_root / "bin" / name


def resolve_runtime_paths(
    app_root: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> RuntimePaths:
    root = (
        Path(app_root)
        if app_root is not None
        else Path(__file__).resolve().parents[1]
    ).resolve()
    env = os.environ if environment is None else environment
    override = env.get("GAOER_ENGLISH_DATA_DIR")
    if override:
        data_root = Path(override).expanduser().resolve()
    else:
        local_app_data = env.get("LOCALAPPDATA")
        base = (
            Path(local_app_data)
            if local_app_data
            else root
        )
        data_root = (base / APP_NAME / "data").resolve()
    return RuntimePaths(app_root=root, data_root=data_root)


def migration_files(migrations_dir: str | Path) -> list[Path]:
    return sorted(
        path
        for path in Path(migrations_dir).glob("*.sql")
        if path.is_file()
    )


def needs_database_initialization(pgdata: str | Path) -> bool:
    return not (Path(pgdata) / "PG_VERSION").is_file()
