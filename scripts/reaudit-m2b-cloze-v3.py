#!/usr/bin/env python3
"""Re-run strict H10/H11 auditing without regenerating cloze content."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.deepseek_generation import CostLedger, DeepSeekClient  # noqa: E402


def load_rewriter():
    path = ROOT / "scripts" / "rewrite-m2b-cloze-v3.py"
    spec = importlib.util.spec_from_file_location(
        "rewrite_m2b_cloze_v3",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("CLOZE_REWRITER_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    rewriter = load_rewriter()
    evidence_path = (
        ROOT / "qa" / "evidence" / "m2b" / "cloze-rewrite-v3.json"
    )
    evidence = rewriter.load_json(evidence_path)
    record = evidence["record"]
    questions = record["questions"]
    contract = rewriter.load_json(
        ROOT / "contracts" / "generation-model.json"
    )
    judge_contract = {
        **contract,
        "model_id": contract["judge_model_id"],
        "prompt_version": "m2-cloze-judge-v2",
        "price_input_per_1m_cny": contract["judge_price_input_per_1m_cny"],
        "price_output_per_1m_cny": contract["judge_price_output_per_1m_cny"],
        "max_tokens": 8192,
    }
    judge_client = DeepSeekClient(
        judge_contract,
        raw_output_dir=(
            ROOT / "qa" / "evidence" / "m2b" / "raw-responses-v3"
        ),
    )
    judge_ledger = CostLedger(judge_contract)
    try:
        audit = rewriter.audit_with_pro(
            judge_client=judge_client,
            judge_ledger=judge_ledger,
            passage=record["passage"],
            questions=questions,
        )
    except Exception as error:
        rewriter.write_json(
            ROOT / "qa" / "evidence" / "m2b" / "cloze-reaudit-v2.json",
            {
                "status": "failed",
                "reason": str(error),
                "judge_requests": [
                    item.as_dict() for item in judge_client.requests
                ],
                "cost_cny": judge_ledger.total_cny,
            },
        )
        raise

    old_cost = evidence.get("cost_cny", {})
    new_cost = {
        **old_cost,
        "judge": round(
            float(old_cost.get("judge", 0.0)) + judge_ledger.total_cny,
            9,
        ),
    }
    new_cost["total"] = round(
        float(new_cost["generator"]) + float(new_cost["judge"]),
        9,
    )
    evidence["cross_audit"] = list(audit.values())
    evidence["cost_cny"] = new_cost
    evidence["reaudit"] = {
        "prompt_version": judge_contract["prompt_version"],
        "status": "passed",
        "judge_requests": [
            item.as_dict() for item in judge_client.requests
        ],
        "cost_cny": round(judge_ledger.total_cny, 9),
    }
    rewriter.write_json(evidence_path, evidence)
    rewriter.write_markdown(
        ROOT / "qa" / "evidence" / "m2b" / "cloze-rewrite-v3.md",
        evidence,
    )
    rewriter.write_json(
        ROOT / "qa" / "evidence" / "m2b" / "cloze-reaudit-v2.json",
        {
            "status": "passed",
            "prompt_version": judge_contract["prompt_version"],
            "cross_audit": list(audit.values()),
            "judge_requests": [
                item.as_dict() for item in judge_client.requests
            ],
            "cost_cny": round(judge_ledger.total_cny, 9),
        },
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "items": len(audit),
                "cost_cny": round(judge_ledger.total_cny, 9),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
