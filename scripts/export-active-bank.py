from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from backend.app.bank_transfer import export_bank
from desktop.runtime_paths import DATABASE_URL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL", DATABASE_URL)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        active = connection.execute(
            """
            SELECT active_bank_id::text AS id
            FROM bank_active_state
            WHERE singleton=TRUE
            """
        ).fetchone()
        if not active or not active["id"]:
            raise SystemExit("ACTIVE_BANK_REQUIRED")
        package = export_bank(connection, active["id"])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "name": package["name"],
                "passages": len(package["passages"]),
                "questions": package["target_size"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
