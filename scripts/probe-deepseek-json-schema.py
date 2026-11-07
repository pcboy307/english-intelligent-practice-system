#!/usr/bin/env python3
"""Probe whether deepseek-v4-pro supports server-side json_schema output."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.deepseek_generation import (  # noqa: E402
    DeepSeekAPIError,
    DeepSeekClient,
)


EVIDENCE = ROOT / "qa" / "evidence" / "m2b"


def main() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "generation-model.json").read_text(
            encoding="utf-8"
        )
    )
    config = {
        **contract,
        "model_id": "deepseek-v4-pro",
        "transport": "json_schema",
    }
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    client = DeepSeekClient(
        config,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    result = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": "deepseek-v4-pro",
        "transport": "json_schema",
        "prompt_version": contract["prompt_version"],
    }
    try:
        response = client.chat_json(
            "probe:json-schema",
            'Return JSON matching {"ok": true}.',
            max_tokens=100,
            response_schema=schema,
        )
    except DeepSeekAPIError as error:
        request = client.requests[-1]
        result.update(
            {
                "status": "unsupported",
                "http_status": error.status_code,
                "error": error.message,
                "request_id": request.request_id,
                "cost_cny": request.cost_cny,
            }
        )
    else:
        result.update(
            {
                "status": "supported",
                "finish_reason": response.finish_reason,
                "request_id": response.request_id,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "output": response.data,
                "cost_cny": client.requests[-1].cost_cny,
            }
        )
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "v4-pro-json-schema-probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "supported":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
