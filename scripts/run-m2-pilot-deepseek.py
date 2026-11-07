#!/usr/bin/env python3
"""Run the M2.0b DeepSeek pilot with split requests and request-level evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
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
    DeepSeekClient,
    FinishReasonError,
    RepairExhausted,
    select_v41_model_id,
)
from backend.app.m2_deepseek_pipeline import generate_pilot_passage  # noqa: E402
from backend.app.m2_pilot import (  # noqa: E402
    load_pilot_schedule,
    validate_pilot_schedule,
)
from backend.app.m2_repository import M2Repository  # noqa: E402
from backend.app.readability import flesch_reading_ease  # noqa: E402


EVIDENCE_DIR = ROOT / "qa" / "evidence" / "m2b"
BANK_NAME = "M2 Bank #2"


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


def ensure_model_id(
    contract: dict[str, Any],
    client: DeepSeekClient,
) -> tuple[str, list[dict[str, Any]]]:
    models = client.list_models()
    model_id = select_v41_model_id(models)
    contract["model_id"] = model_id
    contract["model_id_status"] = "verified_from_get_models"
    (ROOT / "contracts" / "generation-model.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return model_id, [
        {
            "id": item.get("id"),
            "object": item.get("object"),
            "owned_by": item.get("owned_by"),
        }
        for item in models
    ]


def request_summary(client: DeepSeekClient) -> dict[str, Any]:
    generation_requests = [
        item for item in client.requests if item.purpose != "ping"
    ]
    status_counts = Counter(item.status for item in generation_requests)
    finish_reasons = Counter(
        item.finish_reason or "unknown"
        for item in generation_requests
    )
    total = len(generation_requests)
    failures = sum(
        count for status, count in status_counts.items() if status != "ok"
    )
    class_rates = {
        status: round(count / total, 6) if total else 0.0
        for status, count in sorted(status_counts.items())
        if status != "ok"
    }
    return {
        "request_count": total,
        "failure_count": failures,
        "failure_rate": round(failures / total, 6) if total else 0.0,
        "status_counts": dict(sorted(status_counts.items())),
        "class_failure_rates": class_rates,
        "finish_reason_distribution": dict(sorted(finish_reasons.items())),
        "requests": [item.as_dict() for item in client.requests],
    }


def passage_cost_rows(
    ledger: CostLedger,
    client: DeepSeekClient,
    schedule: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for passage in schedule["passages"]:
        passage_type = passage["type"]
        records = [
            item
            for item in ledger.records
            if passage_type in item["purpose"]
        ]
        requests = [
            item
            for item in client.requests
            if item.purpose != "ping" and passage_type in item.purpose
        ]
        prompt_tokens = sum(item["prompt_tokens"] for item in records)
        completion_tokens = sum(item["completion_tokens"] for item in records)
        cost_cny = sum(item["cost_cny"] for item in records)
        question_count = len(passage["questions"])
        rows.append(
            {
                "type": passage_type,
                "passages": 1,
                "questions": question_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost_cny": round(cost_cny, 9),
                "elapsed_seconds": round(
                    sum(item.elapsed_seconds for item in requests),
                    6,
                ),
                "retry_count": sum(
                    1
                    for item in client.requests
                    if item.purpose != "ping"
                    and passage_type in item.purpose
                    and item.status != "ok"
                ),
                "per_question": {
                    "prompt_tokens": round(
                        prompt_tokens / question_count,
                        6,
                    ),
                    "completion_tokens": round(
                        completion_tokens / question_count,
                        6,
                    ),
                    "total_tokens": round(
                        (prompt_tokens + completion_tokens) / question_count,
                        6,
                    ),
                    "cost_cny": round(cost_cny / question_count, 9),
                },
            }
        )
    return rows


def cost_report(
    contract: dict[str, Any],
    ledger: CostLedger,
    client: DeepSeekClient,
    schedule: dict[str, Any],
    *,
    status: str,
    kind: str,
) -> dict[str, Any]:
    rows = passage_cost_rows(ledger, client, schedule)
    passed = status == "pilot_passed"
    question_count = sum(item["questions"] for item in rows) if passed else 0
    total_cost = ledger.total_cny
    per_question_cost = total_cost / question_count if question_count else None
    return {
        "kind": kind,
        "status": status,
        "provider": contract["provider"],
        "model_id": contract["model_id"],
        "prompt_version": contract["prompt_version"],
        "pricing": {
            "currency": "CNY",
            "input_per_1m_tokens": contract["price_input_per_1m_cny"],
            "output_per_1m_tokens": contract["price_output_per_1m_cny"],
            "source": contract["price_source"],
            "source_date": contract["price_source_date"],
        },
        "budget_cap_cny": contract["budget_cap_cny"],
        "totals": {
            "passages": len(schedule["passages"]),
            "accepted_passages": len(schedule["passages"]) if passed else 0,
            "questions": question_count,
            "prompt_tokens": ledger.prompt_tokens,
            "completion_tokens": ledger.completion_tokens,
            "total_tokens": ledger.total_tokens,
            "cost_cny": round(total_cost, 9),
        },
        "per_question": (
            {
                "prompt_tokens": round(
                    ledger.prompt_tokens / question_count,
                    6,
                ),
                "completion_tokens": round(
                    ledger.completion_tokens / question_count,
                    6,
                ),
                "total_tokens": round(
                    ledger.total_tokens / question_count,
                    6,
                ),
                "cost_cny": round(per_question_cost, 9),
            }
            if passed and per_question_cost is not None
            else None
        ),
        "per_passage": rows,
        "extrapolations": (
            {
                str(target): {
                    "questions": target,
                    "total_tokens": round(
                        ledger.total_tokens / question_count * target,
                        3,
                    ),
                    "cost_cny": round(per_question_cost * target, 9),
                }
                for target in (300, 2000)
            }
            if passed and per_question_cost is not None
            else None
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_request_evidence(client: DeepSeekClient) -> dict[str, Any]:
    summary = request_summary(client)
    write_json(EVIDENCE_DIR / "finish-reasons.json", summary)
    write_json(
        EVIDENCE_DIR / "gate-failures.json",
        {
            "basis": "request-level",
            "failure_rate": summary["failure_rate"],
            "status_counts": summary["status_counts"],
            "class_failure_rates": summary["class_failure_rates"],
            "failures": [
                item
                for item in summary["requests"]
                if item["status"] != "ok"
            ],
        },
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-browser-bank", action="store_true")
    args = parser.parse_args()

    contract = load_json(ROOT / "contracts" / "generation-model.json")
    if not os.getenv(contract["api_key_env"]):
        raise RuntimeError(
            f"{contract['api_key_env']} is not set; refusing to write secrets "
            "or call DeepSeek."
        )
    client = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE_DIR / "raw-responses",
    )
    model_id, model_list = ensure_model_id(contract, client)
    ping = client.ping()
    write_json(
        EVIDENCE_DIR / "api-check.json",
        {
            "model_id": model_id,
            "models_returned": model_list,
            "ping": ping,
            "api_key_source": contract["api_key_env"],
        },
    )

    schedule = load_pilot_schedule()

    ledger = CostLedger(contract)
    generated_records = []
    readability = []
    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        repo = M2Repository(connection)
        bank_row = connection.execute(
            """
            SELECT id::text AS id
            FROM question_banks
            WHERE name=%s AND status='generating'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (BANK_NAME,),
        ).fetchone()
        if not bank_row:
            raise RuntimeError("M2_BANK_2_NOT_FOUND_OR_NOT_GENERATING")
        bank_id = bank_row["id"]
        if repo.question_count(bank_id) != 0:
            raise RuntimeError("M2_BANK_2_PILOT_REQUIRES_EMPTY_BANK")
        job = repo.create_generation_job(
            bank_id,
            target_passages=47,
            batch_size=10,
            approved_by="system_owner",
            reason="M2.0b DeepSeek pilot approved",
        )
        repo.set_job_status(job["id"], "running")
        connection.commit()

        try:
            for passage_spec in schedule["passages"]:
                record = generate_pilot_passage(
                    client=client,
                    ledger=ledger,
                    schedule_passage=passage_spec,
                    max_repair_retries=contract["repair_retries_max"],
                )
                generated_records.append(record)
                readability.append(
                    {
                        "passage_group_id": record["passage_group_id"],
                        "type": record["type"],
                        "flesch_reading_ease": flesch_reading_ease(
                            record["passage"]
                        ),
                        "gate_applied": False,
                    }
                )
                report = cost_report(
                    contract,
                    ledger,
                    client,
                    schedule,
                    status="running",
                    kind="m2.0b-pilot",
                )
                report["readability"] = readability
                write_json(EVIDENCE_DIR / "generation-cost-report.json", report)
                summary = write_request_evidence(client)
                if any(
                    rate > 0.30
                    for rate in summary["class_failure_rates"].values()
                ):
                    raise RuntimeError("REQUEST_FAILURE_CLASS_OVER_30_PERCENT")
                ledger.assert_below_threshold("pilot")

            paper_check = validate_pilot_schedule(
                schedule,
                json.loads(
                    (ROOT / "config" / "generation.json").read_text(
                        encoding="utf-8"
                    )
                )["pilot"]["paper_targets"],
            )
            if not paper_check["accepted"]:
                raise RuntimeError(
                    "PILOT_PAPER_INVALID:" + ",".join(paper_check["failures"])
                )

            with connection.transaction():
                for record in generated_records:
                    repo.insert_passage(
                        bank_id=bank_id,
                        job_id=job["id"],
                        batch_id="M2.0B-DEEPSEEK-PILOT",
                        record=record,
                    )
                repo.set_job_status(
                    job["id"],
                    "paused_for_owner",
                    checkpoint={
                        "pilot_complete": True,
                        "owner_approval_required_for_scale": True,
                        "readability": readability,
                    },
                )
            connection.commit()
        except (
            BudgetThresholdReached,
            CircuitOpen,
            FinishReasonError,
            RepairExhausted,
            RuntimeError,
            ValueError,
        ) as error:
            connection.rollback()
            repo.set_job_status(
                job["id"],
                "failed",
                checkpoint={
                    "error": str(error),
                    "requests": [
                        item.as_dict() for item in client.requests
                    ],
                },
            )
            connection.commit()
            report = cost_report(
                contract,
                ledger,
                client,
                schedule,
                status="failed",
                kind="m2.0b-pilot",
            )
            report["readability"] = readability
            write_json(EVIDENCE_DIR / "generation-cost-report.json", report)
            write_request_evidence(client)
            raise

        write_json(EVIDENCE_DIR / "readability.json", readability)
        final_report = cost_report(
            contract,
            ledger,
            client,
            schedule,
            status="pilot_passed",
            kind="m2.0b-pilot",
        )
        final_report["readability"] = readability
        write_json(EVIDENCE_DIR / "generation-cost-report.json", final_report)
        write_request_evidence(client)
        counts = {
            "bank_id": bank_id,
            "question_count": repo.question_count(bank_id),
            "passage_count": connection.execute(
                "SELECT count(*) AS count FROM passages WHERE bank_id=%s",
                (bank_id,),
            ).fetchone()["count"],
            "status": repo.get_bank(bank_id)["status"],
            "job_status": repo.get_job(job["id"])["status"],
        }
        write_json(EVIDENCE_DIR / "bank2-counts.json", counts)

        if args.prepare_browser_bank:
            previous = repo.get_active_bank()
            browser_bank = repo.clone_pilot_for_browser(
                source_bank_id=bank_id,
                name=(
                    "M2.0b Browser Validation "
                    f"{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
                ),
            )
            repo.activate_bank(browser_bank["id"], actor="m2b_pilot")
            connection.commit()
            write_json(
                EVIDENCE_DIR / "browser-bank-state.json",
                {
                    "source_bank_id": bank_id,
                    "browser_bank_id": browser_bank["id"],
                    "previous_active_bank_id": (
                        previous["id"] if previous else None
                    ),
                },
            )

    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print("M2_0B_PILOT=PASS")


if __name__ == "__main__":
    main()
