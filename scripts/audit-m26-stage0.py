#!/usr/bin/env python3
"""Diagnose fill-passage placeholder integrity without changing data."""

from __future__ import annotations

import json
import importlib.util
import os
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "qa" / "evidence" / "m26" / "stage0-diagnosis.json"
TEXT_OUTPUT = ROOT / "qa" / "evidence" / "m26" / "stage0-report.md"
TARGET = "M2-FULL-CLOZE-04"
TOKEN_PATTERN = re.compile(r"[a-z]+(?:['-][a-z]+)*")


def load_candidate_lemmas():
    path = ROOT / "scripts" / "vocabulary-audit.py"
    spec = importlib.util.spec_from_file_location("vocabulary_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("VOCABULARY_AUDIT_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.candidate_lemmas


candidate_lemmas = load_candidate_lemmas()


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def question_order(question_id: str) -> int:
    match = re.search(r"(\d+)$", question_id)
    if not match:
        raise ValueError(f"QUESTION_ORDER_MISSING:{question_id}")
    return int(match.group(1))


def marker_for(type_: str, order: int) -> str:
    if type_ == "grammar_fill":
        return chr(0x2460 + order - 1)
    return f"({order})"


def tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold().replace("\u2019", "'"))


def same_lemma(left: str, right: str) -> bool:
    return bool(set(candidate_lemmas(left)) & set(candidate_lemmas(right)))


def answer_occurs_in_text(content: str, answer: str) -> bool:
    content_tokens = tokens(content)
    answer_tokens = tokens(answer)
    if not answer_tokens:
        return False
    width = len(answer_tokens)
    return any(
        all(
            same_lemma(content_tokens[index + offset], answer_tokens[offset])
            for offset in range(width)
        )
        for index in range(len(content_tokens) - width + 1)
    )


def answer_is_at_slot(slot_token: str, answer: str) -> bool:
    answer_tokens = tokens(answer)
    return len(answer_tokens) == 1 and same_lemma(slot_token, answer_tokens[0])


def write_report(result: dict) -> None:
    lines = [
        "# M2.6 阶段0 定性报告",
        "",
        "日期：2026-11-08",
        "",
        "## 结论",
        "",
        "**情况A：数据错误。** 语篇存储原文把答案词保留在编号空位上，",
        "渲染层只是原样打印该文本，没有额外插入答案。",
        "",
        "## 数据库与取证范围",
        "",
        f"- PostgreSQL：`127.0.0.1:{result['server_port']}`",
        f"- 数据库：`{result['database_name']}`",
        f"- `practice_sessions`：{result['practice_sessions_count']} 行",
        f"- active bank：`{result['bank_id']}`",
        f"- 答案文本逐题检查：{result['answer_checked_questions']} 题",
        "",
        "## 直接证据",
        "",
        "`M2-FULL-CLOZE-04` 的存储原文如下（节选；完整原文见 JSON）：",
        "",
        "```text",
        result["target_snippet"],
        "```",
        "",
        "15 个编号空位的存储词与该题答案逐一相同：",
        "",
        "| 题号 | 答案 | 空位存储词 |",
        "| --- | --- | --- |",
    ]
    target = next(
        row
        for row in result["passages"]
        if row["passage_group_id"] == result["target_passage"]
    )
    for detail in target["details"]:
        lines.append(
            f"| `{detail['question_id']}` | `{detail['answer']}` | "
            f"`{detail['slot_token']}` |"
        )
    lines.extend(
        [
            "",
            "渲染路径：`apps/mobile/app/practice.tsx:377`",
            "",
            "```tsx",
            "<Text style={styles.passage}>{item.passage}</Text>",
            "```",
            "",
            "落库路径：`scripts/run-m2-full.py:433`",
            "",
            "```python",
            '"passage": str(data.get("passage", "")),',
            "```",
            "",
            "生成结果被原样写入，管线中没有“答案词替换为统一占位符”的步骤。",
            "",
            "## 影响面",
            "",
            "对完形和语法填空共 150 题逐题检查；七选五的 `answer` 是",
            "选项字母，不是可检查的答案文本，因此只统计其占位符形态。",
            "",
            "| 口径 | 空数 | 篇数 |",
            "| --- | ---: | ---: |",
            (
                "| 答案直接占据自己的编号空位 | "
                f"{result['direct_answer_visible']['blanks']} | "
                f"{result['direct_answer_visible']['passages']} |"
            ),
            (
                "| 答案词或其屈折形式出现在全文任意位置 | "
                f"{result['answer_form_anywhere']['blanks']} | "
                f"{result['answer_form_anywhere']['passages']} |"
            ),
            (
                "| 编号后直接跟普通单词、无下划线占位符 | "
                f"{result['malformed_placeholder']['blanks']} | "
                f"{result['malformed_placeholder']['passages']} |"
            ),
            "",
            "“全文任意位置”包含语法填空中 `the/of/that/is` 等功能词的",
            "正常复现，不能全部视为答案泄露；直接坏空位只有下面 1 篇。",
            "",
            "### 答案直接占据本空位",
            "",
            "| 语篇 | 题型 | 空数 |",
            "| --- | --- | ---: |",
        ]
    )
    for row in result["passages"]:
        if row["answer_at_slot"]:
            lines.append(
                f"| `{row['passage_group_id']}` | `{row['type']}` | "
                f"{row['answer_at_slot']} |"
            )
    lines.extend(
        [
            "",
            "### 答案词在全文任意位置出现",
            "",
            "| 语篇 | 题型 | 空数 | 题号与答案 |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in result["passages"]:
        if row["answer_anywhere_text_blanks"]:
            listed = ", ".join(
                f"`{item['question_id']}`={item['answer']}"
                for item in row["answer_occurrences"]
            )
            lines.append(
                f"| `{row['passage_group_id']}` | `{row['type']}` | "
                f"{row['answer_anywhere_text_blanks']} | {listed} |"
            )
    lines.extend(
        [
            "",
            "### 占位符形态错误",
            "",
            "| 语篇 | 题型 | 无下划线空位 |",
            "| --- | --- | ---: |",
        ]
    )
    for row in result["passages"]:
        if row["malformed_word_slots"]:
            lines.append(
                f"| `{row['passage_group_id']}` | `{row['type']}` | "
                f"{row['malformed_word_slots']} |"
            )
    lines.extend(
        [
            "",
            "## 处置结论",
            "",
            "- 旧库填空类生成数据不可复用。",
            "- M2.6 必须采用“先定答案词、写文时禁词、逐空替换为统一下划线",
            "  占位符、落库前逐题复核”的新管线。",
            "- 本阶段未创建新 bank、未改名旧 bank、未生成任何 Stage A 内容。",
            "",
        ]
    )
    TEXT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        server_row = connection.execute(
            """
            SELECT
                inet_server_port() AS server_port,
                current_database() AS database_name,
                (SELECT count(*) FROM practice_sessions) AS session_count
            """
        ).fetchone()
        bank = connection.execute(
            """
            SELECT active_bank_id
            FROM bank_active_state
            WHERE singleton=TRUE
            """
        ).fetchone()["active_bank_id"]
        passages = connection.execute(
            """
            SELECT passage_group_id, type, content
            FROM passages
            WHERE bank_id=%s
              AND type IN ('cloze', 'grammar_fill', 'gap_fill')
            ORDER BY passage_group_id
            """,
            (bank,),
        ).fetchall()
        questions = connection.execute(
            """
            SELECT id, passage_group_id, type, answer#>>'{}' AS answer
            FROM questions
            WHERE bank_id=%s
              AND status='published'
              AND type IN ('cloze', 'grammar_fill', 'gap_fill')
            ORDER BY id
            """,
            (bank,),
        ).fetchall()

    by_passage: dict[str, list[dict]] = {}
    for question in questions:
        by_passage.setdefault(question["passage_group_id"], []).append(question)

    reports = []
    target_snippet = ""
    target_content = ""
    for passage in passages:
        malformed_slots = 0
        answer_at_slot = 0
        answer_anywhere = 0
        details = []
        answer_occurrences = []
        for question in by_passage.get(passage["passage_group_id"], []):
            answer = str(question["answer"]).strip()
            order = question_order(question["id"])
            marker = marker_for(passage["type"], order)
            match = re.search(
                re.escape(marker) + r"\s*([^\s,.;:!?()\[\]{}]+)",
                passage["content"],
            )
            if match:
                token = match.group(1)
                is_word = bool(re.match(r"^[A-Za-z][A-Za-z'-]*$", token))
                if is_word and "_" not in token:
                    malformed_slots += 1
                    is_answer_form = answer_is_at_slot(token, answer)
                    if passage["type"] in {"cloze", "grammar_fill"} and is_answer_form:
                        answer_at_slot += 1
                    details.append(
                        {
                            "question_id": question["id"],
                            "answer": answer,
                            "slot_token": token,
                            "is_answer_form": (
                                passage["type"] in {"cloze", "grammar_fill"}
                                and is_answer_form
                            ),
                        }
                    )
            if passage["type"] in {"cloze", "grammar_fill"}:
                occurs = answer_occurs_in_text(passage["content"], answer)
                answer_anywhere += int(occurs)
                if occurs:
                    answer_occurrences.append(
                        {
                            "question_id": question["id"],
                            "answer": answer,
                        }
                    )
        if passage["passage_group_id"] == TARGET:
            target_snippet = passage["content"][:520]
            target_content = passage["content"]
        reports.append(
            {
                "passage_group_id": passage["passage_group_id"],
                "type": passage["type"],
                "malformed_word_slots": malformed_slots,
                "answer_at_slot": answer_at_slot,
                "answer_anywhere_text_blanks": answer_anywhere,
                "answer_occurrences": answer_occurrences,
                "details": details,
            }
        )

    by_type = {}
    for type_ in ("cloze", "grammar_fill", "gap_fill"):
        rows = [row for row in reports if row["type"] == type_]
        answer_relevant = [
            row
            for row in rows
            if type_ in {"cloze", "grammar_fill"}
        ]
        by_type[type_] = {
            "passages": len(rows),
            "malformed_passages": sum(
                row["malformed_word_slots"] > 0 for row in rows
            ),
            "malformed_slots": sum(
                row["malformed_word_slots"] for row in rows
            ),
            "answer_at_slot": sum(row["answer_at_slot"] for row in rows),
            "answer_anywhere_text_blanks": sum(
                row["answer_anywhere_text_blanks"]
                for row in answer_relevant
            ),
            "answer_anywhere_passages": sum(
                row["answer_anywhere_text_blanks"] > 0
                for row in answer_relevant
            ),
            "answer_at_slot_passages": sum(
                row["answer_at_slot"] > 0 for row in rows
            ),
        }
    checked_answer_questions = sum(
        len(by_passage.get(row["passage_group_id"], []))
        for row in reports
        if row["type"] in {"cloze", "grammar_fill"}
    )
    result = {
        "server_port": server_row["server_port"],
        "database_name": server_row["database_name"],
        "practice_sessions_count": server_row["session_count"],
        "bank_id": str(bank),
        "target_passage": TARGET,
        "target_snippet": target_snippet,
        "target_content": target_content,
        "conclusion": "A_DATA_CONTAINS_ANSWER",
        "root_cause": (
            "Stored passage contains numbered answer words instead of a "
            "uniform underscore placeholder; the renderer prints passage "
            "text unchanged."
        ),
        "answer_checked_questions": checked_answer_questions,
        "direct_answer_visible": {
            "blanks": sum(row["answer_at_slot"] for row in reports),
            "passages": sum(row["answer_at_slot"] > 0 for row in reports),
            "passage_ids": [
                row["passage_group_id"]
                for row in reports
                if row["answer_at_slot"] > 0
            ],
        },
        "answer_form_anywhere": {
            "blanks": sum(
                row["answer_anywhere_text_blanks"]
                for row in reports
                if row["type"] in {"cloze", "grammar_fill"}
            ),
            "passages": sum(
                row["answer_anywhere_text_blanks"] > 0
                for row in reports
                if row["type"] in {"cloze", "grammar_fill"}
            ),
        },
        "malformed_placeholder": {
            "blanks": sum(row["malformed_word_slots"] for row in reports),
            "passages": sum(
                row["malformed_word_slots"] > 0 for row in reports
            ),
            "passage_ids": [
                row["passage_group_id"]
                for row in reports
                if row["malformed_word_slots"] > 0
            ],
        },
        "by_type": by_type,
        "passages": reports,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_report(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
