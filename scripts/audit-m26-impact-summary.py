#!/usr/bin/env python3
"""Produce the one-time, corrected M2 Stage 0 impact summary."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
STAGE0 = ROOT / "qa" / "evidence" / "m26" / "stage0-diagnosis.json"
OUTPUT = ROOT / "qa" / "evidence" / "m26" / "post-stage0-impact-summary.json"
TOKEN_PATTERN = r"[a-z]+(?:['-][a-z]+)*"


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def main() -> None:
    stage0 = json.loads(STAGE0.read_text(encoding="utf-8"))
    malformed_non_answer = sum(
        row["malformed_word_slots"] - row["answer_at_slot"]
        for row in stage0["passages"]
    )
    malformed_non_answer_passages = sum(
        row["malformed_word_slots"] - row["answer_at_slot"] > 0
        for row in stage0["passages"]
    )

    whitelist = json.loads(
        (ROOT / "contracts" / "vocabulary-whitelist.json").read_text(
            encoding="utf-8"
        )
    )
    entries = {
        entry["word"].casefold(): entry
        for entry in whitelist["entries"]
    }

    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        bank_id = connection.execute(
            "SELECT active_bank_id FROM bank_active_state WHERE singleton=TRUE"
        ).fetchone()["active_bank_id"]
        fills = connection.execute(
            """
            SELECT q.passage_group_id, q.id, q.type, q.answer#>>'{}' AS answer,
                   p.content
            FROM questions q
            JOIN passages p
              ON p.bank_id=q.bank_id
             AND p.passage_group_id=q.passage_group_id
            WHERE q.bank_id=%s
              AND q.status='published'
              AND q.type IN ('cloze', 'grammar_fill')
            ORDER BY q.id
            """,
            (bank_id,),
        ).fetchall()
        gap_rows = connection.execute(
            """
            SELECT p.passage_group_id, p.content, q.options
            FROM passages p
            JOIN questions q
              ON q.bank_id=p.bank_id
             AND q.passage_group_id=p.passage_group_id
            WHERE p.bank_id=%s
              AND q.status='published'
              AND p.type='gap_fill'
            GROUP BY p.passage_group_id, p.content, q.options
            """,
            (bank_id,),
        ).fetchall()

    open_answer_blanks = 0
    open_answer_passages: set[str] = set()
    for row in fills:
        passage = row["content"].casefold()
        open_words = []
        for token in re.findall(TOKEN_PATTERN, row["answer"].casefold()):
            entry = entries.get(token)
            if entry is None or not entry.get("closed_class"):
                open_words.append(token)
        if any(
            re.search(rf"\b{re.escape(word)}\b", passage)
            for word in open_words
        ):
            open_answer_blanks += 1
            open_answer_passages.add(row["passage_group_id"])

    gap_leak_passages: set[str] = set()
    for passage in gap_rows:
        passage_tokens = re.findall(
            TOKEN_PATTERN,
            passage["content"].casefold(),
        )
        leaked = False
        for option in passage["options"]:
            option_tokens = re.findall(
                TOKEN_PATTERN,
                option.casefold(),
            )
            windows = {
                tuple(option_tokens[index : index + 6])
                for index in range(len(option_tokens) - 5)
            }
            if any(
                tuple(passage_tokens[index : index + 6]) in windows
                for index in range(len(passage_tokens) - 5)
            ):
                leaked = True
                break
        if leaked:
            gap_leak_passages.add(passage["passage_group_id"])

    output = {
        "bank_id": str(bank_id),
        "state1_answer_word_at_slot": {
            "blanks": stage0["direct_answer_visible"]["blanks"],
            "passages": stage0["direct_answer_visible"]["passages"],
        },
        "state2_missing_placeholder_non_answer_word": {
            "blanks": malformed_non_answer,
            "passages": malformed_non_answer_passages,
        },
        "open_class_answer_word_anywhere": {
            "blanks": open_answer_blanks,
            "passages": len(open_answer_passages),
            "function_words_excluded": True,
        },
        "gap_option_text_leak": {
            "passages": len(gap_leak_passages),
            "minimum_contiguous_overlap_words": 6,
        },
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
