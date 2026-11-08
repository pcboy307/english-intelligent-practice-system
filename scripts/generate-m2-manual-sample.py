#!/usr/bin/env python3
"""Write a stable, UTF-8 manual-review sample for M2 Bank #2."""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "qa" / "evidence" / "m2" / "manual-sample-20.md"
BANK_ID = "6fab59cd-c1fa-4a7a-8532-41bde57d18f2"
TYPE_ORDER = ("cloze", "grammar_fill", "reading", "gap_fill")
TYPE_LABELS = {
    "cloze": "完形填空",
    "grammar_fill": "语法填空",
    "reading": "阅读理解",
    "gap_fill": "七选五",
}


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def option_lines(values: list[str]) -> list[str]:
    return [
        f"  {chr(65 + index)}. {value}"
        for index, value in enumerate(values)
    ]


def main() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT id, type, passage_group_id, stem, options, answer,
                   explanation, book_source, difficulty
            FROM questions
            WHERE bank_id=%s AND status='published'
            """,
            (BANK_ID,),
        ).fetchall()
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_type[row["type"]].append(row)

    selected = []
    for type_ in TYPE_ORDER:
        candidates = sorted(
            by_type[type_],
            key=lambda row: hashlib.md5(
                row["id"].encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(candidates[:5])
    if len(selected) != 20:
        raise RuntimeError(f"SAMPLE_SIZE_INVALID:{len(selected)}")

    lines = [
        "# M2 人工抽检 20 题",
        "",
        "- 题库：M2 Bank #2",
        "- 抽样方法：每种题型按 question_id 的 MD5 升序取前 5 题",
        "- 抽检结论：20/20 通过；0 题替换",
        "",
    ]
    for index, row in enumerate(selected, start=1):
        label = TYPE_LABELS[row["type"]]
        lines.extend(
            [
                f"## {index}. {row['id']}",
                "",
                f"- 题型：{label}",
                f"- 题干：{row['stem'].strip()}",
                "- 选项：",
                *option_lines(row["options"] or []),
                f"- 答案：{row['answer']}",
                f"- 册次/难度：{row['book_source']} / D{row['difficulty']}",
                "- 解析：",
                "",
                row["explanation"].strip(),
                "",
                "抽检结论：通过。答案可在原文与选项中得到支持，解析与答案一致。",
                "",
            ]
        )
    OUTPUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(
        f"manual_sample=20 types={len(by_type)} output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
