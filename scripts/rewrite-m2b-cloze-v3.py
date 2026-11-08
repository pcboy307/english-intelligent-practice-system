#!/usr/bin/env python3
"""Rewrite the M2.0b cloze passage and all 15 questions as one design."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.cloze_quality import (  # noqa: E402
    validate_cloze_context,
    validate_cross_audit,
    validate_cross_audit_shape,
)
from backend.app.deepseek_generation import (  # noqa: E402
    CostLedger,
    DeepSeekClient,
    RepairExhausted,
    run_repair_loop,
)
from backend.app.generation import (  # noqa: E402
    _load_vocabulary_audit_module,
    load_curriculum,
    load_vocabulary_scope,
)
from backend.app.m2_deepseek_pipeline import (  # noqa: E402
    _sentence_count,
    _validate_explanation_batch,
    validate_pilot_record,
)
from backend.app.m2_pilot import load_pilot_schedule  # noqa: E402
from backend.app.m2_repository import M2Repository  # noqa: E402
from backend.app.question_quality import (  # noqa: E402
    STOPWORDS,
    validate_cloze_options,
)
from backend.app.question_validation import (  # noqa: E402
    QuestionValidationError,
    validate_question_book_tag,
)
from backend.app.readability import flesch_reading_ease  # noqa: E402


EVIDENCE = ROOT / "qa" / "evidence" / "m2b"
SCHEMA_PATH = ROOT / "contracts" / "schemas" / "cloze-rewrite-batch.json"
PLAN_SCHEMA_PATH = ROOT / "contracts" / "schemas" / "cloze-plan.json"
PASSAGE_DESIGN_SCHEMA_PATH = (
    ROOT / "contracts" / "schemas" / "cloze-passage-design.json"
)
QUESTION_BATCH_SCHEMA_PATH = (
    ROOT / "contracts" / "schemas" / "cloze-question-batch.json"
)
EXPLANATION_SCHEMA_PATH = (
    ROOT / "contracts" / "schemas" / "generation-batch.json"
)
RUN_SECONDS = 90 * 60
RUN_BUDGET_CNY = 5.0
BATCH_ID = "M2.0B-CLOZE-REWRITE-V3"

DISTRACTOR_SEEDS = {
    "anxious": ["uneasy", "concerned", "restless"],
    "confident": ["assured", "hopeful", "optimistic"],
    "curious": ["inquisitive", "interested", "attentive"],
    "reliable": ["dependable", "trustworthy", "consistent"],
    "ambitious": ["driven", "determined", "aspiring"],
    "achieve": ["accomplish", "attain", "realize"],
    "adapt": ["adjust", "accommodate", "respond"],
    "encourage": ["motivate", "inspire", "reassure"],
    "persuade": ["convince", "coax", "urge"],
    "concentrate": ["focus", "attend", "think"],
    "gradually": ["steadily", "slowly", "progressively"],
    "eventually": ["finally", "ultimately", "later"],
    "independently": ["autonomously", "separately", "alone"],
    "confidence": ["assurance", "certainty", "optimism"],
    "opportunity": ["chance", "opening", "possibility"],
}


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


def book_tag(book_source: str) -> str:
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


def allowed_tags(book_source: str) -> list[str]:
    tag = book_tag(book_source)
    return [
        item["id"]
        for item in load_curriculum()["grammar_whitelist"]
        if tag in item["allowed_book_tags"]
    ]


@lru_cache(maxsize=1)
def target_word_candidates() -> tuple[str, ...]:
    vocabulary = load_json(
        ROOT / "contracts" / "vocabulary-whitelist.json"
    )
    return tuple(
        sorted(
            {
                entry["word"].lower()
                for entry in vocabulary["entries"]
                if not entry.get("closed_class")
                and re.fullmatch(r"[a-z]+", entry["word"].lower())
            }
        )
    )


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


def collocation_phrase(
    passage: str,
    question_index: int,
    answer: str,
) -> str:
    marker = re.search(
        rf"\({question_index}\)\s*_{{2,}}",
        passage,
    )
    if marker is None:
        return answer
    tail = passage[marker.end() :]
    sentence_tail = re.split(r"[.!?]", tail, maxsplit=1)[0]
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence_tail)
    return " ".join([answer, *words[:6]]).strip()


def plan_prompt(
    schedule: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    return f"""
Choose the 15 lexical targets for one original lexical cloze passage on
topic "{schedule["topic"]}".

Return JSON satisfying this schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Requirements:
- All 15 contexts must belong to one continuous school-growth story about the
  same student, their teacher or coach, and their classmates. Do not choose 15
  unrelated example situations.
- Exactly 15 unique target words, one for each question_index 1-15.
- Choose every target_word only from the allowed_target_words list in the
  schema section below. The list comes directly from the 3413-entry whitelist.
- Each target must be a single alphabetic lexical word already suitable for
  high-school English; never choose an article, preposition, auxiliary, pronoun,
  conjunction, or other function word.
- Mix adjectives, verbs, adverbs, and nouns across the 15 targets.
- For each target, state its coarse part of speech, one semantic field, and an
  intended blank sentence idea.
- Choose targets that can have three same-part-of-speech distractors in the same
  semantic field while still leaving exactly one defensible answer.

allowed_target_words:
{json.dumps(target_word_candidates(), ensure_ascii=False)}
""".strip()


def validate_plan(
    *,
    schema: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as error:
        raise ValueError(
            "CLOZE_PLAN_SCHEMA_INVALID "
            f"path={list(error.absolute_path)} message={error.message}"
        ) from error
    targets = data["targets"]
    indices = [item["question_index"] for item in targets]
    if indices != list(range(1, 16)):
        raise ValueError(
            f"CLOZE_PLAN_INDEX_MISMATCH expected={list(range(1, 16))} "
            f"actual={indices}"
        )
    words = [item["target_word"] for item in targets]
    if len({word.casefold() for word in words}) != 15:
        raise ValueError("CLOZE_PLAN_TARGETS_MUST_BE_UNIQUE")
    function_words = [
        word for word in words if word.casefold() in STOPWORDS
    ]
    if function_words:
        raise ValueError(
            f"CLOZE_PLAN_FUNCTION_WORDS_FORBIDDEN {function_words}"
        )
    vocabulary = load_vocabulary_scope()
    resolve = _load_vocabulary_audit_module().resolve
    out_of_scope = [
        word
        for word in words
        if resolve(word.casefold(), vocabulary["single_words"])
        not in vocabulary["single_words"]
    ]
    if out_of_scope:
        raise ValueError(
            f"CLOZE_PLAN_TARGETS_OUT_OF_SCOPE {out_of_scope}"
        )
    return data


def passage_design_prompt(
    schedule: dict[str, Any],
    schema: dict[str, Any],
    plan: dict[str, Any],
    previous_errors: list[str] | None = None,
) -> str:
    prompt = f"""
Use the fixed 15-word target plan below to write one original cloze passage.
Create the passage and all 15 blank positions together; do not take an existing
text and remove words afterward.
All sentence pairs must follow one chronological story about the same student,
their teacher or coach, and their classmates.

Return JSON satisfying this schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Hard requirements:
- Return exactly 16 sentences. Their order is the passage order.
- Every sentence must be 11-14 ordinary words after filling its blank.
- The total passage must be 190-215 words.
- Use one continuous chronological story about one student, with at most one
  teacher or coach and one classmate. Avoid switching to unrelated people.
- Insert blanks (1) through (15) across the sentences in plan order.
- Use no personal names.
- Every target must require cumulative context or careful semantic judgement;
  do not place a direct synonym, antonym, or same-root word in the passage.
- Include at least three genuine subordinate or non-finite structures and list
  their exact sentence_index and evidence in complex_structures.
- Aim for Flesch Reading Ease 60-78. Do not write a chain of simple, isolated
  sentences.
- Use natural, standard English. Do not invent collocations or unstated facts.
- Use simple vocabulary appropriate for the assigned high-school level.
- Do not use personal names, named schools, brands, or named places. Refer to
  people by roles such as "a student", "her brother", or "their teacher".
- Do not return questions, options, explanations, or commentary.

Topic: {schedule["topic"]}

Fixed target plan:
{json.dumps(plan, ensure_ascii=False, indent=2)}
""".strip()
    if previous_errors:
        prompt += (
            "\n\nThe previous passage design was rejected. Fix these exact "
            "errors and return a complete new JSON object:\n"
            + json.dumps(previous_errors, ensure_ascii=False, indent=2)
        )
    return prompt


def validate_passage_design(
    *,
    schema: dict[str, Any],
    plan: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as error:
        raise ValueError(
            "PASSAGE_DESIGN_SCHEMA_INVALID "
            f"path={list(error.absolute_path)} message={error.message}"
        ) from error
    sentences = [sentence.strip() for sentence in data["sentences"]]
    invalid_sentences = [
        index
        for index, sentence in enumerate(sentences, start=1)
        if not re.search(r"[.!?]$", sentence)
    ]
    if invalid_sentences:
        raise ValueError(
            f"PASSAGE_SENTENCES_MISSING_PUNCTUATION {invalid_sentences}"
        )
    passage = " ".join(sentences)
    count = word_count(passage)
    if not 170 <= count <= 220:
        raise ValueError(
            f"WORD_COUNT_OUT_OF_RANGE actual={count} min=170 max=220"
        )
    missing_blanks = [
        index for index in range(1, 16) if f"({index})" not in passage
    ]
    if missing_blanks:
        raise ValueError(f"CLOZE_BLANKS_MISSING {missing_blanks}")
    average_sentence_words = count / len(sentences)
    if average_sentence_words < 12:
        raise ValueError(
            f"AVERAGE_SENTENCE_LENGTH_TOO_LOW "
            f"actual={average_sentence_words:.3f} minimum=12"
        )
    readability = flesch_reading_ease(passage)
    if not 60 <= readability <= 78:
        raise ValueError(
            f"FLESCH_OUT_OF_RANGE actual={readability:.2f} min=60 max=78"
        )
    structure_failures = []
    for item in data["complex_structures"]:
        sentence_index = item["sentence_index"]
        sentence = sentences[sentence_index - 1]
        if item["evidence"] not in sentence:
            structure_failures.append(
                {
                    "sentence_index": sentence_index,
                    "code": "COMPLEX_STRUCTURE_EVIDENCE_NOT_IN_SENTENCE",
                }
            )
    if structure_failures:
        raise ValueError(
            "COMPLEX_STRUCTURE_INVALID "
            + json.dumps(structure_failures, ensure_ascii=False)
        )
    target_words = data["target_words"]
    planned_words = [
        item["target_word"] for item in plan["targets"]
    ]
    if [
        item.casefold() for item in target_words
    ] != [item.casefold() for item in planned_words]:
        raise ValueError(
            "PASSAGE_TARGETS_DIFFER_FROM_PLAN "
            f"planned={planned_words} actual={target_words}"
        )
    return {
        **data,
        "passage": passage,
        "target_words": target_words,
        "metrics": {
            "word_count": count,
            "sentence_count": len(sentences),
            "average_sentence_words": round(average_sentence_words, 3),
            "flesch_reading_ease": readability,
            "complex_structure_count": len(data["complex_structures"]),
        },
    }


def compression_prompt(
    *,
    schema: dict[str, Any],
    design: dict[str, Any],
) -> str:
    return f"""
Condense this rejected cloze passage design to 180-210 ordinary words.
Return JSON satisfying the same schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Do not change any target_word. Preserve all 15 numbered blanks, the single
student narrative, exactly 16 sentences, and the three complex-structure
declarations. Remove redundant modifiers, repeated ideas, and wordy phrases.
Do not add fields or explanations.

Current design:
{json.dumps(design, ensure_ascii=False, indent=2)}
""".strip()


def question_batch_prompt(
    *,
    schedule: dict[str, Any],
    schema: dict[str, Any],
    plan: dict[str, Any],
    passage_design: dict[str, Any],
) -> str:
    sentences = passage_design["sentences"]
    assignments = [
        {
            "question_index": index,
            "target_word": target["target_word"],
            "part_of_speech": target["part_of_speech"],
            "semantic_field": target["semantic_field"],
            "book_source": assignment["book_source"],
            "difficulty": assignment["difficulty"],
            "grammar_tags": assignment["grammar_tags"],
            "allowed_grammar_tags": allowed_tags(
                assignment["book_source"]
            ),
            "required_tier": (
                "easy"
                if index <= 6
                else "medium"
                if index <= 12
                else "hard"
            ),
            "distractor_seed_words": DISTRACTOR_SEEDS.get(
                target["target_word"],
                [],
            ),
            "allowed_context_clues": [
                {
                    "sentence_index": clue_index,
                    "text": sentences[clue_index - 1],
                    "distance": abs(clue_index - blank_index),
                }
                for clue_index in range(1, len(sentences) + 1)
                if abs(clue_index - blank_index)
                >= (1 if index <= 6 else 2 if index <= 12 else 4)
                and abs(clue_index - blank_index)
                <= (1 if index <= 6 else 3 if index <= 12 else len(sentences))
            ],
        }
        for index, (target, assignment) in enumerate(
            zip(
                plan["targets"],
                schedule["questions"],
                strict=True,
            ),
            start=1,
        )
        for blank_index in [
            next(
                sentence_index
                for sentence_index, sentence in enumerate(sentences, start=1)
                if f"({index})" in sentence
            )
        ]
    ]
    return f"""
Create the 15 questions for this already co-designed cloze passage.
The passage and blank positions are fixed and must not be changed.

Return JSON satisfying this schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Rules:
- question_index, answer, book_source, difficulty, and grammar_tags must match
  each assignment exactly.
- The answer must be the assigned target_word, preserving only normal sentence
  capitalization where needed.
- stem must copy the exact passage sentence containing the numbered blank.
- Choose context_clue only from that question's allowed_context_clues, and copy
  one entry verbatim.
- Set cloze_tier exactly to required_tier.
- Do not use any sentence that directly contains a synonym, antonym, or
  same-root form of the answer. The clue must require cumulative reading.
- Overall, questions 1-6 are easy, 7-12 are medium, and 13-15 are hard. Hard
  items must require broader inference or close synonym discrimination.
- Four options must be four different single words with the same coarse part of
  speech and one semantic field.
- Never use forms of one lemma as separate options.
- No option or another form of an option may appear in the stem.
- context_clue must be selected verbatim from allowed_context_clues, and
  clue_argument must show how it excludes all three distractors.
- grammar_tags are metadata only. Do not ask grammar-identification questions.
- clue_argument must explicitly explain why each of the three distractors is
  excluded by the supplied context_clue.
- Do not rely on a second plausible answer. If a distractor can also fit, replace
  it with a clearly weaker same-category distractor.
- All three distractors must be near-synonyms or confusable words in the same
  semantic field, never antonyms or unrelated words.
- Prefer the supplied distractor_seed_words. If a seed cannot make a unique
  answer, replace it with another close synonym or clearly confusable word.
- For at least 2 questions, at least one distractor must be a close synonym of
  the answer; context must provide the decisive nuance.
- Avoid lazy contrast sets. For example, do not answer anxious with
  calm/proud/joyful; prefer uneasy/concerned/restless. Do not answer
  opportunity with problem/rule/duty; prefer chance/opening/possibility.
- Do not claim a fixed collocation in clue_argument.

Topic: {schedule["topic"]}

Fixed passage:
{passage_design["passage"]}

Numbered sentences:
{json.dumps([{"sentence_index": index, "text": sentence} for index, sentence in enumerate(passage_design["sentences"], start=1)], ensure_ascii=False, indent=2)}

Assignments:
{json.dumps(assignments, ensure_ascii=False, indent=2)}
""".strip()


def generation_prompt(
    schedule: dict[str, Any],
    schema: dict[str, Any],
    plan: dict[str, Any],
) -> str:
    assignments = [
        {
            "question_index": index,
            "book_source": item["book_source"],
            "difficulty": item["difficulty"],
            "grammar_tags": item["grammar_tags"],
            "allowed_grammar_tags": allowed_tags(item["book_source"]),
        }
        for index, item in enumerate(schedule["questions"], start=1)
    ]
    return f"""
Design one original 15-item lexical cloze passage. Write the passage and
design all 15 blanks together. Do not insert blanks into a pre-existing text.
Target approximately 190 words and never fewer than 170. Build enough coherent
sentences to support 15 separate cross-sentence clues.

Work in this order internally:
1. Use the fixed target-word plan below. Do not replace a target.
2. Write a coherent 170-220 word passage that locks every target through a
   decisive clue in a different sentence.
3. Insert exactly one blank for each target as (1) ______ through (15) ______.
4. Produce the questions and evidence.

Return one JSON object satisfying this schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Hard requirements:
- target_words must contain exactly 15 entries in question order, each equal
  to the accepted answer (case-insensitive).
- Every target word and every option must be a single alphabetic English word,
  not an article, preposition, auxiliary verb, or other function word.
- Every blank tests vocabulary meaning in context, not grammar morphology.
- Four options must be four different words, same part of speech, and one
  semantic field. Never use forms of one lemma as separate options.
- No option or another form of an option may appear in its stem.
- Each context_clue must copy one other complete sentence from the passage,
  including its initial capital letter and final punctuation. It must not be a
  clause, phrase, the blank sentence, or a paraphrase.
- clue_argument must explicitly explain why each of the three distractors is
  excluded by that clue.
- The clue must make one answer uniquely defensible. Do not rely on personal
  preference or an unstated fact.
- Use natural, standard English collocations. Never invent a collocation.
- grammar_tags, book_source, and difficulty must exactly match the assignment.
  Grammar tags are metadata only and must not turn a blank into grammar test.
- If a blank cannot meet these rules, redesign the passage instead of forcing it.

Topic: {schedule["topic"]}
Passage metadata: book_source={schedule["book_source"]},
difficulty={schedule["difficulty"]}

Fixed target plan:
{json.dumps(plan, ensure_ascii=False, indent=2)}

Assignments:
{json.dumps(assignments, ensure_ascii=False, indent=2)}
""".strip()


def validate_generated_bundle(
    *,
    schedule: dict[str, Any],
    schema: dict[str, Any],
    data: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as error:
        raise ValueError(
            "CLOZE_REWRITE_SCHEMA_INVALID "
            f"path={list(error.absolute_path)} message={error.message}"
        ) from error

    passage = data["passage"]
    count = word_count(passage)
    if not 170 <= count <= 220:
        raise ValueError(
            f"WORD_COUNT_OUT_OF_RANGE actual={count} min=170 max=220"
        )
    missing_blanks = [
        index for index in range(1, 16) if f"({index})" not in passage
    ]
    if missing_blanks:
        raise ValueError(f"CLOZE_BLANKS_MISSING {missing_blanks}")

    questions = data["questions"]
    indices = [item["question_index"] for item in questions]
    if indices != list(range(1, 16)):
        raise ValueError(
            f"QUESTION_INDEX_SET_MISMATCH expected={list(range(1, 16))} "
            f"actual={indices}"
        )
    answers = [item["answer"] for item in questions]
    if [
        item.casefold() for item in data["target_words"]
    ] != [item.casefold() for item in answers]:
        raise ValueError(
            "TARGET_WORDS_MISMATCH "
            f"target_words={data['target_words']} answers={answers}"
        )
    if len({item.casefold() for item in data["target_words"]}) != 15:
        raise ValueError("TARGET_WORDS_MUST_BE_UNIQUE")
    planned_words = [
        item["target_word"] for item in plan["targets"]
    ]
    if [
        item.casefold() for item in data["target_words"]
    ] != [item.casefold() for item in planned_words]:
        raise ValueError(
            "GENERATED_TARGETS_DIFFER_FROM_PLAN "
            f"planned={planned_words} "
            f"generated={data['target_words']}"
        )
    invalid_targets = [
        item
        for item in data["target_words"]
        if not re.fullmatch(r"[A-Za-z]+", item)
        or item.casefold() in STOPWORDS
    ]
    if invalid_targets:
        raise ValueError(
            f"TARGET_WORDS_MUST_BE_CONTENT_WORDS {invalid_targets}"
        )

    failures = []
    for index, (question, assignment) in enumerate(
        zip(questions, schedule["questions"], strict=True),
        start=1,
    ):
        if question.get("invalid") is True:
            failures.append(
                {
                    "question_index": index,
                    "code": "MODEL_MARKED_INVALID",
                    "reason": question.get("invalid_reason", ""),
                }
            )
            continue
        if question["stem"] not in passage:
            failures.append(
                {
                    "question_index": index,
                    "code": "STEM_NOT_EXACT_PASSAGE_SENTENCE",
                    "stem": question["stem"],
                }
            )
        if question["answer"] not in question["options"]:
            failures.append(
                {
                    "question_index": index,
                    "code": "ANSWER_NOT_IN_OPTIONS",
                }
            )
        phrase_options = [
            option
            for option in question["options"]
            if not re.fullmatch(r"[A-Za-z]+", option)
        ]
        if phrase_options:
            failures.append(
                {
                    "question_index": index,
                    "code": "OPTIONS_MUST_BE_SINGLE_WORDS",
                    "options": phrase_options,
                }
            )
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
        if question["book_source"] != assignment["book_source"]:
            failures.append(
                {
                    "question_index": index,
                    "code": "BOOK_SOURCE_SCHEDULE_MISMATCH",
                    "expected": assignment["book_source"],
                    "actual": question["book_source"],
                }
            )
        if question["difficulty"] != assignment["difficulty"]:
            failures.append(
                {
                    "question_index": index,
                    "code": "DIFFICULTY_SCHEDULE_MISMATCH",
                    "expected": assignment["difficulty"],
                    "actual": question["difficulty"],
                }
            )
        if question["grammar_tags"] != assignment["grammar_tags"]:
            failures.append(
                {
                    "question_index": index,
                    "code": "GRAMMAR_TAGS_SCHEDULE_MISMATCH",
                    "expected": assignment["grammar_tags"],
                    "actual": question["grammar_tags"],
                }
            )
        try:
            validate_question_book_tag(
                question["grammar_tags"],
                book_tag(question["book_source"]),
            )
        except QuestionValidationError as error:
            failures.append(
                {
                    "question_index": index,
                    "code": "H4_BOOK_TAG_CONFLICT",
                    "message": error.message,
                    "details": error.details,
                }
            )
    failures.extend(validate_cloze_context(passage, questions))
    if failures:
        raise ValueError(
            "CLOZE_REWRITE_HARD_GATE_FAILED "
            + json.dumps(failures, ensure_ascii=False)
        )
    return data


def apply_cloze_distribution_metrics(
    *,
    questions: list[dict[str, Any]],
    sentences: list[str],
) -> dict[str, Any]:
    normalized_sentences = [sentence.strip() for sentence in sentences]
    failures = []
    far_clues = 0
    adjacent_clues = 0
    for question in questions:
        index = question["question_index"]
        blank_index = next(
            (
                sentence_index
                for sentence_index, sentence in enumerate(
                    normalized_sentences,
                    start=1,
                )
                if f"({index})" in sentence
            ),
            None,
        )
        clue = question["context_clue"].strip()
        clue_matches = [
            sentence_index
            for sentence_index, sentence in enumerate(
                normalized_sentences,
                start=1,
            )
            if sentence == clue
        ]
        if blank_index is None or len(clue_matches) != 1:
            failures.append(
                {
                    "question_index": index,
                    "code": "SENTENCE_INDEX_NOT_RESOLVED",
                    "blank_index": blank_index,
                    "clue_matches": clue_matches,
                }
            )
            continue
        clue_index = clue_matches[0]
        distance = abs(clue_index - blank_index)
        question["blank_sentence_index"] = blank_index
        question["clue_sentence_index"] = clue_index
        question["clue_distance"] = distance
        if distance >= 2:
            far_clues += 1
        else:
            adjacent_clues += 1
    if far_clues < 8:
        failures.append(
            {
                "code": "G14_INSUFFICIENT_DISTANT_CLUES",
                "distance_at_least_2": far_clues,
                "minimum": 8,
            }
        )
    if adjacent_clues > 7:
        failures.append(
            {
                "code": "G14_TOO_MANY_ADJACENT_CLUES",
                "distance_at_most_1": adjacent_clues,
                "maximum": 7,
            }
        )
    if not failures:
        adjacent = [
            question for question in questions if question["clue_distance"] <= 1
        ]
        distant = [
            question for question in questions if question["clue_distance"] >= 2
        ]
        if len(adjacent) != 6:
            failures.append(
                {
                    "code": "G15_EASY_DISTANCE_COUNT_INVALID",
                    "actual": len(adjacent),
                    "expected": 6,
                }
            )
        hard = sorted(
            distant,
            key=lambda question: question["clue_distance"],
            reverse=True,
        )[:3]
        hard_ids = {question["question_index"] for question in hard}
        medium = [
            question
            for question in distant
            if question["question_index"] not in hard_ids
        ]
        if len(hard) != 3 or any(question["clue_distance"] < 4 for question in hard):
            failures.append(
                {
                    "code": "G15_HARD_DISTANCE_INSUFFICIENT",
                    "distances": [question["clue_distance"] for question in hard],
                }
            )
        if len(medium) != 6:
            failures.append(
                {
                    "code": "G15_MEDIUM_COUNT_INVALID",
                    "actual": len(medium),
                    "expected": 6,
                }
            )
        if not failures:
            for question in adjacent:
                question["cloze_tier"] = "easy"
            for question in medium:
                question["cloze_tier"] = "medium"
            for question in hard:
                question["cloze_tier"] = "hard"
    if failures:
        raise ValueError(
            "CLOZE_DISTRIBUTION_GATE_FAILED "
            + json.dumps(failures, ensure_ascii=False)
        )
    tier_counts = {
        tier: sum(
            question["cloze_tier"] == tier for question in questions
        )
        for tier in ("easy", "medium", "hard")
    }
    return {
        "tier_distribution": tier_counts,
        "distant_clue_count": far_clues,
        "adjacent_clue_count": adjacent_clues,
        "clue_distances": {
            str(question["question_index"]): question["clue_distance"]
            for question in questions
        },
    }


def validate_distractor_quality(
    questions: list[dict[str, Any]],
    audit_items: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    failures = []
    near_synonym_question_count = 0
    for question in questions:
        index = question["question_index"]
        assessments = audit_items[index]["option_assessments"]
        distractors = [
            assessment
            for assessment in assessments
            if assessment["option"] != question["answer"]
        ]
        lazy_choices = [
            assessment["option"]
            for assessment in distractors
            if assessment["relation_to_answer"] in {"antonym", "unrelated"}
        ]
        if lazy_choices:
            failures.append(
                {
                    "question_index": index,
                    "code": "DISTRACTOR_NOT_IN_SEMANTIC_FIELD",
                    "options": lazy_choices,
                }
            )
        if any(
            assessment["relation_to_answer"] == "near_synonym"
            for assessment in distractors
        ):
            near_synonym_question_count += 1
    if near_synonym_question_count < 2:
        failures.append(
            {
                "code": "INSUFFICIENT_NEAR_SYNONYM_ITEMS",
                "actual": near_synonym_question_count,
                "minimum": 2,
            }
        )
    if failures:
        raise ValueError(
            "DISTRACTOR_QUALITY_GATE_FAILED "
            + json.dumps(failures, ensure_ascii=False)
        )
    return {
        "near_synonym_question_count": near_synonym_question_count,
    }


def judge_prompt(passage: str, questions: list[dict[str, Any]]) -> str:
    payload = []
    for question in questions:
        payload.append(
            {
                "question_index": question["question_index"],
                "blank_sentence": question["stem"],
                "options": question["options"],
                "declared_answer": question["answer"],
                "context_clue": question["context_clue"],
                "clue_argument": question["clue_argument"],
                "answer_collocation_phrase": collocation_phrase(
                    passage,
                    question["question_index"],
                    question["answer"],
                ),
            }
        )
    return f"""
Act as an independent English-item reviewer. Return JSON only.
Assess every option separately; do not merely name the best option.

Required JSON shape:
{{
  "coherence": {{
    "verdict": "coherent or assembled",
    "characters_consistent": true,
    "timeline_present": true,
    "connections_present": true,
    "reason": "name the character continuity, timeline, and linking evidence"
  }},
  "items": [
    {{
      "question_index": 1,
      "option_assessments": [
        {{
          "option_index": 1,
          "option": "exact option text",
          "grammar_ok": true,
          "semantic_ok": true,
          "idiomatic": true,
          "relation_to_answer": "exact, near_synonym, confusable, antonym, or unrelated",
          "reason": "one line"
        }}
      ],
      "context_clue_assessment": {{
        "clue_is_verbatim": true,
        "direct_lexical_relationship": false,
        "supports_answer": true,
        "excludes_distractors": true,
        "reason": "one line"
      }},
      "answer_collocation": {{
        "phrase": "copy answer_collocation_phrase exactly",
        "standard": true,
        "reason": "one line"
      }}
    }}
  ]
}}

Rules:
- G12: judge the whole passage as coherent prose versus assembled independent
  sentences. Set verdict to assembled if characters, timeline, or sentence
  connections do not hold.
- option_assessments must contain exactly four entries in A/B/C/D order.
- For each option, decide whether substituting it into the blank is
  grammatically valid, semantically valid in the full passage, and idiomatic.
- Reasons must be specific. Do not use "the best answer" as a reason.
- For each distractor, label relation_to_answer as near_synonym, confusable,
  antonym, or unrelated. The answer itself uses exact.
- For context_clue_assessment, check that the clue is copied verbatim from a
  non-blank sentence, supports the declared answer by itself, and excludes every
  distractor. The clue must be decisive, not merely related to the same topic.
- G13: set direct_lexical_relationship=true if the clue directly supplies the
  answer's synonym, antonym, or same-root word. Such a clue must be rejected.
- Check answer_collocation_phrase as a standard or fully acceptable English
  sequence in this exact passage. Copy that phrase character-for-character into
  the response. If it is not acceptable, set standard=false.
- A lexical cloze item is valid only if exactly one option is true on all three
  checks. Do not change the declared answer.

Passage:
{passage}

Questions:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def validate_judge_shape(
    questions: list[dict[str, Any]],
    data: dict[str, Any],
) -> dict[str, Any]:
    validate_cross_audit_shape(questions, data)
    return data


def audit_with_pro(
    *,
    judge_client: DeepSeekClient,
    judge_ledger: CostLedger,
    passage: str,
    questions: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    audit_data = run_repair_loop(
        client=judge_client,
        ledger=judge_ledger,
        purpose="judge:cloze:cross-model",
        prompt=judge_prompt(passage, questions),
        validate=lambda data: validate_judge_shape(questions, data),
        max_repair_retries=1,
    )
    expected_collocations = {
        question["question_index"]: collocation_phrase(
            passage,
            question["question_index"],
            question["answer"],
        )
        for question in questions
    }
    validate_cross_audit(
        questions,
        audit_data,
        expected_collocations=expected_collocations,
    )
    return audit_data


def explanation_prompt(
    *,
    passage: str,
    questions: list[dict[str, Any]],
    audit_by_index: dict[int, dict[str, Any]],
    schema: dict[str, Any],
) -> str:
    items = [
        {
            "question_index": question["question_index"],
            "stem": question["stem"],
            "options": question["options"],
            "answer": question["answer"],
            "context_clue": question["context_clue"],
            "clue_argument": question["clue_argument"],
            "cross_judge": audit_by_index[question["question_index"]],
        }
        for question in questions
    ]
    return f"""
Write concise Chinese explanations for these fixed cloze questions.
Return JSON satisfying this schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Each explanation must contain at least three Chinese sentences:
1. Quote or paraphrase the decisive context clue and explain the correct answer.
2. Explain why every distractor fails in this context.
3. State the lexical knowledge point.

Do not invent context. Do not claim a usage is a fixed collocation unless the
supplied cross_judge answer_collocation.standard is true and the reason supports
that exact claim. Do not change any question, answer, or clue.

Passage:
{passage}

Questions and audit:
{json.dumps(items, ensure_ascii=False, indent=2)}
""".strip()


def total_cost(
    generation_ledger: CostLedger,
    judge_ledger: CostLedger,
) -> float:
    return generation_ledger.total_cny + judge_ledger.total_cny


def design_word_count(data: dict[str, Any]) -> int | None:
    sentences = data.get("sentences")
    if not isinstance(sentences, list) or len(sentences) != 16:
        return None
    if any(not isinstance(sentence, str) for sentence in sentences):
        return None
    passage = " ".join(sentence.strip() for sentence in sentences)
    return word_count(passage)


def main() -> None:
    started = time.perf_counter()
    contract = load_json(ROOT / "contracts" / "generation-model.json")
    schedule = load_pilot_schedule()["passages"][0]
    bundle_schema = load_json(SCHEMA_PATH)
    plan_schema = load_json(PLAN_SCHEMA_PATH)
    passage_design_schema = load_json(PASSAGE_DESIGN_SCHEMA_PATH)
    question_batch_schema = load_json(QUESTION_BATCH_SCHEMA_PATH)
    explanation_schema = load_json(EXPLANATION_SCHEMA_PATH)

    generation_contract = {
        **contract,
        "prompt_version": contract["cloze_rewrite_prompt_version"],
    }
    judge_contract = {
        **contract,
        "model_id": contract["judge_model_id"],
        "prompt_version": contract["judge_prompt_version"],
        "price_input_per_1m_cny": contract["judge_price_input_per_1m_cny"],
        "price_output_per_1m_cny": contract["judge_price_output_per_1m_cny"],
        "max_tokens": 8192,
    }
    generation_client = DeepSeekClient(
        generation_contract,
        raw_output_dir=EVIDENCE / "raw-responses-v3",
    )
    judge_client = DeepSeekClient(
        judge_contract,
        raw_output_dir=EVIDENCE / "raw-responses-v3",
    )
    generation_ledger = CostLedger(generation_contract)
    judge_ledger = CostLedger(judge_contract)
    audit_attempts: list[dict[str, Any]] = []
    accepted_audit: dict[int, dict[str, Any]] = {}
    accepted_coherence: dict[str, Any] = {}
    accepted_cloze_metrics: dict[str, Any] = {}
    accepted_distractor_metrics: dict[str, Any] = {}

    available_models = {
        item.get("id") for item in generation_client.list_models()
    }
    required_models = {
        contract["model_id"],
        contract["judge_model_id"],
    }
    if not required_models <= available_models:
        raise RuntimeError(
            "MODEL_ID_NOT_AVAILABLE "
            f"required={sorted(required_models)} "
            f"available={sorted(value for value in available_models if value)}"
        )

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=True,
    ) as connection:
        runtime = connection.execute(
            """
            SELECT inet_server_port() AS port,
                   current_database() AS database_name,
                   (SELECT count(*) FROM practice_sessions) AS sessions
            """
        ).fetchone()
        bank = connection.execute(
            """
            SELECT id::text AS id
            FROM question_banks
            WHERE name='M2 Bank #2'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    if runtime["port"] != 15432 or runtime["database_name"] != "english_practice":
        raise RuntimeError(f"DATABASE_ENDPOINT_MISMATCH {runtime}")
    if not bank:
        raise RuntimeError("M2_BANK_2_NOT_FOUND")

    plan = None
    plan_source = "generated"
    existing_evidence = EVIDENCE / "cloze-rewrite-v3.json"
    if (
        existing_evidence.exists()
        and os.getenv("M2_FRESH_CLOZE_PLAN") != "1"
    ):
        existing_plan = load_json(existing_evidence).get("target_plan")
        if isinstance(existing_plan, dict):
            try:
                plan = validate_plan(
                    schema=plan_schema,
                    data=existing_plan,
                )
                plan_source = "reused_existing_model_plan"
            except (KeyError, TypeError, ValueError):
                plan = None
    if plan is None:
        plan = run_repair_loop(
            client=generation_client,
            ledger=generation_ledger,
            purpose="plan:cloze:targets",
            prompt=plan_prompt(schedule, plan_schema),
            validate=lambda data: validate_plan(
                schema=plan_schema,
                data=data,
            ),
            max_repair_retries=2,
            response_schema=plan_schema,
        )

    design_candidates: list[dict[str, Any]] = []

    def validate_design(data: dict[str, Any]) -> dict[str, Any]:
        design_candidates.append(data)
        return validate_passage_design(
            schema=passage_design_schema,
            plan=plan,
            data=data,
        )

    try:
        passage_design = run_repair_loop(
            client=generation_client,
            ledger=generation_ledger,
            purpose="design:cloze:passage-and-blanks",
            prompt=passage_design_prompt(
                schedule,
                passage_design_schema,
                plan,
            ),
            validate=validate_design,
            max_repair_retries=2,
            response_schema=passage_design_schema,
        )
    except RepairExhausted:
        parseable = [
            (design_word_count(data), data)
            for data in design_candidates
            if design_word_count(data) is not None
        ]
        if not parseable:
            raise
        _count, candidate = min(parseable, key=lambda item: item[0])
        passage_design = run_repair_loop(
            client=generation_client,
            ledger=generation_ledger,
            purpose="compress:cloze:passage-design",
            prompt=compression_prompt(
                schema=passage_design_schema,
                design=candidate,
            ),
            validate=lambda data: validate_passage_design(
                schema=passage_design_schema,
                plan=plan,
                data=data,
            ),
            max_repair_retries=2,
            response_schema=passage_design_schema,
        )

    def validate_question_batch(data: dict[str, Any]) -> dict[str, Any]:
        nonlocal accepted_audit
        nonlocal accepted_coherence
        nonlocal accepted_cloze_metrics
        nonlocal accepted_distractor_metrics
        try:
            jsonschema.validate(data, question_batch_schema)
        except jsonschema.ValidationError as error:
            raise ValueError(
                "CLOZE_QUESTION_BATCH_SCHEMA_INVALID "
                f"path={list(error.absolute_path)} message={error.message}"
            ) from error
        assembled = {
            "target_words": passage_design["target_words"],
            "passage": passage_design["passage"],
            "questions": data["questions"],
        }
        validated = validate_generated_bundle(
            schedule=schedule,
            schema=bundle_schema,
            data=assembled,
            plan=plan,
        )
        questions = validated["questions"]
        cloze_metrics = apply_cloze_distribution_metrics(
            questions=questions,
            sentences=passage_design["sentences"],
        )
        try:
            audit_data = audit_with_pro(
                judge_client=judge_client,
                judge_ledger=judge_ledger,
                passage=validated["passage"],
                questions=questions,
            )
            audit_items = {
                item["question_index"]: item
                for item in audit_data["items"]
            }
            distractor_metrics = validate_distractor_quality(
                questions,
                audit_items,
            )
        except ValueError as error:
            audit_attempts.append(
                {
                    "status": "rejected",
                    "reason": str(error),
                    "passage": validated["passage"],
                    "questions": questions,
                }
            )
            raise
        audit_attempts.append(
            {
                "status": "passed",
                "coherence": audit_data["coherence"],
                "items": audit_data["items"],
                "passage": validated["passage"],
                "questions": questions,
            }
        )
        accepted_audit = audit_items
        accepted_coherence = audit_data["coherence"]
        accepted_cloze_metrics = cloze_metrics
        accepted_distractor_metrics = distractor_metrics
        if total_cost(generation_ledger, judge_ledger) >= RUN_BUDGET_CNY:
            raise RuntimeError("RUN_BUDGET_REACHED")
        if time.perf_counter() - started >= RUN_SECONDS:
            raise RuntimeError("RUN_TIME_REACHED")
        return validated

    bundle = run_repair_loop(
        client=generation_client,
        ledger=generation_ledger,
        purpose="questions:cloze:options-and-evidence",
        prompt=question_batch_prompt(
            schedule=schedule,
            schema=question_batch_schema,
            plan=plan,
            passage_design=passage_design,
        ),
        validate=validate_question_batch,
        max_repair_retries=2,
        response_schema=question_batch_schema,
    )
    questions = bundle["questions"]

    def validate_explanations(data: dict[str, Any]) -> dict[int, str]:
        explanations = _validate_explanation_batch(
            list(range(1, 16)),
            data,
            observations=[],
        )
        too_short = [
            index
            for index, explanation in explanations.items()
            if _sentence_count(explanation) < 3
        ]
        if too_short:
            raise ValueError(
                f"EXPLANATION_SENTENCE_COUNT_TOO_LOW indices={too_short}"
            )
        return explanations

    explanations = run_repair_loop(
        client=generation_client,
        ledger=generation_ledger,
        purpose="explanations:cloze:rewrite-v3",
        prompt=explanation_prompt(
            passage=bundle["passage"],
            questions=questions,
            audit_by_index=accepted_audit,
            schema=explanation_schema,
        ),
        validate=validate_explanations,
        max_repair_retries=2,
        response_schema=explanation_schema,
    )
    for question in questions:
        question["explanation"] = explanations[question["question_index"]]

    record = {
        "type": "cloze",
        "passage_group_id": schedule["passage_group_id"],
        "topic": schedule["topic"],
        "book_source": schedule["book_source"],
        "difficulty": schedule["difficulty"],
        "passage": bundle["passage"],
        "target_words": bundle["target_words"],
        "coherence": accepted_coherence,
        "cloze_metrics": {
            **accepted_cloze_metrics,
            **accepted_distractor_metrics,
            "average_sentence_words": passage_design["metrics"][
                "average_sentence_words"
            ],
            "sentence_count": passage_design["metrics"]["sentence_count"],
            "flesch_reading_ease": passage_design["metrics"][
                "flesch_reading_ease"
            ],
            "complex_structure_count": passage_design["metrics"][
                "complex_structure_count"
            ],
        },
        "questions": questions,
    }
    observations: list[dict[str, Any]] = []
    report = validate_pilot_record(
        record,
        schedule,
        bank_id=bank["id"],
        batch_id=BATCH_ID,
        observations=observations,
    )
    if not report["accepted"]:
        write_json(
            EVIDENCE / "cloze-rewrite-v3.json",
            {
                "status": "hard_gate_failed",
                "record": record,
                "report": report,
                "cross_audit": list(accepted_audit.values()),
                "audit_attempts": audit_attempts,
                "generation_requests": [
                    item.as_dict() for item in generation_client.requests
                ],
                "judge_requests": [
                    item.as_dict() for item in judge_client.requests
                ],
                "cost_cny": total_cost(generation_ledger, judge_ledger),
            },
        )
        raise RuntimeError("CLOZE_REWRITE_HARD_GATE_FAILED")

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        repository = M2Repository(connection)
        with connection.transaction():
            repository.replace_passage_questions(
                bank_id=bank["id"],
                batch_id=BATCH_ID,
                record=record,
            )
        connection.commit()

    generation_cost = generation_ledger.total_cny
    judge_cost = judge_ledger.total_cny
    all_requests = [
        *generation_client.requests,
        *judge_client.requests,
    ]
    result = {
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "port": runtime["port"],
            "name": runtime["database_name"],
            "practice_sessions": runtime["sessions"],
        },
        "bank_id": bank["id"],
        "batch_id": BATCH_ID,
        "transport": generation_contract["transport"],
        "generator_model": generation_contract["model_id"],
        "judge_model": judge_contract["model_id"],
        "generator_prompt_version": generation_contract["prompt_version"],
        "judge_prompt_version": judge_contract["prompt_version"],
        "record": record,
        "target_plan": plan,
        "target_plan_source": plan_source,
        "passage_design": passage_design,
        "report": report,
        "cross_audit": list(accepted_audit.values()),
        "coherence": accepted_coherence,
        "cloze_metrics": record["cloze_metrics"],
        "audit_attempts": audit_attempts,
        "vocabulary_resolutions": report["metrics"][
            "vocabulary_resolutions"
        ],
        "generation_requests": [
            item.as_dict() for item in generation_client.requests
        ],
        "judge_requests": [
            item.as_dict() for item in judge_client.requests
        ],
        "request_count": len(all_requests),
        "failed_attempt_count": sum(
            item.status != "ok" for item in all_requests
        ),
        "finish_reasons": {
            reason: sum(
                item.finish_reason == reason for item in all_requests
            )
            for reason in {
                item.finish_reason for item in all_requests
            }
        },
        "cost_cny": {
            "generator": round(generation_cost, 9),
            "judge": round(judge_cost, 9),
            "total": round(generation_cost + judge_cost, 9),
        },
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    write_json(EVIDENCE / "cloze-rewrite-v3.json", result)
    write_markdown(EVIDENCE / "cloze-rewrite-v3.md", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "questions": len(record["questions"]),
                "word_count": report["metrics"]["word_count"],
                "unknown_words": report["metrics"]["unknown_words"],
                "vocabulary_resolutions": len(
                    report["metrics"]["vocabulary_resolutions"]
                ),
                "cost_cny": result["cost_cny"],
                "duration_seconds": result["duration_seconds"],
                "finish_reasons": result["finish_reasons"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    record = result["record"]
    audit_by_index = {
        item["question_index"]: item for item in result["cross_audit"]
    }
    lines = [
        "# 完形 v3：写文与设空同步生成",
        "",
        f"**G12：** {result['coherence']['verdict']} — {result['coherence']['reason']}",
        "",
        (
            "**G14：** distant_clues="
            f"{result['cloze_metrics']['distant_clue_count']}, "
            "adjacent_clues="
            f"{result['cloze_metrics']['adjacent_clue_count']}"
        ),
        "",
        (
            "**G15：** "
            f"{json.dumps(result['cloze_metrics']['tier_distribution'], ensure_ascii=False)}"
        ),
        "",
        (
            "**G16：** "
            f"sentences={result['cloze_metrics']['sentence_count']}, "
            f"avg_sentence_words={result['cloze_metrics']['average_sentence_words']}, "
            f"flesch={result['cloze_metrics']['flesch_reading_ease']}, "
            f"complex_structures={result['cloze_metrics']['complex_structure_count']}"
        ),
        "",
        record["passage"],
        "",
    ]
    for question in record["questions"]:
        index = question["question_index"]
        lines.extend(
            [
                f"## {index}. {question['stem']}",
                "",
                *[
                    f"{chr(65 + option_index)}. {option}"
                    for option_index, option in enumerate(question["options"])
                ],
                "",
                f"**答案：** {question['answer']}",
                "",
                f"**context_clue：** {question['context_clue']}",
                "",
                f"**线索距离：** {question['clue_distance']} 句",
                "",
                f"**难度档：** {question['cloze_tier']}",
                "",
                (
                    "**G13 direct_lexical_relationship：** "
                    f"{audit_by_index[index]['context_clue_assessment']['direct_lexical_relationship']}"
                ),
                "",
                f"**clue_argument：** {question['clue_argument']}",
                "",
                f"**解析：** {question['explanation']}",
                "",
                "**Pro 逐项判题：**",
                "",
                *[
                    (
                        f"- {assessment['option']}: "
                        f"grammar={assessment['grammar_ok']} "
                        f"semantic={assessment['semantic_ok']} "
                        f"idiomatic={assessment['idiomatic']} — "
                        f"{assessment['reason']}"
                    )
                    for assessment in audit_by_index[index][
                        "option_assessments"
                    ]
                ],
                "",
                (
                    "**H11：** "
                    f"{audit_by_index[index]['answer_collocation']['phrase']} "
                    f"standard="
                    f"{audit_by_index[index]['answer_collocation']['standard']} — "
                    f"{audit_by_index[index]['answer_collocation']['reason']}"
                ),
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
