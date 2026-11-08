"""Independent DeepSeek audit used by external bank imports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deepseek_generation import CostLedger, DeepSeekClient


ROOT = Path(__file__).resolve().parents[2]


def _judge_config() -> dict[str, Any]:
    base = json.loads(
        (ROOT / "contracts" / "generation-model.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        "provider": base["provider"],
        "base_url": base["base_url"],
        "model_id": base["judge_model_id"],
        "api_key_env": base["api_key_env"],
        "transport": base["transport"],
        "max_tokens": base["max_tokens"],
        "temperature": 0,
        "prompt_version": "m26-import-judge-v1",
        "price_input_per_1m_cny": base["judge_price_input_per_1m_cny"],
        "price_output_per_1m_cny": base["judge_price_output_per_1m_cny"],
        "budget_cap_cny": base["budget_cap_cny"],
        "budget_stop_ratio": 1.0,
    }


def _judge_prompt(record: dict[str, Any]) -> str:
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
- `coherent` is false if the passage is a set of unrelated sentences.
- `unique_best` is false if two or more options can fit equally well.
- For cloze, `same_part_of_speech` and `same_semantic_field` judge the four
  options. `near_synonym_distractor` is true only when a distractor has the same
  core meaning and is genuinely easy to confuse with the answer.
- For grammar_fill, `same_part_of_speech` means all options are the same grammar
  category.
- For reading, `evidence_ok` means the passage supports the answer and
  `options_rewritten` means the answer is not copied from the passage.
- For gap_fill, `unique_best` means exactly one of the seven sentences fits.
- `verdict` is `ok` only if the item is teachable and unambiguous.

Type: {record["type"]}
Topic: {record["topic"]}
Passage:
{record["passage"]}

Questions:
{json.dumps(questions, ensure_ascii=False, indent=2)}
""".strip()


def _shape_errors(data: dict[str, Any], expected_count: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(data.get("coherent"), bool):
        errors.append("JUDGE_COHERENT_NOT_BOOLEAN")
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) != expected_count:
        errors.append("JUDGE_QUESTIONS_INVALID")
        return errors
    expected = set(range(1, expected_count + 1))
    indices = [item.get("question_index") for item in questions]
    if set(indices) != expected or len(indices) != len(set(indices)):
        errors.append("JUDGE_INDEX_SET_INVALID")
    for item in questions:
        for field in (
            "unique_best",
            "answer_supported",
            "same_part_of_speech",
            "same_semantic_field",
            "near_synonym_distractor",
            "evidence_ok",
            "options_rewritten",
        ):
            if not isinstance(item.get(field), bool):
                errors.append(
                    f"JUDGE_FIELD_INVALID:{item.get('question_index')}:{field}"
                )
        if item.get("verdict") not in {"ok", "reject"}:
            errors.append(
                f"JUDGE_VERDICT_INVALID:{item.get('question_index')}"
            )
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            errors.append(
                f"JUDGE_REASON_INVALID:{item.get('question_index')}"
            )
    return errors


def audit_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        config = _judge_config()
        client = DeepSeekClient(config)
        ledger = CostLedger(config)
    except Exception as error:
        return {
            "valid": False,
            "failures": [
                {
                    "code": "SEMANTIC_AUDIT_CONFIGURATION_ERROR",
                    "message": f"{type(error).__name__}: {error}",
                }
            ],
            "judgments": [],
            "audited_passages": 0,
            "budget_cap_cny": 5.0,
            "budget_exceeded": False,
            "cost_cny": 0,
            "requests": [],
        }
    failures: list[dict[str, Any]] = []
    judgments: list[dict[str, Any]] = []
    audited_passages = 0
    halted = False
    budget_cap = float(config["budget_cap_cny"]["pilot"])
    for record in records:
        if halted:
            break
        prompt = _judge_prompt(record)
        last_errors: list[str] = []
        judgment = None
        for attempt in range(1, 3):
            retry_prompt = prompt
            if last_errors:
                retry_prompt += (
                    "\n\nFix the JSON shape errors and return the complete "
                    "object again:\n"
                    + json.dumps(last_errors, ensure_ascii=False)
                )
            try:
                response = client.chat_json(
                    f"import-judge:{record['passage_group_id']}:attempt-{attempt}",
                    retry_prompt,
                )
            except Exception as error:
                failures.append(
                    {
                        "code": "SEMANTIC_AUDIT_REQUEST_FAILED",
                        "passage_id": record["passage_group_id"],
                        "message": f"{type(error).__name__}: {error}",
                    }
                )
                halted = True
                break
            ledger.record(
                purpose=f"import-judge:{record['passage_group_id']}",
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )
            if ledger.total_cny >= budget_cap:
                failures.append(
                    {
                        "code": "SEMANTIC_AUDIT_BUDGET_EXCEEDED",
                        "message": (
                            "Semantic audit reached the single-run budget "
                            f"of CNY {budget_cap:.2f}; import was not written."
                        ),
                        "cost_cny": round(ledger.total_cny, 6),
                    }
                )
                halted = True
                break
            last_errors = _shape_errors(
                response.data,
                len(record["questions"]),
            )
            if not last_errors:
                judgment = response.data
                break
        if halted:
            break
        if judgment is None:
            failures.append(
                {
                    "code": "JUDGE_STRUCTURE_EXHAUSTED",
                    "passage_id": record["passage_group_id"],
                    "errors": last_errors,
                }
            )
            continue
        audited_passages += 1
        judgments.append(
            {
                "passage_group_id": record["passage_group_id"],
                "judgment": judgment,
            }
        )
        if not judgment["coherent"]:
            failures.append(
                {
                    "code": "R8_PASSAGE_NOT_COHERENT",
                    "passage_id": record["passage_group_id"],
                }
            )
        near_synonyms = 0
        for item in judgment["questions"]:
            index = item["question_index"]
            prefix = {
                "passage_id": record["passage_group_id"],
                "question_index": index,
            }
            if not item["unique_best"]:
                failures.append({"code": "R9_NO_CLEAR_BEST", **prefix})
            if not item["answer_supported"]:
                failures.append({"code": "ANSWER_UNSUPPORTED", **prefix})
            if item["verdict"] != "ok":
                failures.append({"code": "JUDGE_REJECTED", **prefix})
            if record["type"] == "cloze":
                if not item["same_part_of_speech"]:
                    failures.append({"code": "R13_POS_MISMATCH", **prefix})
                if not item["same_semantic_field"]:
                    failures.append({"code": "R13_SEMANTIC_FIELD", **prefix})
                if item["near_synonym_distractor"]:
                    near_synonyms += 1
            if record["type"] == "reading":
                if not item["evidence_ok"]:
                    failures.append({"code": "R14_EVIDENCE_REJECTED", **prefix})
                if not item["options_rewritten"]:
                    failures.append(
                        {"code": "R14_OPTION_NOT_REWRITTEN", **prefix}
                    )
        if record["type"] == "cloze" and near_synonyms < 2:
            failures.append(
                {
                    "code": "R13_NEAR_SYNONYM_DISTRACTORS_TOO_FEW",
                    "passage_id": record["passage_group_id"],
                }
            )
    return {
        "valid": not failures,
        "failures": failures,
        "judgments": judgments,
        "audited_passages": audited_passages,
        "budget_cap_cny": budget_cap,
        "budget_exceeded": any(
            failure["code"] == "SEMANTIC_AUDIT_BUDGET_EXCEEDED"
            for failure in failures
        ),
        "cost_cny": round(ledger.total_cny, 6),
        "requests": [request.as_dict() for request in client.requests],
    }
