#!/usr/bin/env python3
"""Send exactly one five-question DeepSeek batch and stop on any anomaly."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.deepseek_generation import (  # noqa: E402
    CostLedger,
    DeepSeekClient,
    FinishReasonError,
)
from backend.app.m2_deepseek_pipeline import (  # noqa: E402
    _build_questions_prompt,
    _validate_question_batch,
)
from backend.app.m2_pilot import load_pilot_schedule  # noqa: E402


EVIDENCE = ROOT / "qa" / "evidence" / "m2b"
FIXED_PREVIOUS_SESSION_COUNT = 42


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    contract = load_json(ROOT / "contracts" / "generation-model.json")
    database_url = None
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            database_url = line.split("=", 1)[1].strip()
            break
    if not database_url:
        raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
        autocommit=True,
    ) as connection:
        identity = connection.execute(
            """
            SELECT inet_server_port() AS port,
                   current_database() AS database_name,
                   (SELECT count(*) FROM practice_sessions) AS session_count
            """
        ).fetchone()
        if (
            identity["port"] != 15432
            or identity["database_name"] != "english_practice"
            or identity["session_count"] < FIXED_PREVIOUS_SESSION_COUNT
        ):
            raise RuntimeError("PREFLIGHT_DATABASE_IDENTITY_OR_DATA_REGRESSION")
        write_json(
            EVIDENCE / "preflight.json",
            {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "inet_server_port": identity["port"],
                "current_database": identity["database_name"],
                "practice_sessions": identity["session_count"],
                "previous_recorded_minimum": FIXED_PREVIOUS_SESSION_COUNT,
                "passes": True,
            },
        )
        passage = connection.execute(
            """
            SELECT p.content, p.topic, p.book_source
            FROM passages p
            JOIN question_banks b ON b.id=p.bank_id
            WHERE p.type='cloze'
            ORDER BY
              CASE WHEN b.name='Demo Bank' AND b.status='active' THEN 0 ELSE 1 END,
              p.created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not passage:
            raise RuntimeError("CLOZE_SMOKE_PASSAGE_NOT_FOUND")

    schedule = load_pilot_schedule()["passages"][0]
    batch = schedule["questions"][:5]
    prompt = _build_questions_prompt(
        schedule,
        passage["content"],
        [
            {"question_order": index + 1, **assignment}
            for index, assignment in enumerate(batch)
        ],
    )
    client = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    ledger = CostLedger(contract)
    result = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": contract["model_id"],
        "thinking": contract["thinking"],
        "max_tokens": contract["max_tokens"],
        "passage_source": passage["book_source"],
        "batch_size": 5,
    }
    try:
        response = client.chat_json("smoke:questions:batch-5", prompt)
    except FinishReasonError as error:
        request = client.requests[-1]
        result.update(
            {
                "status": "failed",
                "reason": "finish_reason_length",
                "finish_reason": request.finish_reason,
                "output_tokens": request.completion_tokens,
                "input_tokens": request.prompt_tokens,
                "raw_content": error.raw_content,
                "raw_response": error.raw_response,
            }
        )
        write_json(EVIDENCE / "smoke.json", result)
        write_json(
            EVIDENCE / "smoke-length-response.json",
            {
                "raw_content": error.raw_content,
                "raw_response": error.raw_response,
            },
        )
        raise

    ledger.record(
        purpose="smoke:questions:batch-5",
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
    )
    validated = _validate_question_batch(schedule, batch, response.data)
    result.update(
        {
            "status": "passed",
            "finish_reason": response.finish_reason,
            "input_tokens": response.prompt_tokens,
            "output_tokens": response.completion_tokens,
            "cost_cny": round(ledger.total_cny, 9),
            "questions": validated,
        }
    )
    write_json(EVIDENCE / "smoke.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "finish_reason": result["finish_reason"],
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_cny": result["cost_cny"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
