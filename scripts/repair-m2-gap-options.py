#!/usr/bin/env python3
"""Replace M2 gap-fill passages whose seven choices are not full sentences."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_runner():
    path = ROOT / "scripts" / "run-m2-full.py"
    spec = importlib.util.spec_from_file_location("m2_full_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("M2_RUNNER_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    runner = load_runner()
    schedule = runner.load_json(runner.SCHEDULE_PATH)
    specs = {
        item["passage_group_id"]: item
        for item in schedule["passages"]
        if item["type"] == "gap_fill"
    }
    targets = [
        "M2-FULL-GAP-05",
        "M2-FULL-GAP-06",
        "M2-FULL-GAP-07",
    ]
    checkpoint_path = ROOT / "qa" / "evidence" / "m2" / "run-checkpoint.json"
    checkpoint = runner.load_json(checkpoint_path)
    by_group = {
        item["record"]["passage_group_id"]: item
        for item in checkpoint["records"]
    }
    with psycopg.connect(
        runner.database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        bank = connection.execute(
            """
            SELECT id::text AS id
            FROM question_banks
            WHERE name='M2 Bank #2'
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        repository = runner.M2Repository(connection)
        for index, group_id in enumerate(targets, start=1):
            result = runner.run_one(specs[group_id], index=index)
            record = result["record"]
            repository.replace_passage_questions(
                bank_id=bank["id"],
                batch_id="M2-GAP-OPTION-REPAIR",
                record=record,
            )
            by_group[group_id] = result
        connection.commit()
    checkpoint["records"] = sorted(
        by_group.values(),
        key=lambda item: item["index"],
    )
    checkpoint["failures"] = [
        item
        for item in checkpoint.get("failures", [])
        if item.get("passage_group_id") not in targets
    ]
    checkpoint_path.write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"replaced": targets}, ensure_ascii=False))


if __name__ == "__main__":
    main()
