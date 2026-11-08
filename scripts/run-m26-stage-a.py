#!/usr/bin/env python3
"""Generate and validate the six M2.6 Stage A passages."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.deepseek_generation import (  # noqa: E402
    BudgetThresholdReached,
    CircuitOpen,
    CostLedger,
    DeepSeekAPIError,
    DeepSeekClient,
    RepairExhausted,
    TransportRetriesExhausted,
)
from backend.app.bank_transfer import delete_bank as delete_existing_bank  # noqa: E402
from backend.app.generation import (  # noqa: E402
    validate_generated_passage,
)
from backend.app.m2_deepseek_pipeline import (  # noqa: E402
    generate_pilot_passage,
)
from backend.app.m2_repository import M2Repository  # noqa: E402
from backend.app.readability import flesch_reading_ease  # noqa: E402


SCHEDULE_PATH = ROOT / "config" / "m26-stage-a-schedule.json"
MODEL_PATH = ROOT / "contracts" / "generation-model.json"
EVIDENCE = ROOT / "qa" / "evidence" / "m26" / "stage-a"
RAW_GENERATION = EVIDENCE / "raw-responses" / "generation"
RAW_JUDGE = EVIDENCE / "raw-responses" / "judge"
RUN_SECONDS = 90 * 60
RUN_COST_CAP = 5.0
MAX_PAPER_ATTEMPTS = 8
FORCE_REGENERATE = "--force" in sys.argv[1:]
FORCE_PASSAGE_IDS = {
    item.split("=", 1)[1]
    for item in sys.argv[1:]
    if item.startswith("--force-passage=")
}
ALLOWED_TOPICS = {
    "科技",
    "环境",
    "健康心理",
    "文化艺术",
    "旅行地理",
    "志愿公益",
    "职业创业",
    "家庭代际",
    "体育竞技",
    "社会伦理",
    "人物传记",
    "自然科普",
    "历史遗产",
    "媒体信息",
    "城市交通",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def model_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_json(MODEL_PATH)
    generation = {
        **base,
        "prompt_version": "m26-stage-a-v3.5",
        "budget_cap_cny": {**base["budget_cap_cny"], "pilot": RUN_COST_CAP},
    }
    judge = {
        "provider": base["provider"],
        "base_url": base["base_url"],
        "model_id": base["judge_model_id"],
        "api_key_env": base["api_key_env"],
        "transport": base["transport"],
        "max_tokens": base["max_tokens"],
        "temperature": 0,
        "prompt_version": "m26-stage-a-judge-v4",
        "price_input_per_1m_cny": base["judge_price_input_per_1m_cny"],
        "price_output_per_1m_cny": base["judge_price_output_per_1m_cny"],
        "budget_cap_cny": {**base["budget_cap_cny"], "pilot": RUN_COST_CAP},
        "budget_stop_ratio": 1.0,
    }
    return generation, judge


def judge_prompt(record: dict[str, Any]) -> str:
    questions = [
        {
            "question_index": index,
            "stem": question["stem"],
            "options": question["options"],
            "answer": question["answer"],
            "reading_type": question.get("reading_type"),
            "grammar_category": question.get("grammar_category"),
            "cohesion_type": question.get("cohesion_type"),
        }
        for index, question in enumerate(record["questions"], start=1)
    ]
    rendered_passage = record["passage"]
    for index, question in enumerate(record["questions"], start=1):
        if record["type"] == "gap_fill":
            option_index = ord(str(question["answer"]).upper()) - ord("A")
            replacement = question["options"][option_index]
            marker = f"({index}) ______"
        elif record["type"] == "cloze":
            replacement = str(question["answer"])
            marker = f"({index}) ______"
        elif record["type"] == "grammar_fill":
            replacement = str(question["answer"])
            marker = f"{chr(0x2460 + index - 1)} ______"
        else:
            continue
        rendered_passage = rendered_passage.replace(marker, replacement, 1)
    return f"""
You are an independent senior-high English item reviewer. Judge the fixed
passage and questions. Do not rewrite them and do not assume the stated answer
is correct.

Return JSON with exactly:
{{
  "coherent": true,
  "coherence_reason": "one sentence",
  "questions": [
    {{
      "question_index": 1,
      "unique_best": true,
      "answer_supported": true,
      "answer_grammatical": true,
      "answer_semantic": true,
      "same_part_of_speech": true,
      "same_semantic_field": true,
      "near_synonym_distractor": false,
      "evidence_ok": true,
      "options_rewritten": true,
      "verdict": "ok",
      "reason": "one sentence"
    }}
  ]
}}

Rules:
- The "Passage with stated answers inserted" below is authoritative for the
  `answer_grammatical` and `answer_semantic` checks. If any inserted answer
  creates an ungrammatical, redundant, awkward, or contradictory sentence,
  set the corresponding field to false even if one option is clearly better
  than the others.
- `coherent` is false if the passage is a set of unrelated sentences.
- `unique_best` is false if two or more options can fit equally well.
- For cloze and grammar_fill, mentally insert the stated answer into its blank.
  `answer_grammatical` is false if the resulting sentence is ungrammatical.
  `answer_semantic` is false if the answer does not make sense in context.
- For gap_fill, first map the answer letter to its option text, then apply the
  same grammatical and semantic checks.
- For cloze, `same_part_of_speech` and `same_semantic_field` judge the four
  options; `near_synonym_distractor` is true when a distractor has essentially
  the same core meaning as the answer and is easy for a student to confuse with
  it, even if context makes the answer clearly better. Do not require the
  near-synonym to fit equally well.
- For grammar_fill, `same_part_of_speech` means all options are the same grammar
  category.
- For reading, `evidence_ok` means the passage supports the answer and
  `options_rewritten` means the answer is not copied from the passage.
- For gap_fill, `unique_best` means exactly one of the seven sentences fits.
- `verdict` must be `ok` only if the item is teachable and unambiguous.

Type: {record["type"]}
Topic: {record["topic"]}
Passage with stated answers inserted:
{rendered_passage}

Original passage with blanks:
{record["passage"]}

Questions:
{json.dumps(questions, ensure_ascii=False, indent=2)}
""".strip()


def validate_judge_shape(data: dict[str, Any], expected_count: int) -> dict[str, Any]:
    if not isinstance(data.get("coherent"), bool):
        raise ValueError("JUDGE_COHERENT_NOT_BOOLEAN")
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) != expected_count:
        raise ValueError("JUDGE_QUESTIONS_INVALID")
    expected = set(range(1, expected_count + 1))
    indices = [item.get("question_index") for item in questions]
    if set(indices) != expected or len(indices) != len(set(indices)):
        raise ValueError(
            f"JUDGE_INDEX_SET_INVALID expected={sorted(expected)} actual={indices}"
        )
    required_booleans = (
        "unique_best",
        "answer_supported",
        "answer_grammatical",
        "answer_semantic",
        "same_part_of_speech",
        "same_semantic_field",
        "near_synonym_distractor",
        "evidence_ok",
        "options_rewritten",
    )
    for item in questions:
        for field in required_booleans:
            if not isinstance(item.get(field), bool):
                raise ValueError(
                    f"JUDGE_FIELD_INVALID index={item.get('question_index')} field={field}"
                )
        if item.get("verdict") not in {"ok", "reject"}:
            raise ValueError(
                f"JUDGE_VERDICT_INVALID index={item.get('question_index')}"
            )
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError(
                f"JUDGE_REASON_INVALID index={item.get('question_index')}"
            )
    return data


def judge_record(
    *,
    client: DeepSeekClient,
    ledger: CostLedger,
    record: dict[str, Any],
) -> dict[str, Any]:
    prompt = judge_prompt(record)
    errors: list[str] = []
    for attempt in range(1, 3):
        repair = prompt
        if errors:
            repair += (
                "\n\nYour previous JSON was structurally invalid. Fix exactly "
                "these errors and return the complete JSON object:\n"
                + json.dumps(errors, ensure_ascii=False, indent=2)
            )
        response = client.chat_json(
            f"judge:{record['passage_group_id']}:attempt-{attempt}",
            repair,
        )
        ledger.record(
            purpose=f"judge:{record['passage_group_id']}",
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
        try:
            return validate_judge_shape(
                response.data,
                len(record["questions"]),
            )
        except ValueError as error:
            errors.append(str(error))
    raise ValueError("JUDGE_STRUCTURE_EXHAUSTED:" + "; ".join(errors))


def judge_failures(
    record: dict[str, Any],
    judgment: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if not judgment["coherent"]:
        failures.append("R8_PASSAGE_NOT_COHERENT")
    near_synonym_count = sum(
        bool(question.get("near_synonym_calibration"))
        for question in record["questions"]
    )
    for item in judgment["questions"]:
        index = item["question_index"]
        if not item["unique_best"]:
            failures.append(f"R9_NO_CLEAR_BEST:Q{index}")
        if not item["answer_supported"]:
            failures.append(f"ANSWER_UNSUPPORTED:Q{index}")
        if not item["answer_grammatical"]:
            failures.append(f"ANSWER_GRAMMATICAL_FAILURE:Q{index}")
        if not item["answer_semantic"]:
            failures.append(f"ANSWER_SEMANTIC_FAILURE:Q{index}")
        if item["verdict"] != "ok":
            failures.append(f"JUDGE_REJECTED:Q{index}")
        if record["type"] == "cloze":
            if not item["same_part_of_speech"]:
                failures.append(f"R13_POS_MISMATCH:Q{index}")
            if not item["same_semantic_field"]:
                failures.append(f"R13_SEMANTIC_FIELD:Q{index}")
            if item["near_synonym_distractor"]:
                near_synonym_count += 1
        if record["type"] == "grammar_fill" and not item["same_part_of_speech"]:
            failures.append(f"GRAMMAR_CATEGORY_MISMATCH:Q{index}")
        if record["type"] == "reading":
            if not item["evidence_ok"]:
                failures.append(f"R14_EVIDENCE_REJECTED:Q{index}")
            if not item["options_rewritten"]:
                failures.append(f"R14_OPTION_NOT_REWRITTEN:Q{index}")
    if record["type"] == "cloze" and near_synonym_count < 3:
        failures.append("R13_NEAR_SYNONYM_DISTRACTORS_TOO_FEW")
    return failures


def request_cost(requests: list[Any]) -> dict[str, Any]:
    return {
        "requests": len(requests),
        "prompt_tokens": sum(item.prompt_tokens for item in requests),
        "completion_tokens": sum(item.completion_tokens for item in requests),
        "cost_cny": round(sum(item.cost_cny for item in requests), 6),
        "elapsed_seconds": round(
            sum(item.elapsed_seconds for item in requests),
            3,
        ),
        "finish_reasons": [item.finish_reason for item in requests],
    }


def r11_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    report = validate_generated_passage(record)
    return [
        {
            "question_index": row["question_index"],
            "answer": row["answer"],
            "answer_occurrences": row["answer_occurrences"],
            "slot_form": row["slot_form"],
            "valid": row["valid"],
        }
        for row in report.metrics.get("fill_integrity", [])
    ]


def gate_summary(
    record: dict[str, Any],
    judgment: dict[str, Any],
) -> dict[str, Any]:
    report = validate_generated_passage(record)
    judge_errors = judge_failures(record, judgment)
    row = r11_rows(record)
    return {
        "accepted": report.accepted and not judge_errors,
        "machine_failures": [failure.as_dict() for failure in report.failures],
        "judge_failures": judge_errors,
        "r11": {
            "passed": all(item["valid"] and item["answer_occurrences"] == 0 for item in row),
            "blanks": row,
        },
        "r12": {
            "word_count": report.metrics.get("word_count"),
            "average_sentence_words": report.metrics.get("average_sentence_words"),
            "flesch_reading_ease": report.metrics.get("flesch_reading_ease"),
            "long_sentence_count": report.metrics.get("long_sentence_count"),
            "complex_structure_count": report.metrics.get("complex_structure_count"),
            "cloze_structure_categories": report.metrics.get(
                "cloze_structure_categories"
            ),
            "grammar_categories": report.metrics.get("grammar_categories"),
            "missing_required_grammar_categories": report.metrics.get(
                "missing_required_grammar_categories"
            ),
            "cohesion_types": report.metrics.get("cohesion_types"),
        },
        "r13": {
            "judge": judgment,
        },
        "r14": {
            "reading_types": report.metrics.get("reading_types"),
            "failures": [
                failure.as_dict()
                for failure in report.failures
                if failure.category.value == "m26_reading"
            ],
        },
        "r15": {
            "topic": record["topic"],
            "allowed": record["topic"] in ALLOWED_TOPICS,
        },
    }


def write_full_report(
    results: list[dict[str, Any]],
    gates: list[dict[str, Any]],
) -> None:
    lines = ["# M2.6 Stage A Generated Samples", ""]
    for result, gate in zip(results, gates, strict=True):
        record = result["record"]
        lines.extend(
            [
                f"## {record['passage_group_id']} · {record['type']} · {record['topic']}",
                "",
                record["passage"],
                "",
            ]
        )
        for index, question in enumerate(record["questions"], start=1):
            lines.append(f"**{index}. {question['stem']}**")
            lines.append("")
            for option_index, option in enumerate(question["options"]):
                label = chr(65 + option_index)
                lines.append(f"- {label}. {option}")
            lines.extend(
                [
                    "",
                    f"答案：{question['answer']}",
                    "",
                    f"解析：{question['explanation']}",
                    "",
                ]
            )
        lines.extend(
            [
                f"Gate result: `{gate['accepted']}`",
                "",
            ]
        )
    (EVIDENCE / "stage-a-samples.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def persist_bank(
    *,
    bank_name: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        with connection.transaction():
            existing = connection.execute(
                "SELECT id::text AS id, status FROM question_banks WHERE name=%s",
                (bank_name,),
            ).fetchone()
            if existing:
                if existing["status"] == "active":
                    raise RuntimeError(
                        f"ACTIVE_STAGE_A_BANK_CANNOT_BE_REPLACED:{existing['id']}"
                    )
                history = connection.execute(
                    """
                    SELECT
                        (SELECT count(*) FROM practice_sessions WHERE bank_id=%s) AS sessions,
                        (SELECT count(*) FROM practice_reports WHERE bank_id=%s) AS reports,
                        (SELECT count(*) FROM question_attempts WHERE bank_id=%s) AS attempts,
                        (SELECT count(*) FROM mistake_items WHERE bank_id=%s) AS mistakes,
                        (SELECT count(*) FROM error_tags WHERE bank_id=%s) AS error_tags
                    """,
                    (
                        existing["id"],
                        existing["id"],
                        existing["id"],
                        existing["id"],
                        existing["id"],
                    ),
                ).fetchone()
                if any(int(history[key]) for key in history):
                    raise RuntimeError(
                        "STAGE_A_BANK_HAS_USER_HISTORY:"
                        + json.dumps(history, ensure_ascii=False)
                    )
                delete_existing_bank(connection, existing["id"])
            repository = M2Repository(connection)
            bank = repository.create_bank(
                name=bank_name,
                target_size=500,
                difficulty_profile="advanced",
            )
            job = repository.create_generation_job(
                bank["id"],
            target_passages=72,
                batch_size=1,
                approved_by="user-m26-stage-a",
                reason="M2.6 Stage A six-passage quality pilot",
            )
            repository.set_job_status(job["id"], "running")
            for result in results:
                repository.insert_passage(
                    bank_id=bank["id"],
                    job_id=job["id"],
                    batch_id="M26-STAGE-A",
                    record=result["record"],
                    prevalidated=True,
                )
            repository.set_job_status(
                job["id"],
                "completed",
                checkpoint={
                    "phase": "stage_a_complete",
                    "passages": len(results),
                    "questions": sum(
                        len(item["record"]["questions"])
                        for item in results
                    ),
                },
            )
            connection.execute(
                "UPDATE passages SET status='published' WHERE bank_id=%s",
                (bank["id"],),
            )
            connection.execute(
                "UPDATE questions SET status='published' WHERE bank_id=%s",
                (bank["id"],),
            )
            connection.execute(
                """
                UPDATE question_banks
                SET status='archived', finished_at=now()
                WHERE id=%s
                """,
                (bank["id"],),
            )
            return {
                "bank_id": bank["id"],
                "bank_name": bank_name,
                "job_id": job["id"],
            }


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    RAW_GENERATION.mkdir(parents=True, exist_ok=True)
    RAW_JUDGE.mkdir(parents=True, exist_ok=True)
    schedule = load_json(SCHEDULE_PATH)
    generation_config, judge_config = model_contracts()
    generator = DeepSeekClient(
        generation_config,
        raw_output_dir=RAW_GENERATION,
    )
    judge = DeepSeekClient(
        judge_config,
        raw_output_dir=RAW_JUDGE,
    )
    generation_ledger = CostLedger(generation_config)
    judge_ledger = CostLedger(judge_config)
    started = time.perf_counter()
    ping_result = generator.ping()
    existing_record_by_id: dict[str, dict[str, Any]] = {}
    existing_gate_by_id: dict[str, dict[str, Any]] = {}
    existing_cost_by_id: dict[str, dict[str, Any]] = {}
    old_generated_path = EVIDENCE / "stage-a-generated.json"
    old_gates_path = EVIDENCE / "stage-a-gates.json"
    old_cost_path = EVIDENCE / "stage-a-cost-report.json"
    if (
        not FORCE_REGENERATE
        and old_generated_path.exists()
        and old_gates_path.exists()
    ):
        existing_record_by_id = {
            item["passage_group_id"]: item
            for item in load_json(old_generated_path)
        }
        existing_gate_by_id = {
            item["passage_group_id"]: item
            for item in load_json(old_gates_path).get("papers", [])
        }
    if old_cost_path.exists():
        existing_cost_by_id = {
            item["passage_group_id"]: item
            for item in load_json(old_cost_path).get("papers", [])
        }

    results: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for spec in schedule["passages"]:
        passage_id = spec["passage_group_id"]
        existing_record = existing_record_by_id.get(passage_id)
        existing_gate = existing_gate_by_id.get(passage_id)
        if (
            existing_record is not None
            and existing_gate is not None
            and existing_gate.get("accepted") is True
            and passage_id not in FORCE_PASSAGE_IDS
        ):
            results.append(
                {
                    "record": existing_record,
                    "judgment": existing_gate["r13"]["judge"],
                    "attempt": "resumed",
                    "cost": existing_cost_by_id.get(
                        passage_id,
                        {
                            "generation": request_cost([]),
                            "judge": request_cost([]),
                            "total_cny": 0,
                        },
                    ),
                }
            )
            gates.append(existing_gate)
    failures: list[dict[str, Any]] = []

    try:
        for spec in schedule["passages"]:
            if spec["passage_group_id"] in {
                item["record"]["passage_group_id"]
                for item in results
            }:
                continue
            spec = {**spec, "validation_profile": "m26"}
            accepted_result = None
            accepted_gate = None
            attempt_feedback: list[str] = []
            for paper_attempt in range(1, MAX_PAPER_ATTEMPTS + 1):
                if time.perf_counter() - started > RUN_SECONDS:
                    raise RuntimeError("RUN_TIME_LIMIT_REACHED")
                generation_start = len(generator.requests)
                judge_start = len(judge.requests)
                try:
                    record = generate_pilot_passage(
                        client=generator,
                        ledger=generation_ledger,
                        schedule_passage={
                            **spec,
                            "generation_feedback": attempt_feedback,
                        },
                        bank_id="00000000-0000-4000-8000-000000000000",
                        batch_id="M26-STAGE-A",
                        max_repair_retries=1,
                    )
                    judgment = judge_record(
                        client=judge,
                        ledger=judge_ledger,
                        record=record,
                    )
                    gate = gate_summary(record, judgment)
                    cost = {
                        "generation": request_cost(
                            generator.requests[generation_start:]
                        ),
                        "judge": request_cost(judge.requests[judge_start:]),
                    }
                    cost["total_cny"] = round(
                        cost["generation"]["cost_cny"]
                        + cost["judge"]["cost_cny"],
                        6,
                    )
                    result = {
                        "record": record,
                        "judgment": judgment,
                        "attempt": paper_attempt,
                        "cost": cost,
                    }
                    if gate["accepted"]:
                        accepted_result = result
                        accepted_gate = gate
                        break
                    attempt_feedback = [
                        failure["message"]
                        + (
                            " details="
                            + json.dumps(
                                failure.get("details") or {},
                                ensure_ascii=False,
                            )
                            if failure.get("details")
                            else ""
                        )
                        for failure in gate["machine_failures"]
                    ] + gate["judge_failures"]
                    failures.append(
                        {
                            "passage_group_id": spec["passage_group_id"],
                            "paper_attempt": paper_attempt,
                            "kind": "quality",
                            "gate": gate,
                        }
                    )
                except (
                    DeepSeekAPIError,
                    CircuitOpen,
                    BudgetThresholdReached,
                ):
                    raise
                except (
                    RepairExhausted,
                    TransportRetriesExhausted,
                    ValueError,
                ) as error:
                    attempt_feedback = [str(error)]
                    failures.append(
                        {
                            "passage_group_id": spec["passage_group_id"],
                            "paper_attempt": paper_attempt,
                            "kind": "generation",
                            "error": str(error),
                        }
                    )
                combined_cost = generation_ledger.total_cny + judge_ledger.total_cny
                if combined_cost >= RUN_COST_CAP:
                    raise BudgetThresholdReached(
                        f"RUN_COST_CAP_REACHED cost_cny={combined_cost:.6f}"
                    )
            if accepted_result is None or accepted_gate is None:
                continue
            results.append(accepted_result)
            gates.append(accepted_gate)

        unique_topics = {item["record"]["topic"] for item in results}
        schedule_order = {
            item["passage_group_id"]: index
            for index, item in enumerate(schedule["passages"])
        }
        paired = sorted(
            zip(results, gates, strict=True),
            key=lambda pair: schedule_order[pair[0]["record"]["passage_group_id"]],
        )
        results = [result for result, _ in paired]
        gates = [gate for _, gate in paired]
        topic_counts = {
            topic: sum(item["record"]["topic"] == topic for item in results)
            for topic in unique_topics
        }
        r15 = {
            "topics": sorted(unique_topics),
            "topic_count": len(unique_topics),
            "counts": topic_counts,
            "all_allowed": unique_topics <= ALLOWED_TOPICS,
            "no_topic_over_six": all(value <= 6 for value in topic_counts.values()),
        }
        all_passed = (
            len(results) == len(schedule["passages"])
            and all(gate["accepted"] for gate in gates)
            and r15["topic_count"] >= 6
            and r15["all_allowed"]
        )

        cost_report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ping": ping_result,
            "papers": [
                {
                    "passage_group_id": result["record"]["passage_group_id"],
                    **result["cost"],
                }
                for result in results
            ],
            "totals": {
                "passages": len(results),
                "questions": sum(
                    len(item["record"]["questions"])
                    for item in results
                ),
                "prompt_tokens": (
                    generation_ledger.prompt_tokens
                    + judge_ledger.prompt_tokens
                    + sum(
                        item["cost"]["generation"]["prompt_tokens"]
                        + item["cost"]["judge"]["prompt_tokens"]
                        for item in results
                        if item["attempt"] == "resumed"
                    )
                ),
                "completion_tokens": (
                    generation_ledger.completion_tokens
                    + judge_ledger.completion_tokens
                    + sum(
                        item["cost"]["generation"]["completion_tokens"]
                        + item["cost"]["judge"]["completion_tokens"]
                        for item in results
                        if item["attempt"] == "resumed"
                    )
                ),
                "cost_cny": round(
                    generation_ledger.total_cny
                    + judge_ledger.total_cny
                    + sum(
                        item["cost"]["total_cny"]
                        for item in results
                        if item["attempt"] == "resumed"
                    ),
                    6,
                ),
            },
            "generation_requests": [
                item.as_dict() for item in generator.requests
            ],
            "judge_requests": [item.as_dict() for item in judge.requests],
        }
        question_count = cost_report["totals"]["questions"]
        if question_count:
            per_question = cost_report["totals"]["cost_cny"] / question_count
            cost_report["extrapolations"] = {
                "300_questions_cny": round(per_question * 300, 6),
                "2000_questions_cny": round(per_question * 2000, 6),
            }
        else:
            cost_report["extrapolations"] = None
        write_json(EVIDENCE / "stage-a-cost-report.json", cost_report)
        write_json(
            EVIDENCE / "stage-a-gates.json",
            {
                "all_passed": all_passed,
                "r15": r15,
                "papers": [
                    {
                        "passage_group_id": result["record"]["passage_group_id"],
                        **gate,
                    }
                    for result, gate in zip(results, gates, strict=True)
                ],
                "failures": failures,
            },
        )
        if results:
            write_full_report(results, gates)
            write_json(
                EVIDENCE / "stage-a-generated.json",
                [result["record"] for result in results],
            )
        if not all_passed:
            raise RuntimeError(
                "STAGE_A_INCOMPLETE:"
                + json.dumps(
                    {
                        "passed": len(results),
                        "expected": len(schedule["passages"]),
                        "failures": failures,
                    },
                    ensure_ascii=False,
                )
            )

        bank_result = persist_bank(
            bank_name=schedule["bank_name"],
            results=results,
        )
        write_json(
            EVIDENCE / "stage-a-bank.json",
            bank_result,
        )
        print(
            json.dumps(
                {
                    "stage_a": "PASS",
                    "passages": len(results),
                    "questions": question_count,
                    "cost_cny": cost_report["totals"]["cost_cny"],
                    "bank": bank_result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        write_json(
            EVIDENCE / "stage-a-requests.json",
            {
                "generation": [
                    item.as_dict() for item in generator.requests
                ],
                "judge": [item.as_dict() for item in judge.requests],
            },
        )


if __name__ == "__main__":
    main()
