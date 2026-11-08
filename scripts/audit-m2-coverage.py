#!/usr/bin/env python3
"""Audit M2 Bank #2 quotas and coverage against the frozen contract."""

from __future__ import annotations

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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def book_tag(book_source: str) -> str:
    compact = re.sub(r"\s+", "", book_source)
    for prefix in ("选必二", "选必一", "跨册", "必修"):
        if compact.startswith(prefix):
            return prefix
    return ""


def main() -> None:
    quota = load_json(ROOT / "config" / "m2-quota-allocation.json")
    words = [
        item["word"]
        for item in load_json(
            ROOT / "contracts" / "high-frequency-cloze-words.json"
        )["words"]
    ]
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        bank = connection.execute(
            """
            SELECT id::text AS id, name, status
            FROM question_banks
            WHERE name='M2 Bank #2'
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        if not bank:
            raise RuntimeError("M2_BANK_2_NOT_FOUND")
        if bank["status"] != "active":
            raise RuntimeError("M2_BANK_NOT_ACTIVE")
        rows = connection.execute(
            """
            SELECT type, difficulty, book_source, grammar_tags,
                   knowledge_points
            FROM questions
            WHERE bank_id=%s
              AND status='published'
            """,
            (bank["id"],),
        ).fetchall()
    by_type = Counter(row["type"] for row in rows)
    difficulty = Counter(row["difficulty"] for row in rows)
    book = Counter(
        book_tag(row["book_source"])
        for row in rows
        if row["type"] in {"cloze", "grammar_fill"}
    )
    elective_topics = sum(
        book_tag(row["book_source"]) in {"选必一", "选必二"}
        for row in rows
        if row["type"] in {"reading", "gap_fill"}
    )
    cloze_targets = Counter(
        point.split(":", 1)[1]
        for row in rows
        if row["type"] == "cloze"
        for point in row["knowledge_points"]
        if point.startswith("cloze_target:")
    )
    grammar_tags = Counter(
        tag
        for row in rows
        if row["type"] == "grammar_fill"
        for tag in row["grammar_tags"]
    )
    reading_types = Counter(
        point.split(":", 1)[1]
        for row in rows
        if row["type"] == "reading"
        for point in row["knowledge_points"]
        if point.startswith("reading_type:")
    )
    gap_types = Counter(
        point.removeprefix("gap_fill_")
        for row in rows
        if row["type"] == "gap_fill"
        for point in row["knowledge_points"]
        if point.startswith("gap_fill_")
    )
    expected = {
        "types": {
            key: value["questions"]
            for key, value in quota["types"].items()
        },
        "difficulty": {
            int(key): value for key, value in quota["difficulty"].items()
        },
        "book": quota["book_tag_cloze_grammar"],
        "grammar_tags": quota["grammar_tag_targets"],
        "reading_types": quota["reading_subtypes"],
        "gap_types": quota["gap_cohesion_types"],
        "cloze_targets": {word: 2 for word in words},
    }
    actual = {
        "types": dict(by_type),
        "difficulty": dict(difficulty),
        "book": dict(book),
        "elective_topics": elective_topics,
        "grammar_tags": dict(grammar_tags),
        "reading_types": dict(reading_types),
        "gap_types": dict(gap_types),
        "cloze_targets": dict(cloze_targets),
    }
    failures = []
    if len(rows) != 300:
        failures.append("PUBLISHED_COUNT")
    if by_type != Counter(expected["types"]):
        failures.append("TYPE_COUNTS")
    if difficulty != Counter(expected["difficulty"]):
        failures.append("DIFFICULTY")
    if book != Counter(expected["book"]):
        failures.append("BOOK_TAGS")
    if elective_topics < quota["reading_gap_elective_topic_minimum"]:
        failures.append("ELECTIVE_TOPICS")
    if grammar_tags != Counter(expected["grammar_tags"]):
        failures.append("GRAMMAR_TAGS")
    if reading_types != Counter(expected["reading_types"]):
        failures.append("READING_TYPES")
    if gap_types != Counter(expected["gap_types"]):
        failures.append("GAP_TYPES")
    if cloze_targets != Counter(expected["cloze_targets"]):
        failures.append("CLOZE_TARGETS")
    result = {
        "bank": bank,
        "passed": not failures,
        "failures": failures,
        "expected": expected,
        "actual": actual,
    }
    output = ROOT / "qa" / "evidence" / "m2" / "coverage-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
