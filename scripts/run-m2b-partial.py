#!/usr/bin/env python3
"""Run the complete M2.0b pilot with per-passage failure isolation."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


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
from backend.app.m2_deepseek_pipeline import generate_pilot_passage  # noqa: E402
from backend.app.m2_pilot import load_pilot_schedule  # noqa: E402
from backend.app.m2_repository import M2Repository  # noqa: E402


EVIDENCE = ROOT / "qa" / "evidence" / "m2b"
BANK_NAME = "M2 Bank #2"
RUN_LIMIT_SECONDS = 90 * 60


class BlockingRunError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_passages_markdown(
    records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    lines = ["# M2.0b 实际产出", ""]
    for record in records:
        lines.extend(
            [
                f"## {record['type']} · {record['passage_group_id']}",
                "",
                record["passage"],
                "",
            ]
        )
        for index, question in enumerate(record["questions"], start=1):
            lines.extend(
                [
                    f"### {index}. {question['stem']}",
                    "",
                    *[
                        f"- {option}"
                        for option in question["options"]
                    ],
                    "",
                    f"**答案：** {question['answer']}",
                    "",
                    f"**解析：** {question['explanation']}",
                    "",
                ]
            )
    if failures:
        lines.extend(["## 失败语篇", ""])
        for failure in failures:
            lines.append(
                f"- {failure['type']} / {failure['passage_group_id']}: "
                f"{failure['category']} — {failure['message']}"
            )
        lines.append("")
    (EVIDENCE / "passages.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def request_stats(client: DeepSeekClient) -> dict[str, Any]:
    rows = [item for item in client.requests if item.purpose != "ping"]
    total = len(rows)
    counts = Counter(item.status for item in rows)
    json_parse_failures = counts.get("json_parse_error", 0)
    structure_failures = counts.get("validation_error", 0)
    return {
        "request_count": total,
        "status_counts": dict(sorted(counts.items())),
        "json_parse_fail_rate": (
            round(json_parse_failures / total, 6) if total else 0.0
        ),
        "structure_fail_rate": (
            round(structure_failures / total, 6) if total else 0.0
        ),
        "finish_reason_distribution": dict(
            sorted(
                Counter(
                    item.finish_reason or "unknown" for item in rows
                ).items()
            )
        ),
        "requests": [item.as_dict() for item in rows],
    }


def category_from_error(error: Exception) -> tuple[str, str]:
    message = str(error)
    if isinstance(error, RepairExhausted):
        if "GENERATION_BATCH_SCHEMA_INVALID" in message or "INDEX" in message:
            return "structure", message
        if "EXPLANATION_" in message:
            return "structure", message
        return "structure", message
    if isinstance(error, TransportRetriesExhausted):
        return "transport", message
    if "WORD_COUNT" in message:
        return "word_count", message
    if "QUESTION_COUNT" in message or "QUESTION_OPTIONS" in message:
        return "question_structure", message
    if "PILOT_PASSAGE_HARD_GATE_FAILED" in message:
        return "hard_gate", message
    return "structure", message


def main() -> None:
    started_at = time.perf_counter()
    contract = load_json(ROOT / "contracts" / "generation-model.json")
    schedule = load_pilot_schedule()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    client = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    ledger = CostLedger(contract)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    blocking_issue = None

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        preflight = connection.execute(
            """
            SELECT inet_server_port() AS port,
                   current_database() AS database_name,
                   (SELECT count(*) FROM practice_sessions) AS session_count
            """
        ).fetchone()
        if (
            preflight["port"] != 15432
            or preflight["database_name"] != "english_practice"
            or preflight["session_count"] < 42
        ):
            raise RuntimeError("PREFLIGHT_DATABASE_IDENTITY_OR_DATA_REGRESSION")
        write_json(
            EVIDENCE / "preflight.json",
            {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                **preflight,
                "previous_recorded_minimum": 42,
                "passes": True,
            },
        )

        bank_row = connection.execute(
            """
            SELECT id::text AS id
            FROM question_banks
            WHERE name=%s AND status='generating'
            ORDER BY created_at DESC LIMIT 1
            """,
            (BANK_NAME,),
        ).fetchone()
        if not bank_row:
            raise RuntimeError("M2_BANK_2_NOT_FOUND_OR_NOT_GENERATING")
        bank_id = bank_row["id"]
        repo = M2Repository(connection)
        job = repo.create_generation_job(
            bank_id,
            target_passages=47,
            batch_size=3,
            approved_by="system_owner",
            reason="M2.0b one-shot partial-batch run",
        )
        repo.set_job_status(job["id"], "running")
        connection.commit()

        for passage_spec in schedule["passages"]:
            if time.perf_counter() - started_at >= RUN_LIMIT_SECONDS:
                blocking_issue = "RUN_TIME_LIMIT_90_MINUTES"
                break
            try:
                record = generate_pilot_passage(
                    client=client,
                    ledger=ledger,
                    schedule_passage=passage_spec,
                    bank_id=bank_id,
                    batch_id="M2.0B-DEEPSEEK-PILOT",
                    max_repair_retries=2,
                )
            except DeepSeekAPIError as error:
                if error.status_code in {400, 401, 403}:
                    blocking_issue = f"DEEPSEEK_API_BLOCKING_{error.status_code}: {error}"
                    failures.append(
                        {
                            "type": passage_spec["type"],
                            "passage_group_id": passage_spec["passage_group_id"],
                            "category": "api_capability_or_auth",
                            "message": str(error),
                        }
                    )
                    break
                category, message = category_from_error(error)
                failures.append(
                    {
                        "type": passage_spec["type"],
                        "passage_group_id": passage_spec["passage_group_id"],
                        "category": category,
                        "message": message,
                    }
                )
                continue
            except (RepairExhausted, TransportRetriesExhausted, ValueError) as error:
                category, message = category_from_error(error)
                failures.append(
                    {
                        "type": passage_spec["type"],
                        "passage_group_id": passage_spec["passage_group_id"],
                        "category": category,
                        "message": message,
                    }
                )
                continue
            except CircuitOpen as error:
                blocking_issue = str(error)
                break
            except BudgetThresholdReached as error:
                blocking_issue = str(error)
                break

            with connection.transaction():
                repo.insert_passage(
                    bank_id=bank_id,
                    job_id=job["id"],
                    batch_id="M2.0B-DEEPSEEK-PILOT",
                    record=record,
                    prevalidated=True,
                )
            records.append(record)
            observations.extend(record.get("generation_observations", []))
            write_json(EVIDENCE / "output-passages.json", records)
            write_passages_markdown(records, failures)
            connection.commit()

            try:
                ledger.assert_below_threshold("pilot")
            except BudgetThresholdReached as error:
                blocking_issue = str(error)
                break

        if (
            len(failures) == len(schedule["passages"])
            and len({item["category"] for item in failures}) == 1
        ):
            blocking_issue = (
                "ALL_THREE_PASSAGES_FAILED_SAME_CLASS:"
                + failures[0]["category"]
            )

        accepted_questions = sum(
            len(record["questions"]) for record in records
        )
        total_tokens = ledger.total_tokens
        total_cost = ledger.total_cny
        extrapolations = (
            {
                str(target): {
                    "questions": target,
                    "cost_cny": round(
                        total_cost / accepted_questions * target,
                        6,
                    ),
                    "total_tokens": round(
                        total_tokens / accepted_questions * target,
                        3,
                    ),
                }
                for target in (300, 2000)
            }
            if accepted_questions
            else None
        )
        stats = request_stats(client)
        hard_gate_counts = Counter(
            failure["category"]
            for failure in failures
            if failure["category"]
            in {"word_count", "question_structure", "hard_gate"}
        )
        observation_counts = Counter(
            observation["type"] for observation in observations
        )
        status = "paused_for_owner" if records else "failed"
        with connection.transaction():
            repo.set_job_status(
                job["id"],
                status,
                checkpoint={
                    "partial_batch": True,
                    "accepted_passages": len(records),
                    "accepted_questions": accepted_questions,
                    "failed_passages": failures,
                    "blocking_issue": blocking_issue,
                },
            )
            repo.set_bank_status(
                bank_id,
                "generating",
                coverage_snapshot={
                    "question_counts": {
                        question_type: sum(
                            sum(
                                record["type"] == question_type
                                for question in record["questions"]
                            )
                            for record in records
                        )
                        for question_type in (
                            "cloze",
                            "grammar_fill",
                            "reading",
                            "gap_fill",
                        )
                    },
                    "accepted_passages": len(records),
                    "accepted_questions": accepted_questions,
                    "observations": observations,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        connection.commit()

    write_json(EVIDENCE / "output-passages.json", records)
    write_passages_markdown(records, failures)
    write_json(EVIDENCE / "generation-observations.json", observations)
    run_result = {
        "passages_ok": f"{len(records)}/3",
        "items_ok": f"{accepted_questions}/29",
        "hard_gate_drop": {
            "word_count": hard_gate_counts.get("word_count", 0),
            "question_count": hard_gate_counts.get(
                "question_structure",
                0,
            ),
            "tag": sum(
                1
                for failure in failures
                if "GRAMMAR_TAG" in failure["message"]
            ),
            "book_tag": sum(
                1
                for failure in failures
                if "BOOK_TAG" in failure["message"]
            ),
            "schema": sum(
                1
                for failure in failures
                if failure["category"] == "structure"
            ),
        },
        "observation_fail": {
            "unknown_ratio": observation_counts.get(
                "vocabulary_observation",
                0,
            ),
            "explanation_sentence_count": observation_counts.get(
                "explanation_sentence_count",
                0,
            ),
            "difficulty_schedule": observation_counts.get(
                "difficulty_schedule_mismatch",
                0,
            ),
        },
        "json_parse_fail_rate": stats["json_parse_fail_rate"],
        "structure_fail_rate": stats["structure_fail_rate"],
        "transport": contract["transport"],
        "prompt_version": contract["prompt_version"],
        "cost_cny": round(total_cost, 6),
        "extrap_300": (
            extrapolations["300"]["cost_cny"] if extrapolations else None
        ),
        "extrap_2000": (
            extrapolations["2000"]["cost_cny"] if extrapolations else None
        ),
        "duration_min": round(
            (time.perf_counter() - started_at) / 60,
            2,
        ),
        "blocking_issue": blocking_issue,
        "next": (
            "ready_for_browser_acceptance"
            if accepted_questions == 29
            else "manual_review_required"
        ),
        "failures": failures,
        "finish_reason_distribution": stats[
            "finish_reason_distribution"
        ],
        "request_count": stats["request_count"],
    }
    write_json(EVIDENCE / "run-result.json", run_result)
    print(json.dumps(run_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
