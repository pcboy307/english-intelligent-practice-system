"""Split-request DeepSeek pipeline for the M2.0b pilot."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

from .deepseek_generation import (
    CostLedger,
    DeepSeekClient,
    run_repair_loop,
)
from .generation import (
    FILL_PLACEHOLDER,
    TYPE_RULES,
    load_curriculum,
    validate_fill_placeholder_shape,
    validate_generated_passage,
)
from .readability import flesch_reading_ease
from .question_validation import (
    QuestionValidationError,
    validate_question_book_tag,
)

ROOT = Path(__file__).resolve().parents[2]
GENERATION_BATCH_SCHEMA_PATH = (
    ROOT / "contracts" / "schemas" / "generation-batch.json"
)
GENERATION_BATCH_SCHEMA = json.loads(
    GENERATION_BATCH_SCHEMA_PATH.read_text(encoding="utf-8")
)
QUESTION_SCHEMA = json.loads(
    (ROOT / "contracts" / "schemas" / "question.json").read_text(
        encoding="utf-8"
    )
)
EXPLANATION_SCHEMA = QUESTION_SCHEMA["properties"]["explanation"]


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


def _sentence_count(text: str) -> int:
    return len(
        [
            item
            for item in re.split(r"[。！？]+", text)
            if item.strip()
        ]
    )


def _book_tag(book_source: str) -> str:
    compact = re.sub(r"\s+", "", book_source)
    if compact.startswith("选必二"):
        return "选必二"
    if compact.startswith("选必一"):
        return "选必一"
    if compact.startswith("跨册"):
        return "跨册"
    if compact.startswith("必修"):
        return "必修"
    return ""


def _build_passage_prompt(spec: dict[str, Any]) -> str:
    type_rules = {
        "cloze": (
            f"170-220 words and numbered blanks (1) through (15), "
            f"each written as its number followed by {FILL_PLACEHOLDER} "
            "(for example, '(1) ______')"
        ),
        "grammar_fill": (
            f"120-180 words and circled blanks ① through ⑩, "
            f"each written as its circled label followed by {FILL_PLACEHOLDER} "
            "(for example, '① ______')"
        ),
        "reading": "no more than 250 words",
        "gap_fill": (
            f"no more than 220 words and numbered blanks (1) through (5), "
            f"each written as its number followed by {FILL_PLACEHOLDER} "
            "(for example, '(1) ______')"
        ),
    }
    return f"""
Write only the original practice passage. Return JSON with one key, "passage".
Type: {spec["type"]}
Topic: {spec["topic"]}
Required length: {type_rules[spec["type"]]}
Every blank must contain one label followed by one space and exactly six
underscores: {FILL_PLACEHOLDER}. Never print an answer word, option word, or
word fragment at or beside a blank.
Use simple vocabulary already learned in PEP 2019 required books 1-3 and
elective required books 1-2. Do not use elective books 3-4 material.
Do not mention real people, schools, exam IDs, brands, or named places.
Do not include questions or explanations in this response.
""".strip()


def _build_questions_prompt(
    spec: dict[str, Any],
    passage: str,
    assignments: list[dict[str, Any]],
) -> str:
    return f"""
Create only the questions listed below for the fixed passage.
Return JSON exactly as {{"questions": [...]}}.
Every question must include:
- stem
- exactly four non-empty options
- answer equal to one exact option
- one unique knowledge_points entry
- grammar_tags, book_source and difficulty copied exactly from its assignment

All options in one grammar_fill question must belong to the same grammatical
category. Assess only the assigned grammar tag.
The correct answer must not occur anywhere in the fixed passage, including
inflected forms. Gap-fill options must not reproduce any six-word sequence
from the passage.

Type: {spec["type"]}
Fixed passage:
{passage}

Assignments:
{json.dumps(assignments, ensure_ascii=False, indent=2)}
""".strip()


def _build_explanations_prompt(
    passage: str,
    questions: list[dict[str, Any]],
) -> str:
    explanation_input = [
        {
            "question_index": index,
            "stem": question["stem"],
            "options": question["options"],
            "answer": question["answer"],
        }
        for index, question in enumerate(questions, start=1)
    ]
    return f"""
Write only Chinese explanations for the following fixed questions.
Return JSON that satisfies this schema:
{json.dumps(GENERATION_BATCH_SCHEMA, ensure_ascii=False, indent=2)}

Example JSON output with two items:
{{
  "explanations": [
    {{
      "question_index": 1,
      "explanation": "第一题答案依据。第一题干扰项错误原因。第一题考点。"
    }},
    {{
      "question_index": 2,
      "explanation": "第二题答案依据。第二题干扰项错误原因。第二题考点。"
    }}
  ]
}}
Every array item MUST be an object containing exactly question_index and
explanation. Do not return bare strings and do not drop question_index.
Each explanation must contain at least three complete Chinese sentences,
separated by Chinese full stops: the correct-answer reason, why a distractor
is wrong, and the assessed knowledge point. Do not change any question.

Passage:
{passage}

Questions:
{json.dumps(explanation_input, ensure_ascii=False, indent=2)}
""".strip()


def _validate_passage_step(
    spec: dict[str, Any],
    data: dict[str, Any],
) -> str:
    passage = data.get("passage")
    if not isinstance(passage, str) or not passage.strip():
        raise ValueError("PASSAGE_TEXT_MISSING")
    rule = TYPE_RULES[spec["type"]]
    word_count = _word_count(passage)
    if not rule["min_words"] <= word_count <= rule["max_words"]:
        raise ValueError(
            f"WORD_COUNT_OUT_OF_RANGE actual={word_count} "
            f"min={rule['min_words']} max={rule['max_words']}"
        )
    integrity_failures = validate_fill_placeholder_shape(
        spec["type"],
        passage,
    )
    if integrity_failures:
        raise ValueError(
            "FILL_PLACEHOLDER_INTEGRITY_FAILED:"
            + json.dumps(
                [failure.as_dict() for failure in integrity_failures],
                ensure_ascii=False,
            )
        )
    return passage


def _validate_question_batch(
    spec: dict[str, Any],
    assignments: list[dict[str, Any]],
    data: dict[str, Any],
    observations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("QUESTIONS_ARRAY_MISSING")
    if len(questions) != len(assignments):
        raise ValueError(
            f"QUESTION_COUNT_MISMATCH actual={len(questions)} "
            f"expected={len(assignments)}"
        )
    curriculum = load_curriculum()
    allowed_tags = {item["id"] for item in curriculum["grammar_whitelist"]}
    validated = []
    for index, (question, assignment) in enumerate(
        zip(questions, assignments, strict=True),
        start=1,
    ):
        if not isinstance(question, dict):
            raise ValueError(f"QUESTION_NOT_OBJECT index={index}")
        for field in (
            "stem",
            "options",
            "answer",
            "knowledge_points",
            "grammar_tags",
            "book_source",
            "difficulty",
        ):
            if field not in question:
                raise ValueError(f"QUESTION_FIELD_MISSING index={index} field={field}")
        options = question["options"]
        if (
            not isinstance(options, list)
            or len(options) != 4
            or any(not isinstance(option, str) or not option.strip() for option in options)
        ):
            raise ValueError(f"QUESTION_OPTIONS_INVALID index={index}")
        if not isinstance(question["answer"], str) or question["answer"] not in options:
            raise ValueError(f"QUESTION_ANSWER_NOT_IN_OPTIONS index={index}")
        if not isinstance(question["stem"], str) or not question["stem"].strip():
            raise ValueError(f"QUESTION_STEM_INVALID index={index}")
        if (
            not isinstance(question["knowledge_points"], list)
            or not question["knowledge_points"]
            or len(set(question["knowledge_points"]))
            != len(question["knowledge_points"])
        ):
            raise ValueError(f"QUESTION_KNOWLEDGE_POINTS_INVALID index={index}")
        tags = question["grammar_tags"]
        if (
            not isinstance(tags, list)
            or not 1 <= len(tags) <= 2
            or any(tag not in allowed_tags for tag in tags)
        ):
            raise ValueError(f"QUESTION_GRAMMAR_TAGS_INVALID index={index}")
        if question["book_source"] != assignment["book_source"] and observations is not None:
            observations.append(
                {
                    "type": "book_source_schedule_mismatch",
                    "question_index": index,
                    "expected": assignment["book_source"],
                    "actual": question["book_source"],
                }
            )
        if question["difficulty"] != assignment["difficulty"] and observations is not None:
            observations.append(
                {
                    "type": "difficulty_schedule_mismatch",
                    "question_index": index,
                    "expected": assignment["difficulty"],
                    "actual": question["difficulty"],
                }
            )
        if tags != assignment["grammar_tags"]:
            if observations is not None:
                observations.append(
                    {
                        "type": "grammar_tag_schedule_mismatch",
                        "question_index": index,
                        "expected": assignment["grammar_tags"],
                        "actual": tags,
                    }
                )
        try:
            validate_question_book_tag(tags, _book_tag(question["book_source"]))
        except QuestionValidationError as error:
            raise ValueError(
                f"BOOK_TAG_INVALID index={index} code={error.code}"
            ) from error
        validated.append(question)
    return validated


def _question_contract_projection(
    *,
    record: dict[str, Any],
    question: dict[str, Any],
    index: int,
    bank_id: str,
    batch_id: str,
) -> dict[str, Any]:
    question_type = record["type"]
    presentation_mode = {
        "cloze": "cloze_single_choice",
        "grammar_fill": "passage_single_choice",
        "reading": "reading_single_choice",
        "gap_fill": "seven_choice",
    }[question_type]
    blank_label = (
        chr(0x2460 + index - 1)
        if question_type == "grammar_fill"
        else f"({index})"
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"{record['passage_group_id']}-Q{index:02d}",
        "bank_id": bank_id,
        "type": question_type,
        "passage_group_id": record["passage_group_id"],
        "passage": record["passage"],
        "word_count": _word_count(record["passage"]),
        "stem": question["stem"],
        "options": question["options"],
        "answer": question["answer"],
        "presentation": {
            "mode": presentation_mode,
            "passage_order": 1,
            "question_order": index,
            "blank_label": blank_label,
            "option_layout": "A-G" if question_type == "gap_fill" else "A-D",
        },
        "explanation": question["explanation"],
        "knowledge_points": question["knowledge_points"],
        "grammar_tags": question["grammar_tags"],
        "book_source": question["book_source"],
        "book_tag": _book_tag(question["book_source"]),
        "difficulty": question["difficulty"],
        "out_of_scope_flags": [],
        "status": "draft",
        "batch_id": batch_id,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def validate_pilot_record(
    record: dict[str, Any],
    schedule_passage: dict[str, Any],
    *,
    bank_id: str,
    batch_id: str,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validation = validate_generated_passage(record)
    observation_rows = list(observations or [])
    hard_failures = []
    for failure in validation.failures:
        data = failure.as_dict()
        if failure.category.value in {"vocabulary_scope", "unknown_ratio"}:
            observation_rows.append(
                {
                    "type": "vocabulary_observation",
                    "message": failure.message,
                    "details": failure.details,
                }
            )
        elif failure.message.startswith("Explanation must contain"):
            observation_rows.append(
                {
                    "type": "explanation_sentence_count",
                    "question_index": failure.question_index,
                    "message": failure.message,
                }
            )
        else:
            hard_failures.append(data)

    common_schema = json.loads(
        (ROOT / "contracts" / "schemas" / "common.json").read_text(
            encoding="utf-8"
        )
    )
    registry = Registry().with_resource(
        common_schema["$id"],
        Resource.from_contents(common_schema),
    )
    validator = jsonschema.Draft202012Validator(
        QUESTION_SCHEMA,
        registry=registry,
    )
    for index, question in enumerate(record["questions"], start=1):
        projected = _question_contract_projection(
            record=record,
            question=question,
            index=index,
            bank_id=bank_id,
            batch_id=batch_id,
        )
        for error in sorted(validator.iter_errors(projected), key=lambda item: list(item.path)):
            hard_failures.append(
                {
                    "category": "question_schema",
                    "message": error.message,
                    "question_index": index,
                    "path": list(error.absolute_path),
                }
            )

    return {
        "accepted": not hard_failures,
        "hard_failures": hard_failures,
        "observations": observation_rows,
        "metrics": validation.metrics,
        "flesch_reading_ease": flesch_reading_ease(record["passage"]),
    }


def _validate_explanation_batch(
    expected_indices: list[int],
    data: dict[str, Any],
    observations: list[dict[str, Any]] | None = None,
) -> dict[int, str]:
    try:
        jsonschema.validate(data, GENERATION_BATCH_SCHEMA)
    except jsonschema.ValidationError as error:
        path = list(error.absolute_path)
        if (
            error.validator == "type"
            and len(path) >= 2
            and path[0] == "explanations"
            and isinstance(path[1], int)
            and isinstance(data.get("explanations"), list)
        ):
            item = data["explanations"][path[1]]
            raise ValueError(
                "EXPLANATION_ITEM_NOT_OBJECT: "
                f"received_type={type(item).__name__} "
                f"sample={json.dumps(item, ensure_ascii=False)[:120]}"
            ) from error
        raise ValueError(
            "GENERATION_BATCH_SCHEMA_INVALID: "
            f"path={path} "
            f"received={json.dumps(data, ensure_ascii=False)[:300]!r}"
        ) from error
    explanations = data["explanations"]
    indices = [item["question_index"] for item in explanations]
    if len(indices) != len(set(indices)):
        raise ValueError(
            "EXPLANATION_INDEX_DUPLICATE: "
            f"indices={indices}"
        )
    if set(indices) != set(expected_indices):
        raise ValueError(
            "EXPLANATION_INDEX_SET_MISMATCH: "
            f"expected={sorted(expected_indices)} actual={sorted(indices)}"
        )
    by_index: dict[int, str] = {}
    for item in sorted(explanations, key=lambda value: value["question_index"]):
        question_index = item["question_index"]
        explanation = item["explanation"]
        sentence_count = _sentence_count(explanation)
        if sentence_count < 3 and observations is not None:
            observations.append(
                {
                    "type": "explanation_sentence_count",
                    "question_index": question_index,
                    "actual": sentence_count,
                    "minimum": 3,
                }
            )
        try:
            jsonschema.validate(explanation, EXPLANATION_SCHEMA)
        except jsonschema.ValidationError as error:
            raise ValueError(
                "QUESTION_SCHEMA_EXPLANATION_INVALID: "
                f"received_type={type(explanation).__name__} "
                f"sample={str(explanation)[:120]!r}"
            ) from error
        by_index[question_index] = explanation
    return by_index


def generate_pilot_passage(
    *,
    client: DeepSeekClient,
    ledger: CostLedger,
    schedule_passage: dict[str, Any],
    bank_id: str = "00000000-0000-4000-8000-000000000000",
    batch_id: str = "M2.0B-DEEPSEEK-PILOT",
    max_repair_retries: int = 3,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    passage = run_repair_loop(
        client=client,
        ledger=ledger,
        purpose=f"passage:{schedule_passage['type']}",
        prompt=_build_passage_prompt(schedule_passage),
        validate=lambda data: _validate_passage_step(schedule_passage, data),
        max_repair_retries=max_repair_retries,
    )

    assignments = schedule_passage["questions"]
    questions: list[dict[str, Any]] = []
    for start in range(0, len(assignments), 5):
        batch = assignments[start : start + 5]
        batch_number = start // 5 + 1
        validated = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose=(
                f"questions:{schedule_passage['type']}:"
                f"batch-{batch_number}"
            ),
            prompt=_build_questions_prompt(
                schedule_passage,
                passage,
                [
                    {"question_order": start + index + 1, **assignment}
                    for index, assignment in enumerate(batch)
                ],
            ),
            validate=lambda data, batch=batch: _validate_question_batch(
                schedule_passage,
                batch,
                data,
                observations,
            ),
            max_repair_retries=max_repair_retries,
        )
        questions.extend(validated)

    explanation_by_index: dict[int, str] = {}
    for start in range(0, len(questions), 10):
        batch_questions = questions[start : start + 10]
        expected_indices = list(
            range(start + 1, start + 1 + len(batch_questions))
        )
        batch = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose=(
                f"explanations:{schedule_passage['type']}:"
                f"batch-{start // 10 + 1}"
            ),
            prompt=_build_explanations_prompt(passage, batch_questions),
            response_schema=GENERATION_BATCH_SCHEMA,
            validate=lambda data, indices=expected_indices: (
                _validate_explanation_batch(
                    indices,
                    data,
                    observations=observations,
                )
            ),
            max_repair_retries=max_repair_retries,
        )
        explanation_by_index.update(batch)

    for index, question in enumerate(questions, start=1):
        question["explanation"] = explanation_by_index[index]

    record = {
        "type": schedule_passage["type"],
        "passage_group_id": schedule_passage["passage_group_id"],
        "topic": schedule_passage["topic"],
        "book_source": schedule_passage["book_source"],
        "difficulty": schedule_passage["difficulty"],
        "passage": passage,
        "questions": questions,
    }
    report = validate_pilot_record(
        record,
        schedule_passage,
        bank_id=bank_id,
        batch_id=batch_id,
        observations=observations,
    )
    record["generation_observations"] = report["observations"]
    record["flesch_reading_ease"] = report["flesch_reading_ease"]
    if not report["accepted"]:
        raise ValueError(
            "PILOT_PASSAGE_HARD_GATE_FAILED:"
            + json.dumps(report["hard_failures"], ensure_ascii=False)
        )
    return record
