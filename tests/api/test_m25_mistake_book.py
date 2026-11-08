from __future__ import annotations

import json
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "db" / "migrations" / "002_mistake_book.sql"


def database_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def apply_migration() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    with psycopg.connect(database_url(), autocommit=True) as connection:
        connection.execute(sql)


def test_m25_migration_is_idempotent_and_preserves_existing_rows() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        before = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM practice_sessions) AS sessions,
              (SELECT count(*) FROM saved_answers) AS answers
            """
        ).fetchone()

    apply_migration()
    apply_migration()

    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        after = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM practice_sessions) AS sessions,
              (SELECT count(*) FROM saved_answers) AS answers
            """
        ).fetchone()
        tables = {
            row["table_name"]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='public'
                """
            ).fetchall()
        }
        session_kind = connection.execute(
            """
            SELECT data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='practice_sessions'
              AND column_name='session_kind'
            """
        ).fetchone()

    assert before == after
    assert {
        "question_attempts",
        "mistake_items",
        "report_deletions",
        "bank_switch_log",
    } <= tables
    assert session_kind == {
        "data_type": "character varying",
        "column_default": "'practice'::character varying",
        "is_nullable": "NO",
    }


def test_m25_coverage_tokens_and_openapi_paths_exist() -> None:
    tokens = json.loads(
        (ROOT / "contracts" / "design-tokens.json").read_text(encoding="utf-8")
    )
    assert tokens["color"]["coverage_repeat"] != tokens["color"]["coverage_once"]
    assert tokens["color"]["coverage_once"] != tokens["color"]["coverage_none"]

    openapi = (
        ROOT / "contracts" / "openapi.yaml"
    ).read_text(encoding="utf-8")
    declared_paths = set(
        re.findall(r"(?m)^  (/[^:]+):\s*$", openapi)
    )
    assert {
        "/mistakes",
        "/mistakes/{passage_id}",
        "/mistakes/review/{passage_id}",
        "/stats/coverage",
        "/maintenance/clear-mistakes/preview",
        "/maintenance/clear-mistakes",
        "/maintenance/reset-coverage/preview",
        "/maintenance/reset-coverage",
    } <= declared_paths
