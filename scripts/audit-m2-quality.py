#!/usr/bin/env python3
"""Produce the R1-R10 acceptance report for M2 Bank #2."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.generation import validate_generated_passage  # noqa: E402
from backend.app.question_quality import (  # noqa: E402
    validate_cloze_options,
    validate_reading_question_type,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_runner():
    path = ROOT / "scripts" / "run-m2-full.py"
    spec = importlib.util.spec_from_file_location(
        "audit_m2_full_runner",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("M2_RUNNER_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def rate(passed: int, total: int) -> float:
    return round(passed / total, 6) if total else 1.0


def main() -> None:
    runner = load_runner()
    checkpoint = load_json(
        ROOT / "qa" / "evidence" / "m2" / "run-checkpoint.json"
    )
    records = {
        item["record"]["passage_group_id"]: item["record"]
        for item in checkpoint["records"]
    }
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        bank = connection.execute(
            """
            SELECT id::text AS id, status
            FROM question_banks
            WHERE name='M2 Bank #2'
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        if not bank or bank["status"] != "active":
            raise RuntimeError("M2_BANK_NOT_ACTIVE")
        rows = connection.execute(
            """
            SELECT q.id::text AS id, q.type, q.passage_group_id,
                   p.content AS passage, q.stem, q.options, q.answer,
                   q.explanation, q.knowledge_points, q.grammar_tags,
                   q.book_source, q.difficulty
            FROM questions q
            JOIN passages p
              ON p.bank_id=q.bank_id
             AND p.passage_group_id=q.passage_group_id
            WHERE q.bank_id=%s
              AND q.status='published'
            ORDER BY q.id
            """,
            (bank["id"],),
        ).fetchall()

    counters = {
        "R1": [0, 0],
        "R2": [0, 0],
        "R3": [0, 0],
        "R4": [0, 0],
        "R5": [0, 0],
        "R6": [0, 0],
        "R7": [0, 0],
        "R8": [0, 0],
        "R9": [0, 0],
        "R10": [0, 0],
    }
    failures = []
    if len(rows) != 300:
        failures.append(
            {
                "code": "PUBLISHED_COUNT",
                "expected": 300,
                "actual": len(rows),
            }
        )
    by_group = {}
    for row in rows:
        by_group.setdefault(row["passage_group_id"], []).append(row)

    for row in rows:
        options = row["options"] or []
        answer = str(row["answer"])
        r1 = (
            answer.upper() in set("ABCDEFG")
            if row["type"] == "gap_fill"
            else any(str(option) == answer for option in options)
        )
        counters["R1"][1] += 1
        counters["R1"][0] += int(r1)
        if not r1:
            failures.append({"code": "R1", "question_id": row["id"]})

        if row["type"] == "cloze":
            failures_r2_r3 = validate_cloze_options(
                stem=row["stem"],
                options=options,
                answer=answer,
            )
            r2 = not any(
                item["code"] == "H6_OPTION_SAME_LEMMA"
                for item in failures_r2_r3
            )
            r3 = not any(
                item["code"] == "H7_OPTION_ECHOES_STEM"
                for item in failures_r2_r3
            )
            counters["R2"][1] += 1
            counters["R2"][0] += int(r2)
            counters["R3"][1] += 1
            counters["R3"][0] += int(r3)
            if not r2:
                failures.append({"code": "R2", "question_id": row["id"]})
            if not r3:
                failures.append({"code": "R3", "question_id": row["id"]})

        if row["type"] == "reading":
            r4 = not validate_reading_question_type(row["stem"])
            evidence = next(
                (
                    point.split(":", 1)[1]
                    for point in row["knowledge_points"]
                    if point.startswith("evidence_sentence:")
                ),
                "",
            )
            r5 = bool(evidence) and evidence in row["passage"]
            counters["R4"][1] += 1
            counters["R4"][0] += int(r4)
            counters["R5"][1] += 1
            counters["R5"][0] += int(r5)
            if not r4:
                failures.append({"code": "R4", "question_id": row["id"]})
            if not r5:
                failures.append({"code": "R5", "question_id": row["id"]})

    for group_id, group_rows in by_group.items():
        first = group_rows[0]
        type_ = first["type"]
        record = records[group_id]
        validation = validate_generated_passage(record)
        counters["R6"][1] += 1
        unknown = [
            word
            for word in validation.metrics.get("unknown_words", [])
            if word.casefold().removesuffix("'s")
            not in runner.proper_name_tokens(record["passage"])
        ]
        counters["R6"][0] += int(not unknown)
        if unknown:
            failures.append(
                {
                    "code": "R6",
                    "passage_group_id": group_id,
                    "unknown_words": unknown,
                }
            )
        audit = record.get("pro_audit", {})
        counters["R8"][1] += 1
        counters["R8"][0] += int(audit.get("coherent") is True)
        if audit.get("coherent") is not True:
            failures.append({"code": "R8", "passage_group_id": group_id})
        audit_items = {
            item["question_index"]: item
            for item in audit.get("questions", [])
        }
        for index, question in enumerate(record["questions"], start=1):
            item = audit_items.get(index, {})
            counters["R9"][1] += 1
            r9 = (
                item.get("clear_best") is True
                and str(item.get("best_option", "")).casefold()
                == str(question["answer"]).casefold()
            )
            counters["R9"][0] += int(r9)
            if not r9:
                failures.append(
                    {
                        "code": "R9",
                        "passage_group_id": group_id,
                        "question_index": index,
                    }
                )
            counters["R10"][1] += 1
            r10 = runner.explanation_has_two_distractors(
                question,
                type_,
            )
            counters["R10"][0] += int(r10)
            if not r10:
                failures.append(
                    {
                        "code": "R10",
                        "passage_group_id": group_id,
                        "question_index": index,
                    }
                )

    coverage_path = ROOT / "qa" / "evidence" / "m2" / "coverage-report.json"
    coverage_ok = (
        coverage_path.exists()
        and load_json(coverage_path).get("passed") is True
    )
    counters["R7"] = [int(coverage_ok), 1]
    if not coverage_ok:
        failures.append({"code": "R7"})

    report = {
        "bank": bank,
        "passed": not failures,
        "criteria": {
            code: {
                "passed": value[0],
                "checked": value[1],
                "rate": rate(value[0], value[1]),
            }
            for code, value in counters.items()
        },
        "failures": failures,
    }
    output = ROOT / "qa" / "evidence" / "m2" / "quality-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
