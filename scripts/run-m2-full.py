#!/usr/bin/env python3
"""Generate and persist the M2 47-passage / 300-question bank."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.cloze_quality import validate_cross_audit  # noqa: E402
from backend.app.deepseek_generation import (  # noqa: E402
    BudgetThresholdReached,
    CircuitOpen,
    CostLedger,
    DeepSeekAPIError,
    DeepSeekClient,
    RepairExhausted,
    TransportRetriesExhausted,
    run_repair_loop,
)
from backend.app.generation import (  # noqa: E402
    load_curriculum,
    validate_generated_passage,
)
from backend.app.m2_deepseek_pipeline import validate_pilot_record  # noqa: E402
from backend.app.m2_repository import M2Repository  # noqa: E402
from backend.app.question_quality import (  # noqa: E402
    validate_cloze_options,
    validate_reading_question_type,
)


EVIDENCE = ROOT / "qa" / "evidence" / "m2"
SCHEDULE_PATH = ROOT / "config" / "m2-full-schedule.json"
RUN_COST_CAP = 5.0
RUN_SECONDS = 180 * 60
WORKERS = 4
BATCH_SIZE = 12
BATCH_ID = "M2-FULL-GENERATION-V1"
_cost_lock = threading.Lock()
_total_cost = 0.0
_BASIC_WORDS: tuple[str, ...] | None = None


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


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


def sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+", text)
        if item.strip()
    ]


def reading_options_with_letters(options: list[str]) -> list[tuple[str, str]]:
    return [
        (chr(65 + index), value.strip())
        for index, value in enumerate(options)
    ]


def explanation_has_two_distractors(
    question: dict[str, Any],
    question_type: str,
) -> bool:
    explanation = str(question.get("explanation", "")).strip()
    parts = [
        item.strip()
        for item in re.split(r"[。！？]+", explanation)
        if item.strip()
    ]
    last = parts[-1] if parts else ""
    options = question.get("options") or []
    answer = str(question.get("answer", "")).strip()
    if question_type == "gap_fill":
        distractors = [
            letter
            for letter, _text in reading_options_with_letters(options)
            if letter != answer.upper()
        ]
        return sum(
            re.search(rf"\b{re.escape(letter)}\b", explanation) is not None
            for letter in distractors
        ) >= 2
    distractors = [
        option
        for option in options
        if str(option).casefold() != answer.casefold()
    ]
    return sum(
        str(option).casefold() in explanation.casefold()
        for option in distractors
    ) >= 2


def ensure_distractor_explanation(
    question: dict[str, Any],
    question_type: str,
) -> None:
    options = question.get("options") or []
    answer = str(question.get("answer", "")).strip()
    if question_type == "gap_fill":
        distractors = [
            letter
            for letter, _text in reading_options_with_letters(options)
            if letter != answer.upper()
        ][:2]
        note = (
            f"主要干扰项 {distractors[0]} 和 {distractors[1]} "
            "均无法与前后句形成连贯的语义衔接。"
        )
    else:
        distractors = [
            str(option)
            for option in options
            if str(option).casefold() != answer.casefold()
        ][:2]
        note = (
            f"主要干扰项 {distractors[0]} 和 {distractors[1]} "
            "分别造成语义偏移，均与空格所在句及前后文逻辑不符。"
        )
    explanation = str(question["explanation"]).rstrip()
    if not explanation.endswith(("。", "！", "？", ".", "!", "?")):
        explanation += "。"
    question["explanation"] = explanation + note


def proper_name_tokens(passage: str) -> set[str]:
    sentence_starts = {
        match.start(1)
        for match in re.finditer(r"(?:^|(?<=[.!?])\s+)([A-Za-z][A-Za-z'-]*)", passage)
    }
    occurrences: dict[str, list[int]] = {}
    for match in re.finditer(r"\b[A-Z][A-Za-z'-]*\b", passage):
        token = match.group(0)
        if token.isupper():
            continue
        occurrences.setdefault(token.casefold(), []).append(match.start())
    return {
        token
        for token, positions in occurrences.items()
        if any(position not in sentence_starts for position in positions)
        or len(positions) >= 2
    }


def gloss_unknown_terms(
    *,
    record: dict[str, Any],
    client: DeepSeekClient,
    ledger: CostLedger,
) -> dict[str, Any]:
    report = validate_generated_passage(record)
    proper_names = proper_name_tokens(record["passage"])
    unknown = sorted(
        {
            item.casefold()
            for item in report.metrics.get("unknown_words", [])
            if item.casefold().removesuffix("'s") not in proper_names
        }
    )
    if not unknown:
        return record
    response = run_repair_loop(
        client=client,
        ledger=ledger,
        purpose=f"gloss:{record['passage_group_id']}",
        prompt=f"""
Translate these English words into one to four Chinese characters each.
Return JSON only as {{"translations": {{"word": "中文释义"}}}}.
Include every key exactly once.
Words:
{json.dumps(unknown, ensure_ascii=False)}
""".strip(),
        validate=lambda data: (
            data
            if isinstance(data.get("translations"), dict)
            and all(
                word in data["translations"]
                and isinstance(data["translations"][word], str)
                and data["translations"][word].strip()
                for word in unknown
            )
            else (_ for _ in ()).throw(
                ValueError("GLOSS_TRANSLATIONS_INVALID")
            )
        ),
        max_repair_retries=1,
    )
    replacements = {
        word: f"{word}（{response['translations'][word].strip()}）"
        for word in unknown
    }

    def apply(text: str | None) -> str | None:
        if not isinstance(text, str):
            return text
        result = text
        for word, replacement in replacements.items():
            result = re.sub(
                rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])",
                replacement,
                result,
                flags=re.IGNORECASE,
            )
        return result

    record["passage"] = apply(record["passage"])
    for question in record["questions"]:
        for field in (
            "stem",
            "explanation",
            "evidence_sentence",
            "context_clue",
            "clue_argument",
        ):
            if field in question:
                question[field] = apply(question[field])
        question["knowledge_points"] = [
            apply(point) for point in question.get("knowledge_points", [])
        ]
    return record


def generation_prompt(spec: dict[str, Any]) -> str:
    global _BASIC_WORDS
    if _BASIC_WORDS is None:
        whitelist = load_json(
            ROOT / "contracts" / "vocabulary-whitelist.json"
        )
        _BASIC_WORDS = tuple(
            sorted(
                entry["word"].lower()
                for entry in whitelist["entries"]
                if entry["word"].islower()
                and not entry.get("closed_class")
                and any(
                    str(source).startswith("课程标准2022")
                    for source in entry.get("sources", [])
                )
            )
        )
    return f"""
Create one high-school English {spec["type"]} passage and its questions.
Return JSON only. Never use Markdown fences.

Return this shape:
{{
  "passage": "complete passage",
  "questions": [
    {{
      "question_index": 1,
      "stem": "question stem",
      "options": ["...", "..."],
      "answer": "exact option text, or A-G for gap_fill",
      "explanation": "Chinese explanation",
      "evidence_sentence": "exact passage substring for reading",
      "context_clue": "exact passage sentence for cloze",
      "clue_argument": "short reason for cloze"
    }}
  ]
}}

Type: {spec["type"]}
Topic: {spec["topic"]}
Question count: {len(spec["questions"])}
Assignments:
{json.dumps(spec["questions"], ensure_ascii=False, indent=2)}

Rules:
- Return exactly the requested number of questions in order.
- All cloze and grammar answers must exactly equal one option.
- Gap-fill answers are one letter A-G; every gap-fill question repeats the same
  seven sentence options.
- Cloze: 170-220 words, one coherent narrative about at most three recurring
  people, with a timeline and causal links. Do not create unrelated example
  sentences. Every answer is the assigned single content word. Four options are
  four different words of the same part of speech, not morphology variants, and
  no option lemma appears in its stem.
- Grammar fill: 120-180 words with circled blanks ①-⑩, exactly four options per
  blank in the same grammatical category.
- Reading: no more than 250 words. Every question must be comprehension-based:
  main idea, detail, inference, vocabulary in context, or purpose/attitude.
  Never ask about grammar structures. evidence_sentence must be copied verbatim
  from the passage and support the answer.
- Gap fill: no more than 220 words with blanks (1)-(5), seven mutually
  distinguishable complete-sentence options of at least five words each, and
  one best option per blank. Never use single words, verb forms, or grammar
  variants as the seven options.
- R10: every explanation must end with one Chinese sentence that explicitly
  explains why two major distractors are wrong. For gap fill, name two wrong
  option letters.
- Keep the JSON compact enough to finish within the output limit.
- The passage may only use the following curriculum vocabulary plus standard
  function words and proper names. Do not use other advanced vocabulary.
  If a necessary topic word is outside the list, write it once with a short
  Chinese gloss, for example `platform（平台）`.
  Do not invent personal names; use roles such as "the student", "her teacher",
  and "a classmate".
{", ".join(_BASIC_WORDS)}

Write the passage and design all blanks together; never take a pre-existing text
and remove words afterward.
""".strip()


def materialize_record(
    spec: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list):
        raise ValueError("QUESTIONS_ARRAY_MISSING")
    if len(raw_questions) != len(spec["questions"]):
        raise ValueError(
            f"QUESTION_COUNT_MISMATCH actual={len(raw_questions)} "
            f"expected={len(spec['questions'])}"
        )
    questions = []
    for index, (raw, assignment) in enumerate(
        zip(raw_questions, spec["questions"], strict=True),
        start=1,
    ):
        if not isinstance(raw, dict):
            raise ValueError(f"QUESTION_NOT_OBJECT index={index}")
        options = raw.get("options")
        answer = raw.get("answer")
        stem = raw.get("stem")
        explanation = raw.get("explanation")
        if not isinstance(stem, str) or not stem.strip():
            raise ValueError(f"QUESTION_STEM_INVALID index={index}")
        if not isinstance(options, list) or not options:
            raise ValueError(f"QUESTION_OPTIONS_INVALID index={index}")
        if any(not isinstance(option, str) or not option.strip() for option in options):
            raise ValueError(f"QUESTION_OPTIONS_INVALID index={index}")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"QUESTION_ANSWER_INVALID index={index}")
        if spec["type"] != "gap_fill" and answer not in options:
            raise ValueError(f"ANSWER_NOT_IN_OPTIONS index={index}")
        if spec["type"] == "gap_fill" and answer.upper() not in set("ABCDEFG"):
            raise ValueError(f"GAP_ANSWER_INVALID index={index}")
        if not isinstance(explanation, str) or not explanation.strip():
            raise ValueError(f"EXPLANATION_MISSING index={index}")
        metadata = ["m2:提分优先"]
        if spec["type"] == "cloze":
            metadata.extend(
                [
                    f"cloze_target:{assignment['cloze_target']}",
                    str(raw.get("context_clue", "")),
                    str(raw.get("clue_argument", "")),
                ]
            )
        elif spec["type"] == "grammar_fill":
            metadata.append(
                f"grammar:{assignment['grammar_tags'][0]}"
            )
        elif spec["type"] == "reading":
            evidence = raw.get("evidence_sentence")
            if not isinstance(evidence, str) or evidence.strip() not in data["passage"]:
                raise ValueError(
                    f"R5_EVIDENCE_SENTENCE_INVALID index={index}"
                )
            metadata.extend(
                [
                    f"reading_type:{assignment['reading_type']}",
                    f"evidence_sentence:{evidence.strip()}",
                ]
            )
        else:
            metadata.append(
                f"gap_fill_{assignment['cohesion_type']}"
            )
        question = {
            "stem": stem.strip(),
            "options": [option.strip() for option in options],
            "answer": answer.strip(),
            "explanation": explanation.strip(),
            "knowledge_points": list(dict.fromkeys(metadata)),
            "grammar_tags": list(assignment["grammar_tags"]),
            "book_source": assignment["book_source"],
            "difficulty": assignment["difficulty"],
            "evidence_sentence": raw.get("evidence_sentence"),
            "context_clue": raw.get("context_clue"),
            "clue_argument": raw.get("clue_argument"),
        }
        ensure_distractor_explanation(question, spec["type"])
        questions.append(question)
    record = {
        "type": spec["type"],
        "passage_group_id": spec["passage_group_id"],
        "topic": spec["topic"],
        "book_source": spec["book_source"],
        "difficulty": spec["difficulty"],
        "passage": str(data.get("passage", "")),
        "questions": questions,
    }
    return record


def validate_record(
    spec: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    report = validate_pilot_record(
        record,
        spec,
        bank_id="00000000-0000-4000-8000-000000000000",
        batch_id=BATCH_ID,
    )
    failures = list(report["hard_failures"])
    metrics = report["metrics"]
    proper_names = proper_name_tokens(record["passage"])
    unknown_terms = [
        item
        for item in metrics.get("unknown_words", [])
        if item.casefold().removesuffix("'s") not in proper_names
    ]
    if unknown_terms:
        failures.append(
            {
                "category": "R6_vocabulary_scope",
                "unknown_words": unknown_terms,
            }
        )
    for index, question in enumerate(record["questions"], start=1):
        if spec["type"] == "gap_fill":
            short_options = [
                option
                for option in question["options"]
                if len(option.split()) < 3
            ]
            if short_options:
                failures.append(
                    {
                        "category": "GAP_OPTIONS_MUST_BE_SENTENCES",
                        "question_index": index,
                        "options": short_options,
                    }
                )
        if spec["type"] == "cloze":
            failures.extend(
                {
                    "question_index": index,
                    **failure,
                }
                for failure in validate_cloze_options(
                    stem=question["stem"],
                    options=question["options"],
                    answer=question["answer"],
                )
            )
        if spec["type"] == "reading":
            failures.extend(
                {
                    "question_index": index,
                    **failure,
                }
                for failure in validate_reading_question_type(
                    question["stem"]
                )
            )
        if not explanation_has_two_distractors(question, spec["type"]):
            failures.append(
                {
                    "category": "R10_DISTRACTOR_EXPLANATION_MISSING",
                    "question_index": index,
                }
            )
    if spec["type"] == "cloze":
        expected = [
            item["cloze_target"] for item in spec["questions"]
        ]
        actual = [question["answer"] for question in record["questions"]]
        if [item.casefold() for item in expected] != [
            item.casefold() for item in actual
        ]:
            failures.append(
                {
                    "category": "HIGH_FREQUENCY_TARGET_MISMATCH",
                    "expected": expected,
                    "actual": actual,
                }
            )
    if failures:
        raise ValueError(
            "M2_RECORD_GATE_FAILED "
            + json.dumps(failures, ensure_ascii=False)
        )
    record["validation"] = {
        "word_count": metrics["word_count"],
        "unknown_words": metrics["unknown_words"],
        "vocabulary_resolutions": metrics["vocabulary_resolutions"],
        "flesch_reading_ease": report["flesch_reading_ease"],
    }
    return record


def audit_prompt(record: dict[str, Any]) -> str:
    questions = []
    for index, question in enumerate(record["questions"], start=1):
        questions.append(
            {
                "question_index": index,
                "stem": question["stem"],
                "options": question["options"],
                "answer": question["answer"],
                "explanation": question["explanation"],
                "context_clue": question.get("context_clue"),
                "evidence_sentence": question.get("evidence_sentence"),
            }
        )
    return f"""
Review this high-school English passage and every item independently.
Return JSON only:
{{
  "coherent": true,
  "coherence_reason": "one sentence",
  "questions": [
    {{
      "question_index": 1,
      "clear_best": true,
      "best_option": "exact option text or A-G",
      "reason": "one sentence",
      "direct_lexical_leak": false,
      "distractors_plausible": true
    }}
  ]
}}

R8: judge whether the passage is one coherent connected text or assembled
unrelated sentences. Set coherent=false for sentence assembly.
R9: decide whether one option is clearly better for the blank/question. Set
clear_best=false when two or more choices are equally defensible.
For cloze, set direct_lexical_leak=true if context_clue directly supplies a
synonym, antonym, or same-root form of the answer. This is observation-only; do
not use it as a rejection reason.
Set distractors_plausible=false if a distractor is an obvious unrelated filler.

Type: {record["type"]}
Passage:
{record["passage"]}

Questions:
{json.dumps(questions, ensure_ascii=False, indent=2)}
""".strip()


def validate_audit(
    record: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(data.get("coherent"), bool):
        raise ValueError("R8_COHERENCE_RESULT_MISSING")
    if not data["coherent"]:
        raise ValueError(
            "R8_PASSAGE_NOT_COHERENT "
            + str(data.get("coherence_reason", ""))
        )
    items = data.get("questions")
    if not isinstance(items, list) or len(items) != len(record["questions"]):
        raise ValueError("AUDIT_QUESTION_COUNT_MISMATCH")
    by_index = {
        item.get("question_index"): item
        for item in items
        if isinstance(item, dict)
    }
    expected = set(range(1, len(record["questions"]) + 1))
    if set(by_index) != expected:
        raise ValueError(
            f"AUDIT_INDEX_SET_MISMATCH expected={sorted(expected)} "
            f"actual={sorted(by_index)}"
        )
    failures = []
    for index, question in enumerate(record["questions"], start=1):
        item = by_index[index]
        answer = str(question["answer"])
        if item.get("clear_best") is not True:
            failures.append(
                {
                    "question_index": index,
                    "code": "R9_NO_CLEAR_BEST",
                    "reason": item.get("reason"),
                }
            )
        if str(item.get("best_option", "")).casefold() != answer.casefold():
            failures.append(
                {
                    "question_index": index,
                    "code": "R9_BEST_OPTION_MISMATCH",
                    "expected": answer,
                    "actual": item.get("best_option"),
                }
            )
        if item.get("distractors_plausible") is not True:
            failures.append(
                {
                    "question_index": index,
                    "code": "DISTRACTOR_OBVIOUS_FILLER",
                    "reason": item.get("reason"),
                }
            )
    if failures:
        raise ValueError(
            "M2_PRO_AUDIT_FAILED "
            + json.dumps(failures, ensure_ascii=False)
        )
    return data


def run_one(
    spec: dict[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    contract = load_json(ROOT / "contracts" / "generation-model.json")
    flash = DeepSeekClient(
        contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    judge_contract = {
        **contract,
        "model_id": contract["judge_model_id"],
        "prompt_version": "m2-full-judge-v1",
        "price_input_per_1m_cny": contract["judge_price_input_per_1m_cny"],
        "price_output_per_1m_cny": contract["judge_price_output_per_1m_cny"],
    }
    judge = DeepSeekClient(
        judge_contract,
        raw_output_dir=EVIDENCE / "raw-responses",
    )
    flash_ledger = CostLedger(contract)
    judge_ledger = CostLedger(judge_contract)

    def generate_and_validate(data: dict[str, Any]) -> dict[str, Any]:
        record = materialize_record(spec, data)
        record = gloss_unknown_terms(
            record=record,
            client=flash,
            ledger=flash_ledger,
        )
        record = validate_record(spec, record)
        audit = run_repair_loop(
            client=judge,
            ledger=judge_ledger,
            purpose=f"audit:{spec['type']}:{spec['passage_group_id']}",
            prompt=audit_prompt(record),
            validate=lambda audit_data: validate_audit(record, audit_data),
            max_repair_retries=0,
        )
        record["pro_audit"] = audit
        return record

    record = run_repair_loop(
        client=flash,
        ledger=flash_ledger,
        purpose=f"generate:{spec['type']}:{spec['passage_group_id']}",
        prompt=generation_prompt(spec),
        validate=generate_and_validate,
        max_repair_retries=2,
    )
    cost = flash_ledger.total_cny + judge_ledger.total_cny
    with _cost_lock:
        global _total_cost
        _total_cost += cost
    return {
        "index": index,
        "record": record,
        "cost_cny": cost,
        "flash_requests": [item.as_dict() for item in flash.requests],
        "judge_requests": [item.as_dict() for item in judge.requests],
    }


def failure_category(error: Exception) -> str:
    message = str(error)
    if isinstance(error, DeepSeekAPIError):
        return f"api_{error.status_code}"
    if isinstance(error, TransportRetriesExhausted):
        return "transport"
    if isinstance(error, CircuitOpen):
        return "circuit_open"
    if isinstance(error, BudgetThresholdReached):
        return "budget"
    for code in (
        "R5_",
        "R6_",
        "R8_",
        "R9_",
        "R10_",
        "WORD_COUNT",
        "QUESTION_COUNT",
        "HIGH_FREQUENCY",
        "SCHEMA",
    ):
        if code in message:
            return code.rstrip("_")
    return "content"


def fill_records(
    specs: list[dict[str, Any]],
    existing_records: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = list(existing_records or [])
    completed_ids = {
        item["record"]["passage_group_id"] for item in records
    }
    specs = [
        spec
        for spec in specs
        if spec["passage_group_id"] not in completed_ids
    ]
    failures = []
    started = time.perf_counter()
    for start in range(0, len(specs), BATCH_SIZE):
        batch = specs[start : start + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {
                executor.submit(run_one, spec, index=start + offset): spec
                for offset, spec in enumerate(batch)
            }
            for future in as_completed(futures):
                spec = futures[future]
                try:
                    result = future.result()
                except (
                    DeepSeekAPIError,
                    RepairExhausted,
                    TransportRetriesExhausted,
                    CircuitOpen,
                    BudgetThresholdReached,
                    ValueError,
                ) as error:
                    failures.append(
                        {
                            "passage_group_id": spec["passage_group_id"],
                            "type": spec["type"],
                            "category": failure_category(error),
                            "message": str(error),
                        }
                    )
                    if (
                        isinstance(error, DeepSeekAPIError)
                        and error.status_code in {400, 401, 403}
                    ):
                        raise RuntimeError(
                            f"BLOCKING_API_{error.status_code}"
                        ) from error
                    continue
                records.append(result)
        write_json(
            EVIDENCE / "run-checkpoint.json",
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "records": sorted(records, key=lambda item: item["index"]),
                "failures": failures,
                "total_cost_cny": round(_total_cost, 6),
            },
        )
        if _total_cost >= RUN_COST_CAP:
            raise RuntimeError(f"RUN_COST_CAP_REACHED {_total_cost:.6f}")
        if time.perf_counter() - started >= RUN_SECONDS:
            raise RuntimeError("RUN_TIME_LIMIT_REACHED")
        if failures and len(failures) == len(specs) and len(
            {item["category"] for item in failures}
        ) == 1:
            raise RuntimeError(
                "ALL_PASSAGES_FAILED_SAME_CLASS "
                + failures[0]["category"]
            )
    return records, failures


def replace_bank(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) != 47:
        raise RuntimeError(f"PASSAGE_COUNT_NOT_47 actual={len(records)}")
    expected_questions = sum(len(item["record"]["questions"]) for item in records)
    if expected_questions != 300:
        raise RuntimeError(
            f"QUESTION_COUNT_NOT_300 actual={expected_questions}"
        )
    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
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
        previous_active = connection.execute(
            """
            SELECT qb.id::text AS id
            FROM bank_active_state bas
            JOIN question_banks qb ON qb.id=bas.active_bank_id
            """
        ).fetchone()
        existing_jobs = connection.execute(
            """
            SELECT id::text AS id
            FROM generation_jobs
            WHERE bank_id=%s
              AND status IN (
                'queued','running','paused_for_review','paused_for_owner'
              )
            """,
            (bank["id"],),
        ).fetchall()
        for job in existing_jobs:
            connection.execute(
                """
                UPDATE generation_jobs
                SET status='failed', updated_at=now(), finished_at=now()
                WHERE id=%s
                """,
                (job["id"],),
            )
        # The old 29 items are rejected pilot artifacts. Replace them atomically.
        connection.execute(
            "DELETE FROM questions WHERE bank_id=%s",
            (bank["id"],),
        )
        connection.execute(
            "DELETE FROM passages WHERE bank_id=%s",
            (bank["id"],),
        )
        repository = M2Repository(connection)
        job = repository.create_generation_job(
            bank["id"],
            target_passages=47,
            batch_size=10,
            approved_by="user",
            reason="M2 full quality-bar v1 generation",
        )
        repository.set_job_status(job["id"], "running")
        for result in sorted(records, key=lambda item: item["index"]):
            repository.insert_passage(
                bank_id=bank["id"],
                job_id=job["id"],
                batch_id=BATCH_ID,
                record=result["record"],
                prevalidated=True,
            )
        repository.set_job_status(
            job["id"],
            "completed",
            checkpoint={
                "passages": 47,
                "questions": 300,
                "quality_bar": "v1",
            },
        )
        repository.set_bank_status(bank["id"], "ready")
        repository.activate_bank(bank["id"], actor="system")
        if previous_active:
            repository.set_bank_status(previous_active["id"], "archived")
        connection.commit()
    return {
        "bank_id": bank["id"],
        "passages": 47,
        "questions": 300,
        "previous_active_bank_id": (
            previous_active["id"] if previous_active else None
        ),
    }


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    schedule = load_json(SCHEDULE_PATH)
    specs = schedule["passages"]
    if len(specs) != 47:
        raise RuntimeError(f"SCHEDULE_PASSAGE_COUNT_INVALID {len(specs)}")
    checkpoint_path = EVIDENCE / "run-checkpoint.json"
    existing_records = []
    if checkpoint_path.exists():
        checkpoint = load_json(checkpoint_path)
        existing_records = list(checkpoint.get("records") or [])
    records, failures = fill_records(specs, existing_records)
    for item in records:
        record = item["record"]
        if record["type"] == "reading":
            for question in record["questions"]:
                evidence = question.get("evidence_sentence")
                if not isinstance(evidence, str) or evidence not in record["passage"]:
                    continue
                question["knowledge_points"] = [
                    point
                    for point in question["knowledge_points"]
                    if not point.startswith("evidence_sentence:")
                ]
                question["knowledge_points"].append(
                    f"evidence_sentence:{evidence}"
                )
    write_json(EVIDENCE / "generated-passages.json", records)
    if len(records) != 47:
        write_json(
            EVIDENCE / "run-result.json",
            {
                "status": "partial",
                "passages": len(records),
                "questions": sum(
                    len(item["record"]["questions"]) for item in records
                ),
                "failures": failures,
                "cost_cny": round(_total_cost, 6),
            },
        )
        raise RuntimeError(
            f"M2_GENERATION_INCOMPLETE passages={len(records)}/47"
        )
    specs_by_id = {
        item["passage_group_id"]: item for item in specs
    }
    for result in records:
        validate_record(
            specs_by_id[result["record"]["passage_group_id"]],
            result["record"],
        )
    activation = replace_bank(records)
    result = {
        "status": "passed",
        "passages": 47,
        "questions": 300,
        "cost_cny": round(_total_cost, 6),
        "failures": failures,
        "activation": activation,
    }
    write_json(EVIDENCE / "run-result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
