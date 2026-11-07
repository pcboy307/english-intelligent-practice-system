#!/usr/bin/env python3
"""Resume the M2.0b pilot after the coverage-report crash."""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
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


def write_markdown(records: list[dict], failures: list[dict]) -> None:
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
                    *[f"- {option}" for option in question["options"]],
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
    (EVIDENCE / "passages.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    started_at = time.perf_counter()
    contract = load_json(ROOT / "contracts" / "generation-model.json")
    schedule = load_pilot_schedule()
    existing_records = json.loads(
        (EVIDENCE / "output-passages.json").read_text(encoding="utf-8")
    )
    client = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    ledger = CostLedger(contract)
    failures: list[dict] = []
    newly_generated_questions = 0
    blocking_issue = None

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        bank = connection.execute(
            """
            SELECT id::text AS id
            FROM question_banks
            WHERE name=%s AND status='generating'
            ORDER BY created_at DESC LIMIT 1
            """,
            (BANK_NAME,),
        ).fetchone()
        if not bank:
            raise RuntimeError("M2_BANK_2_NOT_FOUND_OR_NOT_GENERATING")
        bank_id = bank["id"]
        repo = M2Repository(connection)
        job_row = connection.execute(
            """
            SELECT id::text AS id
            FROM generation_jobs
            WHERE bank_id=%s AND status='running'
            ORDER BY created_at DESC LIMIT 1
            """,
            (bank_id,),
        ).fetchone()
        if not job_row:
            raise RuntimeError("RUNNING_GENERATION_JOB_NOT_FOUND")
        job_id = job_row["id"]
        existing_types = {
            row["type"]
            for row in connection.execute(
                "SELECT DISTINCT type FROM passages WHERE bank_id=%s",
                (bank_id,),
            ).fetchall()
        }

        for passage_spec in schedule["passages"]:
            if passage_spec["type"] in existing_types:
                continue
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
                        "category": (
                            "api_capability_or_auth"
                            if error.status_code in {400, 401, 403}
                            else "transport"
                        ),
                        "message": str(error),
                    }
                )
                if blocking_issue:
                    break
                continue
            except (RepairExhausted, TransportRetriesExhausted, ValueError) as error:
                message = str(error)
                category = (
                    "structure"
                    if isinstance(error, RepairExhausted)
                    else "hard_gate"
                )
                failures.append(
                    {
                        "type": passage_spec["type"],
                        "passage_group_id": passage_spec["passage_group_id"],
                        "category": category,
                        "message": message,
                    }
                )
                continue
            except (CircuitOpen, BudgetThresholdReached) as error:
                blocking_issue = str(error)
                break

            with connection.transaction():
                repo.insert_passage(
                    bank_id=bank_id,
                    job_id=job_id,
                    batch_id="M2.0B-DEEPSEEK-PILOT",
                    record=record,
                    prevalidated=True,
                )
            existing_records.append(record)
            newly_generated_questions += len(record["questions"])
            connection.commit()
            existing_types.add(passage_spec["type"])
            write_json(EVIDENCE / "output-passages.json", existing_records)
            write_markdown(existing_records, failures)

        order = {
            item["type"]: index
            for index, item in enumerate(schedule["passages"])
        }
        records = sorted(
            existing_records,
            key=lambda item: order[item["type"]],
        )
        write_json(EVIDENCE / "output-passages.json", records)
        write_markdown(records, failures)

        accepted_questions = sum(len(item["questions"]) for item in records)
        row_counts = {
            row["type"]: row["count"]
            for row in connection.execute(
                """
                SELECT type, count(*) AS count
                FROM questions WHERE bank_id=%s GROUP BY type
                """,
                (bank_id,),
            ).fetchall()
        }
        request_rows = [
            item for item in client.requests if item.purpose != "ping"
        ]
        statuses = Counter(item.status for item in request_rows)
        request_count = len(request_rows)
        json_parse_fail_rate = (
            statuses.get("json_parse_error", 0) / request_count
            if request_count
            else 0.0
        )
        structure_fail_rate = (
            statuses.get("validation_error", 0) / request_count
            if request_count
            else 0.0
        )
        observations = [
            observation
            for record in records
            for observation in record.get("generation_observations", [])
        ]
        total_cost = ledger.total_cny
        extrapolations = (
            {
                str(target): round(
                    total_cost / newly_generated_questions * target,
                    6,
                )
                for target in (300, 2000)
            }
            if newly_generated_questions
            else None
        )
        all_failed_same = (
            len(failures) == len(schedule["passages"])
            and len({item["category"] for item in failures}) == 1
        )
        if all_failed_same and not blocking_issue:
            blocking_issue = (
                "ALL_THREE_PASSAGES_FAILED_SAME_CLASS:"
                + failures[0]["category"]
            )
        job_status = "paused_for_owner" if records else "failed"
        with connection.transaction():
            repo.set_job_status(
                job_id,
                job_status,
                checkpoint={
                    "partial_batch": True,
                    "accepted_passages": len(records),
                    "accepted_questions": accepted_questions,
                    "failures": failures,
                    "blocking_issue": blocking_issue,
                },
            )
            repo.set_bank_status(
                bank_id,
                "generating",
                coverage_snapshot={
                    "question_counts": {
                        qtype: row_counts.get(qtype, 0)
                        for qtype in (
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

    result = {
        "passages_ok": f"{len(records)}/3",
        "items_ok": f"{accepted_questions}/29",
        "hard_gate_drop": {
            "word_count": sum(
                "WORD_COUNT" in item["message"] for item in failures
            ),
            "question_count": sum(
                "QUESTION_COUNT" in item["message"] for item in failures
            ),
            "tag": sum(
                "GRAMMAR_TAG" in item["message"] for item in failures
            ),
            "book_tag": sum(
                "BOOK_TAG" in item["message"] for item in failures
            ),
            "schema": sum(
                item["category"] == "structure" for item in failures
            ),
        },
        "observation_fail": {
            "unknown_ratio": sum(
                item["type"] == "vocabulary_observation"
                for item in observations
            ),
            "explanation_sentence_count": sum(
                item["type"] == "explanation_sentence_count"
                for item in observations
            ),
            "difficulty": sum(
                item["type"] == "difficulty_schedule_mismatch"
                for item in observations
            ),
        },
        "json_parse_fail_rate": round(json_parse_fail_rate, 6),
        "structure_fail_rate": round(structure_fail_rate, 6),
        "transport": contract["transport"],
        "prompt_version": contract["prompt_version"],
        "cost_cny": round(total_cost, 6),
        "cost_note": (
            "API-usage-backed for this resumed phase only; earlier-phase "
            "usage was lost before evidence persistence"
        ),
        "extrap_300": extrapolations["300"] if extrapolations else None,
        "extrap_2000": extrapolations["2000"] if extrapolations else None,
        "duration_min": round((time.perf_counter() - started_at) / 60, 2),
        "blocking_issue": blocking_issue,
        "next": (
            "ready_for_browser_acceptance"
            if accepted_questions == 29
            else "manual_review_required"
        ),
        "failures": failures,
    }
    write_json(EVIDENCE / "run-result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
