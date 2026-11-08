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
    M26_RULES,
    PLACEHOLDER_TYPES,
    _cloze_structure_categories,
    _load_vocabulary_audit_module,
    _placeholder_count_failures,
    get_type_rules,
    load_curriculum,
    load_vocabulary_scope,
    validate_fill_placeholder_shape,
    validate_gap_option_leak,
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


def _unique_unknown_words(text: str) -> list[str]:
    vocabulary = load_vocabulary_scope()
    audit = _load_vocabulary_audit_module().count_passage(
        text,
        vocabulary["single_words"],
        vocabulary["phrases"],
    )
    return sorted({str(word).casefold() for word in audit["unknown"]})


def _build_passage_prompt(spec: dict[str, Any]) -> str:
    profile = str(spec.get("validation_profile", "m2"))
    rule = get_type_rules(spec["type"], profile)
    targets = [
        str(
            question.get("answer_target")
            or question.get("cloze_target")
            or ""
        )
        for question in spec["questions"]
        if question.get("answer_target") or question.get("cloze_target")
    ]
    if profile == "m26":
        length_ranges = {
            "cloze": (
                f"{rule['min_words']}-{rule['max_words']} words; aim for "
                f"{rule['min_words'] + 10}-{rule['max_words'] - 10} and "
                "verify the count before returning"
            ),
            "grammar_fill": (
                f"{rule['min_words']}-{rule['max_words']} words; aim for "
                f"{rule['min_words'] + 10}-{rule['max_words'] - 10} with ten "
                "grammar blanks"
            ),
            "reading": (
                f"{rule['min_words']}-{rule['max_words']} words; aim for "
                f"{rule['min_words'] + 20}-{rule['max_words'] - 15} and "
                "verify the count before returning"
            ),
            "gap_fill": (
                f"{rule['min_words']}-{rule['max_words']} words; aim for "
                f"{rule['min_words'] + 15}-{rule['max_words'] - 15} and "
                "verify the count before returning"
            ),
        }
    else:
        length_ranges = {
            "cloze": "170-220 words",
            "grammar_fill": "120-180 words",
            "reading": "no more than 250 words",
            "gap_fill": "no more than 220 words",
        }
    type_rules = {
        "cloze": (
            f"{length_ranges['cloze']} and numbered "
            "blanks (1) through (15), "
            f"each written as its number followed by {FILL_PLACEHOLDER} "
            "(for example, '(1) ______')"
        ),
        "grammar_fill": (
            f"{length_ranges['grammar_fill']} and circled "
            "blanks ① through ⑩, "
            f"each written as its circled label followed by {FILL_PLACEHOLDER} "
            "(for example, '① ______')"
        ),
        "reading": length_ranges["reading"],
        "gap_fill": (
            length_ranges["gap_fill"]
            + " and numbered blanks (1) through (5), "
            f"each written as its number followed by {FILL_PLACEHOLDER} "
            "(for example, '(1) ______')"
        ),
    }
    blank_instruction = (
        "Every blank must contain one label followed by one space and exactly six "
        f"underscores: {FILL_PLACEHOLDER}. Never print an answer word, option "
        "word, or word fragment at or beside a blank."
        if spec["type"] in PLACEHOLDER_TYPES
        else "This passage type has no blanks. Do not include numbered blanks, "
        "circled labels, or underscore placeholders anywhere."
    )
    target_block = ""
    if targets:
        marker_for = (
            lambda index: f"({index})"
            if spec["type"] in {"cloze", "gap_fill"}
            else chr(0x2460 + index - 1)
        )
        target_map = [
            {
                "blank": marker_for(index),
                "answer": str(
                    question.get("answer_target")
                    or question.get("cloze_target")
                    or ""
                ).strip(),
            }
            for index, question in enumerate(spec["questions"], start=1)
            if question.get("answer_target") or question.get("cloze_target")
        ]
        target_block = (
            "\nThe blank-to-answer mapping is fixed and MUST be followed exactly. "
            "For every entry below, the exact answer must be grammatical, "
            "idiomatic, and semantically justified when substituted into that "
            "numbered blank:\n"
            f"{json.dumps(target_map, ensure_ascii=False, indent=2)}"
            "\nDo not print any target or its inflected form anywhere in the "
            "passage. Each marker replaces the ENTIRE target. Do not leave any "
            "word from a target immediately before or after its marker. Before "
            "returning, test every blank by mentally inserting its mapped answer."
        )
    feedback_block = ""
    feedback = spec.get("generation_feedback")
    if feedback:
        feedback_block = (
            "\nThe previous generated passage was rejected by the deterministic "
            "quality validator. Repair the cause while preserving every other "
            "requirement:\n"
            + (
                "\n".join(f"- {item}" for item in feedback)
                if isinstance(feedback, list)
                else f"- {feedback}"
            )
        )
    style_guidance_block = ""
    style_guidance = spec.get("style_guidance")
    if style_guidance:
        style_guidance_block = (
            "\nSTYLE GUIDANCE (mandatory):\n"
            + (
                "\n".join(f"- {item}" for item in style_guidance)
                if isinstance(style_guidance, list)
                else f"- {style_guidance}"
            )
        )
    m26_quality = ""
    if profile == "m26":
        cloze_rule = M26_RULES["cloze"]
        reading_rule = M26_RULES["reading"]
        grammar_rule = M26_RULES["grammar_fill"]
        m26_quality = f"""
M2.6 quality requirements:
- Cloze: average sentence length at least
  {cloze_rule['average_sentence_words_minimum']} words; Flesch Reading Ease
  {cloze_rule['flesch_reading_ease']['minimum']}-
  {cloze_rule['flesch_reading_ease']['maximum']} (preferably 50-58, not the
  upper boundary); at least
  {cloze_rule['long_sentence_minimum_count']} sentences of at least
  {cloze_rule['long_sentence_minimum_words']} words. Across the passage include
  at least {cloze_rule['structure_categories_minimum_count']} distinct
  structures from: non-finite, nominal clause, parenthetical/appositive, and
  inversion/ellipsis. Use precise abstract nouns from the approved list and
  avoid a chain of short, simple clauses that makes the prose too easy.
- Reading: average sentence length at least
  {reading_rule['average_sentence_words_minimum']} words; Flesch Reading Ease
  {reading_rule['flesch_reading_ease']['minimum']}-
  {reading_rule['flesch_reading_ease']['maximum']}; include at least one
  paragraph-function question asking why a named paragraph mentions a detail.
- Grammar fill: the ten items together must include all five mandatory
  categories: perfect/passive non-finite, preposition + which, what-led nominal
  clause, subjunctive, and inversion. Additional grammar categories may be used
  for the remaining items. Punctuation outside each blank must still produce a
  grammatical sentence after insertion; never place a comma between a subject
  and its predicate.
- Gap fill: use at least three distinct cohesion types: pronoun reference,
  logical connector, lexical repetition, time order, general-to-specific. The
  passage must be expository or argumentative and discuss an abstract issue such
  as technology ethics, urban governance, or a psychological mechanism.
- The passage must be coherent, not a collection of unrelated example
  sentences. Use at most three recurring people or actors.
- Abstract nouns are allowed when they are in the frozen vocabulary whitelist or
  are clarified by context.
- Do not invent personal names. Refer to people only by roles such as the
  student, teacher, parent, neighbour, or volunteer.
"""
    vocabulary_block = ""
    if profile == "m26":
        allowed_words = " ".join(
            sorted(load_vocabulary_scope()["single_words"])
        )
        vocabulary_block = (
            "\nUse only these base words or their accepted inflections unless "
            "a topic term is unavoidable:\n"
            + allowed_words
        )
    return f"""
Write only the original practice passage. Return JSON with one key, "passage".
Type: {spec["type"]}
Topic: {spec["topic"]}
Topic focus: {spec.get("topic_focus", spec["topic"])}
Required length: {type_rules[spec["type"]]}
{blank_instruction}
{target_block}
{feedback_block}
{style_guidance_block}
{m26_quality}
{vocabulary_block}
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
    option_count = 7 if spec["type"] == "gap_fill" else 4
    batch_count = len(assignments)
    answer_rule = (
        "answer is one letter A-G"
        if spec["type"] == "gap_fill"
        else "answer equal to one exact option"
    )
    fixed_targets = [
        {
            "question_order": assignment.get("question_order"),
            "answer_target": (
                assignment.get("answer_target")
                or assignment.get("cloze_target")
            ),
        }
        for assignment in assignments
        if assignment.get("answer_target") or assignment.get("cloze_target")
    ]
    target_rule = ""
    if fixed_targets:
        target_rule = (
            "\nFIXED ANSWERS: the answer field must exactly equal these target "
            "strings, character for character, and each target must appear once "
            "in that question's options:\n"
            + json.dumps(fixed_targets, ensure_ascii=False, indent=2)
        )
    assignment_metadata = [
        {
            "question_order": assignment.get("question_order"),
            "reading_type": assignment.get("reading_type"),
            "cohesion_type": assignment.get("cohesion_type"),
            "grammar_category": assignment.get("grammar_category"),
        }
        for assignment in assignments
        if any(
            assignment.get(field) is not None
            for field in ("reading_type", "cohesion_type", "grammar_category")
        )
    ]
    assignment_rule = ""
    if assignment_metadata:
        assignment_rule = (
            "\nQUESTION-TYPE ASSIGNMENTS (follow exactly):\n"
            + json.dumps(assignment_metadata, ensure_ascii=False, indent=2)
        )
    m26_rules = ""
    if spec.get("validation_profile") == "m26":
        m26_rules = """
M2.6 question requirements:
- Cloze distractors must belong to the same semantic field and part of speech.
  Do not use one correct word plus three obvious antonyms. At least three cloze
  questions must include a genuine near-synonym/easily confused distractor.
- Every reading question is comprehension-based. The correct option must be a
  paraphrase, never share five consecutive words with the passage.
- Gap-fill options must be seven complete, mutually distinguishable sentences,
  and only one option may fit each blank.
"""
    return f"""
Create only the questions listed below for the fixed passage.
Return JSON exactly as {{"questions": [...]}}.
This is one partial batch: return exactly {batch_count} questions, one for each
assignment below and in the same order. Do not return the other questions from
the passage.
Every question must include:
- stem
- exactly {option_count} non-empty options
- {answer_rule}
- one unique knowledge_points entry
- grammar_tags, book_source and difficulty copied exactly from its assignment
- evidence_sentence for every reading question: an exact passage substring
{target_rule}
{assignment_rule}

All options in one grammar_fill question must belong to the same grammatical
category. Assess only the assigned grammar tag.
When an assignment contains answer_target, the answer must equal that exact
text; do not replace it with another word or phrase.
The correct answer must not occur anywhere in the fixed passage, including
inflected forms. Gap-fill options must not reproduce any six-word sequence
from the passage.
{m26_rules}

Type: {spec["type"]}
For gap_fill, every question must use the same complete seven-sentence option
set.
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
    *,
    enforce_minimum: bool = True,
    enforce_quality: bool = True,
) -> str:
    passage = data.get("passage")
    if not isinstance(passage, str) or not passage.strip():
        raise ValueError("PASSAGE_TEXT_MISSING")
    rule = get_type_rules(
        spec["type"],
        str(spec.get("validation_profile", "m2")),
    )
    word_count = _word_count(passage)
    minimum_ok = word_count >= rule["min_words"] or not enforce_minimum
    if not minimum_ok or word_count > rule["max_words"]:
        raise ValueError(
            f"WORD_COUNT_OUT_OF_RANGE actual={word_count} "
            f"min={rule['min_words']} max={rule['max_words']}"
        )
    integrity_failures = validate_fill_placeholder_shape(
        spec["type"],
        passage,
    ) + _placeholder_count_failures(spec["type"], passage)
    if integrity_failures:
        raise ValueError(
            "FILL_PLACEHOLDER_INTEGRITY_FAILED:"
            + json.dumps(
                [failure.as_dict() for failure in integrity_failures],
                ensure_ascii=False,
            )
        )
    if spec.get("validation_profile") == "m26" and enforce_quality:
        cloze_rule = M26_RULES["cloze"]
        reading_rule = M26_RULES["reading"]
        unknown_words = _unique_unknown_words(passage)
        if len(unknown_words) > 3:
            raise ValueError(
                "R12_VOCABULARY_LIMIT "
                f"unique_unknown={len(unknown_words)} words={unknown_words}"
            )
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", passage)
            if sentence.strip()
        ]
        average_sentence_words = (
            word_count / len(sentences) if sentences else 0
        )
        if spec["type"] in {"cloze", "reading"}:
            flesch = flesch_reading_ease(passage)
            rule_key = "cloze" if spec["type"] == "cloze" else "reading"
            flesch_range = M26_RULES[rule_key]["flesch_reading_ease"]
            if not (
                float(flesch_range["minimum"])
                <= flesch
                <= float(flesch_range["maximum"])
            ):
                raise ValueError(
                    f"R12_{rule_key.upper()}_FLESCH actual={flesch} "
                    f"expected={flesch_range['minimum']}-"
                    f"{flesch_range['maximum']}"
                )
        if spec["type"] == "cloze":
            if average_sentence_words < float(
                cloze_rule["average_sentence_words_minimum"]
            ):
                raise ValueError(
                    "R12_CLOZE_SENTENCE_LENGTH "
                    f"actual={average_sentence_words:.2f}"
                )
            long_sentences = sum(
                _word_count(sentence)
                >= int(cloze_rule["long_sentence_minimum_words"])
                for sentence in sentences
            )
            if long_sentences < int(
                cloze_rule["long_sentence_minimum_count"]
            ):
                raise ValueError(
                    f"R12_CLOZE_LONG_SENTENCES actual={long_sentences}"
                )
            structure_categories = _cloze_structure_categories(passage)
            if len(structure_categories) < int(
                cloze_rule["structure_categories_minimum_count"]
            ):
                raise ValueError(
                    "R12_CLOZE_STRUCTURE_CATEGORIES "
                    f"actual={structure_categories}"
                )
        if (
            spec["type"] == "reading"
            and average_sentence_words
            < float(reading_rule["average_sentence_words_minimum"])
        ):
            raise ValueError(
                "R12_READING_SENTENCE_LENGTH "
                f"actual={average_sentence_words:.2f}"
            )
    return passage


def _append_m26_passage(
    *,
    client: DeepSeekClient,
    ledger: CostLedger,
    spec: dict[str, Any],
    passage: str,
) -> str:
    rule = get_type_rules(spec["type"], "m26")
    current = passage
    for expansion_index in range(1, 5):
        current_words = _word_count(current)
        if current_words >= rule["min_words"]:
            return _validate_passage_step(
                spec,
                {"passage": current},
                enforce_quality=False,
            )
        needed = rule["min_words"] - current_words
        lower = needed + 8
        upper = needed + 24
        appended = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose=(
                f"extend-passage:{spec['type']}:{expansion_index}"
            ),
            prompt=f"""
Continue the existing passage below with new, coherent sentences from the
same topic, characters, and time line. Append between {lower} and {upper}
English words. Do not repeat or rewrite the existing passage. Do not add,
remove, or move blank markers. Do not print any preplanned answer or its
inflected form. Return JSON only as {{"append": "new sentences"}}.

Preplanned answers:
{json.dumps([
    question.get("answer_target") or question.get("cloze_target")
    for question in spec["questions"]
    if question.get("answer_target") or question.get("cloze_target")
], ensure_ascii=False)}

Existing passage:
{current}
""".strip(),
            validate=lambda data: (
                str(data.get("append", "")).strip()
                if isinstance(data.get("append"), str)
                and data["append"].strip()
                and not any(
                    marker in data["append"]
                    for marker in (
                        ["(" + str(index) + ")" for index in range(1, 16)]
                        if spec["type"] in {"cloze", "gap_fill"}
                        else [chr(0x2460 + index - 1) for index in range(1, 11)]
                    )
                )
                else (_ for _ in ()).throw(
                    ValueError("M26_PASSAGE_APPEND_INVALID")
                )
            ),
            max_repair_retries=1,
        )
        current = f"{current.rstrip()} {appended}"
    return _validate_passage_step(
        spec,
        {"passage": current},
        enforce_quality=False,
    )


def _simplify_m26_vocabulary(
    *,
    client: DeepSeekClient,
    ledger: CostLedger,
    spec: dict[str, Any],
    passage: str,
) -> str:
    current = passage
    for attempt in range(1, 7):
        unknown = _unique_unknown_words(current)
        try:
            return _validate_passage_step(spec, {"passage": current})
        except ValueError as quality_error:
            quality_message = str(quality_error)
        rewritten = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose=(
                f"simplify-vocabulary:{spec['type']}:{attempt}"
            ),
            prompt=f"""
Rewrite the complete passage below so that all words outside the approved
senior-high curriculum list are replaced with common approved alternatives.
Keep the same topic, characters, sequence of ideas, blank markers, and
approximate word count. Never reveal or insert any preplanned answer. Return
JSON only as {{"passage": "complete rewritten passage"}}.

If any quality error concerns Flesch Reading Ease being too high, do not make
the sentences shorter or simpler. Merge adjacent short sentences into longer
multi-clause sentences, embed nominal clauses and parenthetical phrases, and
replace vague general words with precise abstract nouns from the approved
curriculum. Preserve the blank-to-answer mapping and every placeholder exactly.

Words that must be removed or replaced:
{json.dumps(unknown, ensure_ascii=False)}

Other quality errors that must be fixed without weakening the requirements:
{quality_message}

Approved answer targets that must remain absent:
{json.dumps([
    question.get("answer_target") or question.get("cloze_target")
    for question in spec["questions"]
    if question.get("answer_target") or question.get("cloze_target")
], ensure_ascii=False)}

Current passage:
{current}
""".strip(),
            validate=lambda data: _validate_passage_step(
                spec,
                data,
                enforce_minimum=False,
                enforce_quality=False,
            ),
            max_repair_retries=1,
        )
        current = rewritten
    return _validate_passage_step(spec, {"passage": current})


def _validate_question_batch(
    spec: dict[str, Any],
    assignments: list[dict[str, Any]],
    data: dict[str, Any],
    observations: list[dict[str, Any]] | None = None,
    passage: str | None = None,
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
        expected_options = 7 if spec["type"] == "gap_fill" else 4
        if (
            not isinstance(options, list)
            or len(options) != expected_options
            or any(not isinstance(option, str) or not option.strip() for option in options)
        ):
            raise ValueError(f"QUESTION_OPTIONS_INVALID index={index}")
        if not isinstance(question["answer"], str):
            raise ValueError(f"QUESTION_ANSWER_INVALID index={index}")
        if spec["type"] == "gap_fill":
            if question["answer"].upper() not in set("ABCDEFG"):
                raise ValueError(f"QUESTION_ANSWER_NOT_IN_OPTIONS index={index}")
        elif question["answer"] not in options:
            raise ValueError(f"QUESTION_ANSWER_NOT_IN_OPTIONS index={index}")
        if not isinstance(question["stem"], str) or not question["stem"].strip():
            raise ValueError(f"QUESTION_STEM_INVALID index={index}")
        if spec["type"] == "reading" and spec.get("validation_profile") == "m26":
            evidence = question.get("evidence_sentence")
            if (
                not isinstance(evidence, str)
                or not evidence.strip()
                or passage is None
                or evidence.strip() not in passage
            ):
                raise ValueError(
                    f"R14_EVIDENCE_SENTENCE_INVALID index={index}"
                )
            question["evidence_sentence"] = evidence.strip()
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
        target = assignment.get("answer_target") or assignment.get("cloze_target")
        if target and str(question["answer"]).casefold() != str(target).casefold():
            raise ValueError(
                "ANSWER_TARGET_MISMATCH "
                f"index={index} expected={target!r} actual={question['answer']!r}"
            )
        try:
            validate_question_book_tag(tags, _book_tag(question["book_source"]))
        except QuestionValidationError as error:
            raise ValueError(
                f"BOOK_TAG_INVALID index={index} code={error.code}"
            ) from error
        validated.append(question)
    if spec["type"] == "gap_fill":
        leaks = validate_gap_option_leak(
            passage or "",
            validated,
        )
        if leaks:
            raise ValueError(
                "GAP_OPTION_TEXT_LEAK:"
                + json.dumps(
                    [failure.as_dict() for failure in leaks],
                    ensure_ascii=False,
                )
            )
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


def _build_distractors_prompt(
    *,
    spec: dict[str, Any],
    assignment: dict[str, Any],
    question_index: int,
    passage: str,
    target: str,
) -> str:
    requires_near_synonym = bool(
        assignment.get("near_synonym_calibration")
        or assignment.get("near_synonym_required")
    )
    near_synonym_rule = (
        "At least one distractor must be a genuine near-synonym or easily "
        "confused word. The fixed answer must still be the only option that "
        "matches all contextual clues. All three distractors must be words a "
        "student would plausibly consider for this exact blank, not unrelated "
        "verbs or pure opposites."
        if spec["type"] == "cloze"
        else "All distractors must belong to the same grammatical category "
        "as the answer."
    )
    if spec["type"] == "cloze" and requires_near_synonym:
        near_synonym_rule += (
            " This question MUST contain exactly one near-synonym distractor; "
            "the context must make the fixed answer clearly better than that "
            "near-synonym, while both other distractors are clearly impossible."
        )
    elif spec["type"] == "cloze":
        near_synonym_rule += (
            " This question is not one of the three designated near-synonym "
            "items. Keep all three distractors in the same broad semantic field "
            "and part of speech, but make them clearly impossible from the "
            "surrounding context."
        )
    return f"""
The correct answer for blank {question_index} is fixed and must not be changed:
{target!r}

Return JSON only as {{"distractors": ["...", "...", "..."]}}.
Write exactly three distractors for this blank. Distractors must be different
from the answer and from one another, must fit the same part of speech and
semantic field, and must not be obvious antonyms. {near_synonym_rule}

Type: {spec["type"]}
Grammar tags: {json.dumps(assignment["grammar_tags"], ensure_ascii=False)}
Grammar category: {assignment.get("grammar_category", "same category as answer")}
Passage:
{passage}
""".strip()


def _generate_m26_fixed_choice_questions(
    *,
    client: DeepSeekClient,
    ledger: CostLedger,
    spec: dict[str, Any],
    passage: str,
    max_repair_retries: int,
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for index, assignment in enumerate(spec["questions"], start=1):
        target = str(
            assignment.get("answer_target")
            or assignment.get("cloze_target")
            or ""
        ).strip()
        if not target:
            raise ValueError(f"ANSWER_TARGET_MISSING index={index}")
        configured = assignment.get("distractor_candidates")
        if isinstance(configured, list) and len(configured) == 3:
            distractors = [str(value).strip() for value in configured]
        else:
            distractors = run_repair_loop(
                client=client,
                ledger=ledger,
                purpose=f"distractors:{spec['type']}:{index}",
                prompt=_build_distractors_prompt(
                    spec=spec,
                    assignment=assignment,
                    question_index=index,
                    passage=passage,
                    target=target,
                ),
                validate=lambda data: (
                    [
                        str(value).strip()
                        for value in data.get("distractors", [])
                    ]
                    if isinstance(data.get("distractors"), list)
                    and len(data["distractors"]) == 3
                    and all(
                        isinstance(value, str)
                        and value.strip()
                        and value.strip().casefold() != target.casefold()
                        for value in data["distractors"]
                    )
                    and len(
                        {
                            value.strip().casefold()
                            for value in data["distractors"]
                        }
                    )
                    == 3
                    else (_ for _ in ()).throw(
                        ValueError(f"DISTRACTORS_INVALID index={index}")
                    )
                ),
                max_repair_retries=max_repair_retries,
            )
        options = list(distractors)
        options.insert(index % 4, target)
        question = {
            "stem": f"Choose the best option for blank {index}.",
            "options": options,
            "answer": target,
            "knowledge_points": [f"grammar:{assignment['grammar_tags'][0]}"],
            "grammar_tags": list(assignment["grammar_tags"]),
            "book_source": assignment["book_source"],
            "difficulty": assignment["difficulty"],
        }
        for metadata_field in (
            "grammar_category",
            "reading_type",
            "cohesion_type",
            "near_synonym_calibration",
        ):
            value = assignment.get(metadata_field)
            if value is not None:
                question[metadata_field] = value
        questions.append(question)
    return questions


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
    if schedule_passage.get("validation_profile") == "m26":
        passage = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose=f"passage:{schedule_passage['type']}",
            prompt=_build_passage_prompt(schedule_passage),
            validate=lambda data: _validate_passage_step(
                schedule_passage,
                data,
                enforce_minimum=False,
                enforce_quality=False,
            ),
            max_repair_retries=max_repair_retries,
        )
        passage = _append_m26_passage(
            client=client,
            ledger=ledger,
            spec=schedule_passage,
            passage=passage,
        )
        passage = _simplify_m26_vocabulary(
            client=client,
            ledger=ledger,
            spec=schedule_passage,
            passage=passage,
        )
    else:
        passage = run_repair_loop(
            client=client,
            ledger=ledger,
            purpose=f"passage:{schedule_passage['type']}",
            prompt=_build_passage_prompt(schedule_passage),
            validate=lambda data: _validate_passage_step(schedule_passage, data),
            max_repair_retries=max_repair_retries,
        )

    assignments = schedule_passage["questions"]
    if (
        schedule_passage.get("validation_profile") == "m26"
        and schedule_passage["type"] in {"cloze", "grammar_fill"}
    ):
        questions = _generate_m26_fixed_choice_questions(
            client=client,
            ledger=ledger,
            spec=schedule_passage,
            passage=passage,
            max_repair_retries=max_repair_retries,
        )
    else:
        questions = []
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
                    passage=passage,
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
        for metadata_field in (
            "grammar_category",
            "reading_type",
            "cohesion_type",
        ):
            value = assignments[index - 1].get(metadata_field)
            if value is not None:
                question[metadata_field] = value

    record = {
        "validation_profile": schedule_passage.get(
            "validation_profile",
            "m2",
        ),
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
