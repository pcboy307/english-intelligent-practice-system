#!/usr/bin/env python3
"""Regenerate only the M2.0b cloze questions against the fixed passage."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.deepseek_generation import (  # noqa: E402
    BudgetThresholdReached,
    CostLedger,
    DeepSeekClient,
    RepairExhausted,
)
from backend.app.generation import load_curriculum  # noqa: E402
from backend.app.m2_deepseek_pipeline import (  # noqa: E402
    _build_explanations_prompt,
    _validate_explanation_batch,
    validate_pilot_record,
)
from backend.app.m2_pilot import load_pilot_schedule  # noqa: E402
from backend.app.m2_repository import M2Repository  # noqa: E402
from backend.app.question_quality import validate_cloze_options  # noqa: E402


EVIDENCE = ROOT / "qa" / "evidence" / "m2b"
RUN_SECONDS = 90 * 60


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_resume_questions(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    payload = load_json(path)
    questions = payload.get("accepted_questions")
    if not isinstance(questions, list):
        return {}
    resumed = {}
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_index = question.get("question_index")
        if (
            isinstance(question_index, int)
            and 1 <= question_index <= 15
            and question_index not in resumed
        ):
            resumed[question_index] = question
    return resumed


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def allowed_tags(book_source: str) -> list[str]:
    book_tag = (
        "选必二"
        if book_source.startswith("选必二")
        else "选必一"
        if book_source.startswith("选必一")
        else "跨册"
        if book_source.startswith("跨册")
        else "必修"
    )
    curriculum = load_curriculum()
    return [
        item["id"]
        for item in curriculum["grammar_whitelist"]
        if book_tag in item["allowed_book_tags"]
    ]


def question_prompt(
    passage: str,
    assignments: list[dict],
) -> str:
    items = [
        {
            "question_index": item["question_index"],
            "book_source": item["book_source"],
            "difficulty": item["difficulty"],
            "allowed_grammar_tags": allowed_tags(item["book_source"]),
        }
        for item in assignments
    ]
    return f"""
Create lexical meaning-in-context cloze questions for the fixed passage.
Return JSON only:
{{
  "questions": [
    {{
      "question_index": 1,
      "stem": "the exact sentence containing (1) ______",
      "options": ["word1", "word2", "word3", "word4"],
      "answer": "word1",
      "knowledge_points": ["one unique lexical point"],
      "grammar_tags": ["one allowed grammar tag"],
      "book_source": "exact assignment",
      "difficulty": 1,
      "invalid": false,
      "invalid_reason": ""
    }}
  ]
}}

Rules:
- Every blank tests vocabulary meaning in context, never grammar morphology.
- Four options must be four DIFFERENT words. Never use forms of one lemma.
- All four options must have the same part of speech and belong to one semantic field.
- Do not include any option word, or another form of that word, in the stem.
- The blank's required part of speech must match every option.
- grammar_tags are metadata only. Choose one allowed tag related to incidental
  grammar; do not make the question a grammar-identification task.
- If no clean, uniquely answerable lexical question can be produced for an
  index, return invalid=true with a reason instead of forcing an answer.

Passage:
{passage}

Assignments:
{json.dumps(items, ensure_ascii=False, indent=2)}
""".strip()


def validate_question_shape(
    assignments: list[dict],
    data: dict,
) -> list[dict]:
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("QUESTIONS_ARRAY_MISSING")
    expected = {item["question_index"] for item in assignments}
    actual = {
        item.get("question_index")
        for item in questions
        if isinstance(item, dict)
    }
    if actual != expected:
        raise ValueError(
            f"QUESTION_INDEX_SET_MISMATCH expected={sorted(expected)} "
            f"actual={sorted(value for value in actual if isinstance(value, int))}"
        )
    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("QUESTION_NOT_OBJECT")
        for field in (
            "question_index",
            "stem",
            "options",
            "answer",
            "knowledge_points",
            "grammar_tags",
            "book_source",
            "difficulty",
        ):
            if field not in item:
                raise ValueError(f"QUESTION_FIELD_MISSING:{field}")
        if (
            not isinstance(item["options"], list)
            or len(item["options"]) != 4
            or any(not isinstance(option, str) or not option.strip() for option in item["options"])
        ):
            raise ValueError("QUESTION_OPTIONS_INVALID")
        if item["answer"] not in item["options"]:
            raise ValueError("QUESTION_ANSWER_NOT_IN_OPTIONS")
    return questions


def local_question_gates(
    question: dict,
    assignment: dict,
) -> list[dict]:
    failures = validate_cloze_options(
        stem=question["stem"],
        options=question["options"],
        answer=question["answer"],
    )
    if question["book_source"] != assignment["book_source"]:
        failures.append(
            {
                "code": "BOOK_SOURCE_SCHEDULE_MISMATCH",
                "expected": assignment["book_source"],
                "actual": question["book_source"],
            }
        )
    allowed = set(allowed_tags(question["book_source"]))
    if any(tag not in allowed for tag in question["grammar_tags"]):
        failures.append(
            {
                "code": "H4_BOOK_TAG_CONFLICT",
                "grammar_tags": question["grammar_tags"],
                "book_source": question["book_source"],
            }
        )
    return failures


def validate_question_batch(
    assignments: list[dict],
    data: dict,
) -> list[dict]:
    questions = validate_question_shape(assignments, data)
    assignments_by_index = {
        item["question_index"]: item for item in assignments
    }
    failures = []
    for question in questions:
        if question.get("invalid") is True:
            continue
        assignment = assignments_by_index[question["question_index"]]
        gate_failures = local_question_gates(question, assignment)
        if gate_failures:
            failures.append(
                {
                    "question_index": question["question_index"],
                    "stem": question["stem"],
                    "options": question["options"],
                    "answer": question["answer"],
                    "failures": gate_failures,
                }
            )
    if failures:
        raise ValueError(
            "QUESTION_HARD_GATE_FAILED "
            + json.dumps(failures, ensure_ascii=False)
        )
    return questions


def audit_prompt(
    passage: str,
    questions: list[dict],
) -> str:
    payload = []
    for item in questions:
        payload.append(
            {
                "question_index": item["question_index"],
                "stem": item["stem"],
                "options": item["options"],
                "answer": item["answer"],
            }
        )
    return f"""
Audit these four-option cloze questions. Return JSON only:
{{
  "items": [
    {{
      "question_index": 1,
      "option_pos": ["adjective", "adjective", "adjective", "adjective"],
      "valid_option_indices": [1],
      "invalid": false,
      "invalid_reason": ""
    }}
  ]
}}

For every question:
- Replace the blank with each option separately.
- List every option that is both grammatically and semantically valid.
- valid_option_indices must contain exactly one 1-based option index for a valid
  question. If zero or more than one option works, set invalid=true.
- option_pos must contain exactly four entries and all four should be the same
  coarse part of speech.
- Do not accept inflection-only choices or options already stated in the stem.

Passage:
{passage}

Questions:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def validate_audit_shape(
    expected_indices: list[int],
    data: dict,
) -> list[dict]:
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("AUDIT_ITEMS_ARRAY_MISSING")
    actual = [item.get("question_index") for item in items if isinstance(item, dict)]
    if set(actual) != set(expected_indices) or len(actual) != len(set(actual)):
        raise ValueError(
            f"AUDIT_INDEX_SET_MISMATCH expected={expected_indices} actual={actual}"
        )
    return items


def audit_questions(
    client: DeepSeekClient,
    ledger: CostLedger,
    passage: str,
    questions: list[dict],
) -> dict[int, dict]:
    expected_indices = [item["question_index"] for item in questions]
    from backend.app.deepseek_generation import run_repair_loop

    data = run_repair_loop(
        client=client,
        ledger=ledger,
        purpose="audit:cloze:uniqueness",
        prompt=audit_prompt(passage, questions),
        validate=lambda value: validate_audit_shape(expected_indices, value),
        max_repair_retries=1,
    )
    return {item["question_index"]: item for item in data}


def main() -> None:
    started = time.perf_counter()
    contract = load_json(ROOT / "contracts" / "generation-model.json")
    schedule = load_pilot_schedule()["passages"][0]
    client = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    ledger = CostLedger(contract)
    accepted = load_resume_questions(EVIDENCE / "cloze-rework.json")
    resumed_count = len(accepted)
    rejected: list[dict] = []
    invalid_count = 0
    total_generated = 0

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=True,
    ) as connection:
        bank = connection.execute(
            """
            SELECT id::text AS id
            FROM question_banks
            WHERE name='M2 Bank #2'
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        if not bank:
            raise RuntimeError("M2_BANK_2_NOT_FOUND")
        passage = connection.execute(
            """
            SELECT content
            FROM passages
            WHERE bank_id=%s AND passage_group_id=%s
            """,
            (bank["id"], schedule["passage_group_id"]),
        ).fetchone()
        if not passage:
            raise RuntimeError("EXISTING_CLOZE_PASSAGE_NOT_FOUND")

    from backend.app.deepseek_generation import run_repair_loop

    for _round in range(8):
        missing = [
            index for index in range(1, 16) if index not in accepted
        ]
        if not missing:
            break
        assignments = [
            {
                "question_index": index,
                **schedule["questions"][index - 1],
            }
            for index in missing[:5]
        ]
        expected_indices = [
            item["question_index"] for item in assignments
        ]
        data = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose="questions:cloze:lexical-rework",
            prompt=question_prompt(passage["content"], assignments),
            validate=lambda value: validate_question_batch(assignments, value),
            max_repair_retries=2,
        )
        items = [
            item
            for item in data
            if item["question_index"] in expected_indices
        ]
        total_generated += len(items)
        valid_for_audit = []
        for item in items:
            if item.get("invalid") is True:
                invalid_count += 1
                rejected.append(
                    {
                        "question_index": item["question_index"],
                        "category": "invalid",
                        "reason": item.get("invalid_reason", ""),
                    }
                )
                continue
            valid_for_audit.append(item)
        if not valid_for_audit:
            continue
        audits = audit_questions(
            client,
            ledger,
            passage["content"],
            valid_for_audit,
        )
        for item in valid_for_audit:
            audit = audits[item["question_index"]]
            pos = audit.get("option_pos")
            valid_indices = audit.get("valid_option_indices")
            answer_index = item["options"].index(item["answer"]) + 1
            if (
                audit.get("invalid") is True
                or not isinstance(pos, list)
                or len(pos) != 4
                or len(set(pos)) != 1
                or valid_indices != [answer_index]
            ):
                invalid_count += int(audit.get("invalid") is True)
                rejected.append(
                    {
                        "question_index": item["question_index"],
                        "category": "H9_H10_AUDIT_FAILED",
                        "audit": audit,
                    }
                )
                continue
            accepted[item["question_index"]] = item

        if time.perf_counter() - started > RUN_SECONDS:
            break
        ledger.assert_below_threshold("pilot")

    if not accepted:
        write_json(
            EVIDENCE / "cloze-rework.json",
            {
                "status": "failed",
                "accepted": 0,
                "rejected": rejected,
                "invalid_rate": 1.0,
                "requests": [item.as_dict() for item in client.requests],
            },
        )
        raise RuntimeError("CLOZE_REWORK_NO_VALID_QUESTIONS")

    questions = [accepted[index] for index in sorted(accepted)]
    missing_explanations = [
        question
        for question in questions
        if not isinstance(question.get("explanation"), str)
        or not question["explanation"].strip()
    ]
    if missing_explanations:
        explanations = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose="explanations:cloze:rework",
            prompt=_build_explanations_prompt(
                passage["content"],
                missing_explanations,
            ),
            response_schema=None,
            validate=lambda data: _validate_explanation_batch(
                list(range(1, len(missing_explanations) + 1)),
                data,
                observations=[],
            ),
            max_repair_retries=2,
        )
        for index, question in enumerate(missing_explanations, start=1):
            question["explanation"] = explanations[index]

    record = {
        "type": "cloze",
        "passage_group_id": schedule["passage_group_id"],
        "topic": schedule["topic"],
        "book_source": schedule["book_source"],
        "difficulty": schedule["difficulty"],
        "passage": passage["content"],
        "questions": questions,
    }
    observations = []
    report = validate_pilot_record(
        record,
        schedule,
        bank_id=bank["id"],
        batch_id="M2.0B-CLOZE-REWORK",
        observations=observations,
    )
    if not report["accepted"]:
        write_json(
            EVIDENCE / "cloze-rework.json",
            {
                "status": "failed",
                "accepted": len(questions),
                "report": report,
                "rejected": rejected,
                "accepted_questions": questions,
            },
        )
        raise RuntimeError("CLOZE_REWORK_HARD_GATE_FAILED")

    if len(questions) != 15:
        write_json(
            EVIDENCE / "cloze-rework.json",
            {
                "status": "partial",
                "accepted": len(questions),
                "rejected": rejected,
                "questions": questions,
                "report": report,
            },
        )
        raise RuntimeError("CLOZE_REWORK_NOT_FIFTEEN_QUESTIONS")

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        repo = M2Repository(connection)
        with connection.transaction():
            repo.replace_passage_questions(
                bank_id=bank["id"],
                batch_id="M2.0B-CLOZE-REWORK",
                record=record,
            )
        connection.commit()

    result = {
        "status": "passed",
        "questions": 15,
        "resumed_questions": resumed_count,
        "invalid_count": invalid_count,
        "invalid_rate": round(invalid_count / total_generated, 6)
        if total_generated
        else 0.0,
        "rejected": rejected,
        "report": report,
        "requests": [item.as_dict() for item in client.requests],
        "cost_cny": round(ledger.total_cny, 9),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "record": record,
    }
    write_json(EVIDENCE / "cloze-rework.json", result)
    (EVIDENCE / "cloze-rework.md").write_text(
        "\n".join(
            [
                "# 完形重做稿",
                "",
                record["passage"],
                "",
                *[
                    line
                    for index, question in enumerate(record["questions"], start=1)
                    for line in [
                        f"## {index}. {question['stem']}",
                        "",
                        *[f"- {option}" for option in question["options"]],
                        "",
                        f"**答案：** {question['answer']}",
                        "",
                        f"**解析：** {question['explanation']}",
                        "",
                    ]
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "questions": 15,
                "resumed_questions": resumed_count,
                "invalid_rate": result["invalid_rate"],
                "cost_cny": result["cost_cny"],
                "duration_seconds": result["duration_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
