#!/usr/bin/env python3
"""Publish the three audited M2 gap-fill replacements."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "M2-FULL-GAP-05",
    "M2-FULL-GAP-06",
    "M2-FULL-GAP-07",
}
REPAIR_BATCH = "M2-GAP-OPTION-REPAIR"
EVIDENCE = ROOT / "qa" / "evidence" / "m2" / "bank2-lifecycle-repair.json"


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def main() -> None:
    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        bank = connection.execute(
            """
            SELECT qb.id::text AS id, qb.name, qb.status
            FROM bank_active_state bas
            JOIN question_banks qb ON qb.id=bas.active_bank_id
            """
        ).fetchone()
        if not bank or bank["name"] != "M2 Bank #2":
            raise RuntimeError("ACTIVE_BANK_NOT_M2")
        if bank["status"] != "active":
            raise RuntimeError("M2_BANK_NOT_ACTIVE")

        rows = connection.execute(
            """
            SELECT id, passage_group_id, type, options, answer, status, batch_id
            FROM questions
            WHERE bank_id=%s
              AND passage_group_id = ANY(%s)
            ORDER BY id
            FOR UPDATE
            """,
            (bank["id"], sorted(TARGETS)),
        ).fetchall()
        if len(rows) != 15:
            raise RuntimeError(f"REPAIR_ROW_COUNT_INVALID:{len(rows)}")

        group_counts = Counter(row["passage_group_id"] for row in rows)
        if group_counts != Counter({group_id: 5 for group_id in TARGETS}):
            raise RuntimeError(f"REPAIR_GROUP_COUNTS_INVALID:{group_counts}")
        for row in rows:
            if row["type"] != "gap_fill":
                raise RuntimeError(f"REPAIR_TYPE_INVALID:{row['id']}")
            if row["batch_id"] != REPAIR_BATCH:
                raise RuntimeError(f"REPAIR_BATCH_INVALID:{row['id']}")
            if row["status"] not in {"draft", "published"}:
                raise RuntimeError(f"REPAIR_STATUS_INVALID:{row['id']}")
            options = row["options"] or []
            if (
                len(options) != 7
                or str(row["answer"]).upper() not in set("ABCDEFG")
                or any(
                    not isinstance(option, str)
                    or not option.strip()
                    or option.rstrip()[-1:] not in ".?!"
                    for option in options
                )
            ):
                raise RuntimeError(f"REPAIR_OPTIONS_INVALID:{row['id']}")

        updated = connection.execute(
            """
            UPDATE questions
            SET status='published', updated_at=now()
            WHERE bank_id=%s
              AND passage_group_id = ANY(%s)
              AND batch_id=%s
              AND status='draft'
            RETURNING id
            """,
            (bank["id"], sorted(TARGETS), REPAIR_BATCH),
        ).fetchall()

        counts = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM passages
               WHERE bank_id=%s AND status='published') AS passages,
              (SELECT count(*) FROM questions
               WHERE bank_id=%s AND status='published') AS questions,
              (SELECT count(*) FROM questions
               WHERE bank_id=%s AND status='draft') AS draft_questions
            """,
            (bank["id"], bank["id"], bank["id"]),
        ).fetchone()
        if counts != {
            "passages": 47,
            "questions": 300,
            "draft_questions": 0,
        }:
            raise RuntimeError(f"BANK_PUBLISHED_COUNTS_INVALID:{counts}")
        connection.commit()

    evidence = {
        "status": "passed",
        "bank": bank,
        "repair_batch": REPAIR_BATCH,
        "passage_group_ids": sorted(TARGETS),
        "published_question_ids": sorted(row["id"] for row in updated),
        "published_this_run": len(updated),
        "published_counts": counts,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
