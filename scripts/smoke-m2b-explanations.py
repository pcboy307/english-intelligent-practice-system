#!/usr/bin/env python3
"""Send exactly one ten-explanation DeepSeek batch."""

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
    DeepSeekAPIError,
    DeepSeekClient,
    FinishReasonError,
)
from backend.app.m2_deepseek_pipeline import (  # noqa: E402
    GENERATION_BATCH_SCHEMA,
    _build_explanations_prompt,
    _validate_explanation_batch,
)


EVIDENCE = ROOT / "qa" / "evidence" / "m2b"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "generation-model.json").read_text(
            encoding="utf-8"
        )
    )
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
        group = connection.execute(
            """
            SELECT p.bank_id, p.passage_group_id, p.content
            FROM passages p
            JOIN question_banks b ON b.id=p.bank_id
            WHERE p.type='cloze' AND b.status='active'
            ORDER BY p.created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not group:
            raise RuntimeError("ACTIVE_CLOZE_PASSAGE_NOT_FOUND")
        rows = connection.execute(
            """
            SELECT q.stem, q.options, q.answer
            FROM questions q
            WHERE q.bank_id=%s AND q.passage_group_id=%s
            ORDER BY q.id
            LIMIT 10
            """,
            (group["bank_id"], group["passage_group_id"]),
        ).fetchall()
        if len(rows) != 10:
            raise RuntimeError("SMOKE_REQUIRES_TEN_EXISTING_QUESTIONS")

    questions = [
        {
            "stem": row["stem"],
            "options": row["options"],
            "answer": row["answer"],
        }
        for row in rows
    ]
    prompt = _build_explanations_prompt(group["content"], questions)
    client = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    ledger = CostLedger(contract)
    result = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": contract["model_id"],
        "transport": contract["transport"],
        "prompt_version": contract["prompt_version"],
        "thinking": contract["thinking"],
        "max_tokens": contract["max_tokens"],
        "batch_size": 10,
        "passage_group_id": group["passage_group_id"],
    }
    try:
        response = client.chat_json(
            "smoke:explanations:batch-10",
            prompt,
            response_schema=GENERATION_BATCH_SCHEMA,
        )
    except FinishReasonError as error:
        request = client.requests[-1]
        result.update(
            {
                "status": "failed",
                "reason": "finish_reason_length",
                "finish_reason": request.finish_reason,
                "input_tokens": request.prompt_tokens,
                "output_tokens": request.completion_tokens,
                "raw_content": error.raw_content,
                "raw_response": error.raw_response,
                "request_id": request.request_id,
                "cost_cny": request.cost_cny,
            }
        )
        write_json(EVIDENCE / "smoke-explanations.json", result)
        raise
    except DeepSeekAPIError as error:
        request = client.requests[-1]
        result.update(
            {
                "status": "failed",
                "reason": "deepseek_api_error",
                "error": str(error),
                "request_id": request.request_id,
                "input_tokens": request.prompt_tokens,
                "output_tokens": request.completion_tokens,
                "cost_cny": request.cost_cny,
            }
        )
        write_json(EVIDENCE / "smoke-explanations.json", result)
        raise

    try:
        explanations = _validate_explanation_batch(
            list(range(1, 11)),
            response.data,
        )
    except ValueError as error:
        request = client.requests[-1]
        result.update(
            {
                "status": "failed",
                "reason": "contract_validation_error",
                "error": str(error),
                "finish_reason": response.finish_reason,
                "input_tokens": response.prompt_tokens,
                "output_tokens": response.completion_tokens,
                "request_id": request.request_id,
                "cost_cny": request.cost_cny,
            }
        )
        write_json(EVIDENCE / "smoke-explanations.json", result)
        raise

    ledger.record(
        purpose="smoke:explanations:batch-10",
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
    )
    result.update(
        {
            "status": "passed",
            "finish_reason": response.finish_reason,
            "input_tokens": response.prompt_tokens,
            "output_tokens": response.completion_tokens,
            "cost_cny": round(ledger.total_cny, 9),
            "explanations": explanations,
        }
    )
    write_json(EVIDENCE / "smoke-explanations.json", result)
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
