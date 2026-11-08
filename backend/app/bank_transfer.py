"""Validation and database operations for importable question banks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from .generation import validate_generated_passage


TYPE_QUESTION_COUNTS = {
    "cloze": 15,
    "grammar_fill": 10,
    "reading": 4,
    "gap_fill": 5,
}
TYPE_OPTION_COUNTS = {
    "cloze": 4,
    "grammar_fill": 4,
    "reading": 4,
    "gap_fill": 7,
}
DIFFICULTY_PROFILES = {"standard", "foundation", "advanced"}
TOP_LEVEL_FIELDS = {
    "format_version",
    "name",
    "target_size",
    "difficulty_profile",
    "generated_at",
    "composition",
    "passages",
}
PASSAGE_FIELDS = {
    "type",
    "passage_group_id",
    "topic",
    "book_source",
    "difficulty",
    "word_count",
    "passage",
    "questions",
    "options",
    "validation_profile",
    "generation_observations",
    "flesch_reading_ease",
}
QUESTION_FIELDS = {
    "number",
    "stem",
    "options",
    "answer",
    "explanation",
    "knowledge_points",
    "grammar_tags",
    "book_source",
    "difficulty",
    "evidence_sentence",
    "reading_type",
    "grammar_category",
    "cohesion_type",
    "context_clue",
    "clue_argument",
    "near_synonym_calibration",
}
ROOT = Path(__file__).resolve().parents[2]
M26_CONTRACT = json.loads(
    (ROOT / "contracts" / "m26-generation-params-v2.json").read_text(
        encoding="utf-8"
    )
)
M26_COMPOSITION = M26_CONTRACT["composition"]
M26_TARGET_SIZE = int(M26_COMPOSITION["target_size"])
M26_DIFFICULTY_TARGETS = {
    int(key): int(value)
    for key, value in M26_COMPOSITION["difficulty"].items()
}
M26_BOOK_TARGETS = {
    str(key): int(value)
    for key, value in M26_COMPOSITION["book_distribution"].items()
}
M26_COMPOSITION_TARGETS = {
    str(key): int(value)
    for key, value in M26_COMPOSITION["passages"].items()
}
M26_ALLOWED_TOPICS = set(M26_COMPOSITION["allowed_topics"])
ANSWER_LETTER = re.compile(r"^[A-G]$")
BOOK_SOURCE_PATTERN = re.compile(
    r"^(?:必修[1-3] U[1-5]|选必一 U[1-5]|选必二 U[1-5]|跨册综合)$"
)
GRAMMAR_CATEGORIES = {
    "relative_clauses_defining",
    "relative_clauses_non_defining",
    "passive_voice_tenses",
    "past_participle_nonfinite",
    "v_ing_nonfinite",
    "noun_clauses",
    "adverbial_clauses",
    "noun_clause",
    "relative_clause",
    "adverbial_clause",
    "subjunctive_basic_if",
    "subjunctive_basic_should",
    "partial_inversion_basic",
    "cleft_basic",
    "tense_system",
    "subject_verb_agreement",
    "articles",
    "prepositions",
    "pronouns",
    "conjunctions",
    "word_formation",
    "comparatives_superlatives",
    "with_compound",
    "infinitive_nonfinite",
    "non_finite_perfect_passive",
    "preposition_plus_which",
    "what_noun_clause",
    "subjunctive",
    "inversion",
    "时态语态",
    "冠词",
}
GRAMMAR_IDS = {
    "relative_clauses_defining",
    "relative_clauses_non_defining",
    "passive_voice_tenses",
    "past_participle_nonfinite",
    "v_ing_nonfinite",
    "noun_clauses",
    "adverbial_clauses",
    "subjunctive_basic_if",
    "subjunctive_basic_should",
    "partial_inversion_basic",
    "cleft_basic",
    "tense_system",
    "subject_verb_agreement",
    "articles",
    "prepositions",
    "pronouns",
    "conjunctions",
    "word_formation",
    "comparatives_superlatives",
    "with_compound",
    "infinitive_nonfinite",
}
COHESION_TYPES = {
    "pronoun_reference",
    "logical_connector",
    "lexical_repetition",
    "semantic_contrast",
    "time_order",
    "general_to_specific",
}
UNCHECKED_ESSENTIAL_CODES = {
    "PACKAGE_NOT_OBJECT",
    "BANK_NAME_INVALID",
    "PASSAGES_INVALID",
    "PASSAGE_NOT_OBJECT",
    "PASSAGE_ID_MISSING",
    "PASSAGE_ID_DUPLICATE",
    "PASSAGE_TYPE_INVALID",
    "PASSAGE_TEXT_INVALID",
    "QUESTION_COUNT_INVALID",
    "QUESTION_NOT_OBJECT",
    "OPTIONS_INVALID",
    "OPTION_LABELS_INVALID",
    "GAP_SHARED_OPTIONS_MISMATCH",
    "ANSWER_INVALID",
    "ANSWER_LETTER_INVALID",
    "ANSWER_LETTER_OUT_OF_RANGE",
    "ANSWER_NOT_IN_OPTIONS",
}


@dataclass
class ImportValidationError(Exception):
    errors: list[dict[str, Any]]

    def __str__(self) -> str:
        return "IMPORT_VALIDATION_FAILED"


def _error(
    code: str,
    message: str,
    *,
    passage_id: str | None = None,
    question_index: int | None = None,
    sample: Any = None,
) -> dict[str, Any]:
    result = {
        "code": code,
        "message": message,
        "passage_id": passage_id,
        "question_index": question_index,
    }
    if sample is not None:
        result["sample"] = sample
    return result


def _book_tag(book_source: str) -> str:
    compact = re.sub(r"\s+", "", book_source)
    compact = (
        compact.replace("选必1", "选必一")
        .replace("选必2", "选必二")
        .replace("必修1", "必修一")
        .replace("必修2", "必修二")
        .replace("必修3", "必修三")
    )
    if compact.startswith("选必二"):
        return "选必二"
    if compact.startswith("选必一"):
        return "选必一"
    if compact.startswith("跨册"):
        return "跨册"
    if compact.startswith(("必修", "必修一", "必修二", "必修三")):
        return "必修"
    return ""


def _option_list(
    raw_options: Any,
    expected_count: int,
    errors: list[dict[str, Any]],
    *,
    passage_id: str,
    question_index: int | None,
) -> list[str]:
    if isinstance(raw_options, dict):
        labels = sorted(raw_options)
        if labels != [
            chr(ord("A") + index)
            for index in range(expected_count)
        ]:
            errors.append(
                _error(
                    "OPTION_LABELS_INVALID",
                    "Option labels must be continuous A through the expected label.",
                    passage_id=passage_id,
                    question_index=question_index,
                    sample=list(raw_options),
                )
            )
            return []
        return [str(raw_options[label]).strip() for label in labels]
    if (
        not isinstance(raw_options, list)
        or len(raw_options) != expected_count
        or any(not isinstance(value, str) or not value.strip() for value in raw_options)
    ):
        errors.append(
            _error(
                "OPTIONS_INVALID",
                f"Exactly {expected_count} non-empty options are required.",
                passage_id=passage_id,
                question_index=question_index,
                sample=raw_options,
            )
        )
        return []
    return [value.strip() for value in raw_options]


def normalize_import_package(
    package: dict[str, Any],
    *,
    strict_validation: bool = True,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if not isinstance(package, dict):
        raise ImportValidationError(
            [_error("PACKAGE_NOT_OBJECT", "Import package must be a JSON object.")]
        )
    required_top = TOP_LEVEL_FIELDS if strict_validation else {"name", "passages"}
    unknown = sorted(set(package) - TOP_LEVEL_FIELDS)
    missing = sorted(required_top - set(package))
    if strict_validation and unknown:
        errors.append(
            _error("UNKNOWN_TOP_LEVEL_FIELDS", "Import contains unknown fields.", sample=unknown)
        )
    if missing:
        errors.append(
            _error("MISSING_TOP_LEVEL_FIELDS", "Import is missing required fields.", sample=missing)
        )
    format_version = package.get("format_version")
    if strict_validation and format_version not in {"bank-v1", "m26-v1"}:
        errors.append(
            _error(
                "FORMAT_VERSION_UNSUPPORTED",
                "format_version must be bank-v1 or m26-v1.",
                sample=format_version,
            )
        )
    name = package.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        errors.append(
            _error(
                "BANK_NAME_INVALID",
                "题库名称不能为空，长度必须在 1-80 个字符之间。",
            )
        )
    difficulty_profile = package.get("difficulty_profile")
    if strict_validation and difficulty_profile not in DIFFICULTY_PROFILES:
        errors.append(
            _error(
                "DIFFICULTY_PROFILE_INVALID",
                "difficulty_profile must be standard, foundation, or advanced.",
            )
        )
    target_size = package.get("target_size")
    if strict_validation and (
        not isinstance(target_size, int) or target_size <= 0
    ):
        errors.append(_error("TARGET_SIZE_INVALID", "target_size must be a positive integer."))
        target_size = 0
    composition = package.get("composition")
    raw_passages = package.get("passages")
    if not isinstance(composition, dict):
        if strict_validation:
            errors.append(
                _error("COMPOSITION_INVALID", "composition must be an object.")
            )
        composition = {}
    if not isinstance(raw_passages, list) or not raw_passages:
        errors.append(_error("PASSAGES_INVALID", "passages must be a non-empty array."))
        raw_passages = []

    records: list[dict[str, Any]] = []
    actual_composition = {key: 0 for key in TYPE_QUESTION_COUNTS}
    seen_passages: set[str] = set()
    for passage_index, raw in enumerate(raw_passages, start=1):
        if not isinstance(raw, dict):
            errors.append(
                _error(
                    "PASSAGE_NOT_OBJECT",
                    "Passage must be a JSON object.",
                    sample=passage_index,
                )
            )
            continue
        passage_id = str(raw.get("passage_group_id", "")).strip()
        passage_type = raw.get("type")
        if not passage_id:
            errors.append(_error("PASSAGE_ID_MISSING", "passage_group_id is required."))
        elif passage_id in seen_passages:
            errors.append(
                _error(
                    "PASSAGE_ID_DUPLICATE",
                    "passage_group_id must be unique within the import.",
                    passage_id=passage_id,
                )
            )
        seen_passages.add(passage_id)
        if passage_type not in TYPE_QUESTION_COUNTS:
            errors.append(
                _error(
                    "PASSAGE_TYPE_INVALID",
                    "Unknown passage type.",
                    passage_id=passage_id,
                    sample=passage_type,
                )
            )
            continue
        unknown_passage = sorted(set(raw) - PASSAGE_FIELDS)
        if strict_validation and unknown_passage:
            errors.append(
                _error(
                    "UNKNOWN_PASSAGE_FIELDS",
                    "Passage contains unknown fields.",
                    passage_id=passage_id,
                    sample=unknown_passage,
                )
            )
        passage = raw.get("passage")
        topic = raw.get("topic")
        book_source = raw.get("book_source")
        difficulty = raw.get("difficulty")
        if not isinstance(passage, str) or not passage.strip():
            errors.append(
                _error("PASSAGE_TEXT_INVALID", "passage must be non-empty.", passage_id=passage_id)
            )
            passage = ""
        if not isinstance(topic, str) or not topic.strip():
            errors.append(_error("TOPIC_INVALID", "topic must be non-empty.", passage_id=passage_id))
            topic = "未分类"
        if (
            not isinstance(book_source, str)
            or not BOOK_SOURCE_PATTERN.fullmatch(book_source)
            or not _book_tag(book_source)
        ):
            errors.append(
                _error(
                    "BOOK_SOURCE_FORMAT_INVALID",
                    "book_source must use the canonical book-source format.",
                    passage_id=passage_id,
                    sample=book_source,
                )
            )
            book_source = "跨册综合"
        if not isinstance(difficulty, int) or not 1 <= difficulty <= 5:
            errors.append(
                _error(
                    "PASSAGE_DIFFICULTY_INVALID",
                    "difficulty must be 1-5.",
                    passage_id=passage_id,
                    sample=difficulty,
                )
            )
            difficulty = 3
        raw_questions = raw.get("questions")
        expected_questions = TYPE_QUESTION_COUNTS[passage_type]
        if not isinstance(raw_questions, list) or len(raw_questions) != expected_questions:
            errors.append(
                _error(
                    "QUESTION_COUNT_INVALID",
                    f"{passage_type} must contain {expected_questions} questions.",
                    passage_id=passage_id,
                    sample=len(raw_questions) if isinstance(raw_questions, list) else None,
                )
            )
            continue
        actual_composition[passage_type] += 1
        passage_options: list[str] = []
        if passage_type == "gap_fill":
            if "options" in raw:
                passage_options = _option_list(
                    raw.get("options"),
                    TYPE_OPTION_COUNTS[passage_type],
                    errors,
                    passage_id=passage_id,
                    question_index=None,
                )
            else:
                candidate_options = [
                    _option_list(
                        question.get("options"),
                        TYPE_OPTION_COUNTS[passage_type],
                        errors,
                        passage_id=passage_id,
                        question_index=index,
                    )
                    for index, question in enumerate(raw_questions, start=1)
                    if isinstance(question, dict)
                ]
                if candidate_options:
                    passage_options = candidate_options[0]
                    if any(
                        options != passage_options
                        for options in candidate_options[1:]
                    ):
                        errors.append(
                            _error(
                                "GAP_SHARED_OPTIONS_MISMATCH",
                                "All gap-fill questions must use the same seven options.",
                                passage_id=passage_id,
                            )
                        )
        questions: list[dict[str, Any]] = []
        for question_index, raw_question in enumerate(raw_questions, start=1):
            qerrors: list[dict[str, Any]] = []
            if not isinstance(raw_question, dict):
                errors.append(
                    _error(
                        "QUESTION_NOT_OBJECT",
                        "Question must be a JSON object.",
                        passage_id=passage_id,
                        question_index=question_index,
                    )
                )
                continue
            unknown_question = sorted(set(raw_question) - QUESTION_FIELDS)
            if strict_validation and unknown_question:
                errors.append(
                    _error(
                        "UNKNOWN_QUESTION_FIELDS",
                        "Question contains unknown fields.",
                        passage_id=passage_id,
                        question_index=question_index,
                        sample=unknown_question,
                    )
                )
            number = raw_question.get("number", question_index)
            if number != question_index:
                errors.append(
                    _error(
                        "QUESTION_NUMBER_INVALID",
                        "Question numbers must be continuous and ordered.",
                        passage_id=passage_id,
                        question_index=question_index,
                        sample=number,
                    )
                )
            stem = str(raw_question.get("stem", "")).strip()
            if passage_type == "reading" and not stem:
                errors.append(
                    _error(
                        "STEM_MISSING",
                        "Reading question stem is required.",
                        passage_id=passage_id,
                        question_index=question_index,
                    )
                )
            if not stem:
                stem = (
                    f"Choose the best option for blank {question_index}."
                    if passage_type != "gap_fill"
                    else f"Choose the sentence that best fits blank ({question_index})."
                )
            options = (
                passage_options
                if passage_type == "gap_fill"
                else _option_list(
                    raw_question.get("options"),
                    TYPE_OPTION_COUNTS[passage_type],
                    errors,
                    passage_id=passage_id,
                    question_index=question_index,
                )
            )
            answer = raw_question.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                errors.append(
                    _error(
                        "ANSWER_INVALID",
                        "answer must be a non-empty string.",
                        passage_id=passage_id,
                        question_index=question_index,
                    )
                )
                answer = ""
            elif passage_type == "gap_fill":
                if not ANSWER_LETTER.fullmatch(answer.strip().upper()):
                    errors.append(
                        _error(
                            "ANSWER_LETTER_INVALID",
                            "Gap-fill answer must be A-G.",
                            passage_id=passage_id,
                            question_index=question_index,
                            sample=answer,
                        )
                    )
                answer = answer.strip().upper()
            elif ANSWER_LETTER.fullmatch(answer.strip().upper()):
                option_index = ord(answer.strip().upper()) - ord("A")
                if not 0 <= option_index < len(options):
                    errors.append(
                        _error(
                            "ANSWER_LETTER_OUT_OF_RANGE",
                            "Answer letter does not match an option.",
                            passage_id=passage_id,
                            question_index=question_index,
                            sample=answer,
                        )
                    )
                else:
                    answer = options[option_index]
            elif answer not in options:
                errors.append(
                    _error(
                        "ANSWER_NOT_IN_OPTIONS",
                        "Answer must match one option.",
                        passage_id=passage_id,
                        question_index=question_index,
                        sample=answer,
                    )
                )
            explanation = raw_question.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                errors.append(
                    _error(
                        "EXPLANATION_INVALID",
                        "explanation must be non-empty.",
                        passage_id=passage_id,
                        question_index=question_index,
                    )
                )
                explanation = "导入时未提供解析。"
            grammar_tags = raw_question.get("grammar_tags")
            if (
                not isinstance(grammar_tags, list)
                or not grammar_tags
                or any(not isinstance(tag, str) or not tag for tag in grammar_tags)
                or any(tag not in GRAMMAR_IDS for tag in grammar_tags)
            ):
                errors.append(
                    _error(
                        "GRAMMAR_TAGS_INVALID",
                        "grammar_tags must be a non-empty list.",
                        passage_id=passage_id,
                        question_index=question_index,
                    )
                )
                grammar_tags = []
            if not grammar_tags:
                grammar_tags = ["tense_system"]
            question_difficulty = raw_question.get("difficulty", difficulty)
            question_book_source = raw_question.get("book_source", book_source)
            if (
                not isinstance(question_difficulty, int)
                or not 1 <= question_difficulty <= 5
            ):
                question_difficulty = difficulty
            if (
                not isinstance(question_book_source, str)
                or not BOOK_SOURCE_PATTERN.fullmatch(question_book_source)
                or not _book_tag(question_book_source)
            ):
                errors.append(
                    _error(
                        "BOOK_SOURCE_FORMAT_INVALID",
                        "Question book_source must use the canonical book-source format.",
                        passage_id=passage_id,
                        question_index=question_index,
                        sample=question_book_source,
                    )
                )
                question_book_source = book_source
            grammar_category = raw_question.get("grammar_category")
            if (
                grammar_category is not None
                and grammar_category not in GRAMMAR_CATEGORIES
            ):
                errors.append(
                    _error(
                        "GRAMMAR_CATEGORY_INVALID",
                        "grammar_category is outside the frozen category set.",
                        passage_id=passage_id,
                        question_index=question_index,
                        sample=grammar_category,
                    )
                )
            cohesion_type = raw_question.get("cohesion_type")
            if cohesion_type is not None and cohesion_type not in COHESION_TYPES:
                errors.append(
                    _error(
                        "COHESION_TYPE_INVALID",
                        "cohesion_type is outside the frozen category set.",
                        passage_id=passage_id,
                        question_index=question_index,
                        sample=cohesion_type,
                    )
                )
            knowledge_points = raw_question.get("knowledge_points")
            if (
                not isinstance(knowledge_points, list)
                or not knowledge_points
            ):
                knowledge_points = [
                    f"import:{passage_type}:{question_index}"
                ]
            question = {
                "stem": stem,
                "options": options,
                "answer": answer,
                "explanation": str(explanation or "").strip(),
                "knowledge_points": knowledge_points,
                "grammar_tags": grammar_tags,
                "book_source": question_book_source,
                "difficulty": question_difficulty,
            }
            for field in (
                "evidence_sentence",
                "reading_type",
                "grammar_category",
                "cohesion_type",
                "context_clue",
                "clue_argument",
                "near_synonym_calibration",
            ):
                if field in raw_question:
                    question[field] = raw_question[field]
            questions.append(question)
        validation_profile = (
            raw.get("validation_profile")
            or ("m26" if format_version == "m26-v1" else "m2")
        )
        record = {
            "validation_profile": validation_profile,
            "type": passage_type,
            "passage_group_id": passage_id,
            "topic": topic,
            "book_source": book_source,
            "difficulty": difficulty,
            "passage": passage,
            "questions": questions,
        }
        records.append(record)

    question_count = sum(len(record["questions"]) for record in records)
    if strict_validation:
        if question_count != target_size:
            errors.append(
                _error(
                    "TARGET_SIZE_MISMATCH",
                    f"target_size={target_size} but import contains {question_count} questions.",
                )
            )
        for type_, expected in TYPE_QUESTION_COUNTS.items():
            declared = composition.get(type_, 0)
            actual = actual_composition[type_]
            if declared != actual:
                errors.append(
                    _error(
                        "COMPOSITION_MISMATCH",
                        f"{type_} composition={declared} but import contains {actual} passages.",
                    )
                )
    else:
        target_size = question_count
        if question_count <= 0:
            errors.append(
                _error(
                    "TARGET_SIZE_INVALID",
                    "导入包中没有可写入的题目。",
                )
            )

    if strict_validation and format_version == "m26-v1":
        profile_mismatches = [
            {
                "passage_group_id": record["passage_group_id"],
                "validation_profile": record["validation_profile"],
            }
            for record in records
            if record["validation_profile"] != "m26"
        ]
        if profile_mismatches:
            errors.append(
                _error(
                    "M26_PROFILE_MISMATCH",
                    "m26-v1 requires every passage to use validation_profile=m26.",
                    sample=profile_mismatches,
                )
            )
        if target_size != M26_TARGET_SIZE:
            errors.append(
                _error(
                    "M26_TARGET_SIZE_INVALID",
                    f"m26-v1 packages must contain exactly {M26_TARGET_SIZE} questions.",
                    sample=target_size,
                )
            )
        for type_, expected in M26_COMPOSITION_TARGETS.items():
            if actual_composition[type_] != expected:
                errors.append(
                    _error(
                        "M26_COMPOSITION_INVALID",
                        f"m26-v1 requires {expected} {type_} passages.",
                        sample={
                            "type": type_,
                            "actual": actual_composition[type_],
                            "expected": expected,
                        },
                    )
                )
        difficulty_counts = {value: 0 for value in range(1, 6)}
        book_counts = {key: 0 for key in M26_BOOK_TARGETS}
        topic_counts: dict[str, int] = {}
        for record in records:
            topic_counts[record["topic"]] = topic_counts.get(record["topic"], 0) + 1
            for question in record["questions"]:
                if (
                    isinstance(question["difficulty"], int)
                    and question["difficulty"] in difficulty_counts
                ):
                    difficulty_counts[question["difficulty"]] += 1
                book = _book_tag(question["book_source"])
                if book:
                    book_counts[book] += 1
        if difficulty_counts != M26_DIFFICULTY_TARGETS:
            errors.append(
                _error(
                    "M26_DIFFICULTY_DISTRIBUTION_INVALID",
                    "Difficulty distribution does not match the M2.6 contract.",
                    sample=difficulty_counts,
                )
            )
        if book_counts != M26_BOOK_TARGETS:
            errors.append(
                _error(
                    "M26_BOOK_DISTRIBUTION_INVALID",
                    "Book distribution does not match the M2.6 contract.",
                    sample=book_counts,
                )
            )
        invalid_topics = sorted(set(topic_counts) - M26_ALLOWED_TOPICS)
        if invalid_topics:
            errors.append(
                _error(
                    "M26_TOPIC_INVALID",
                    "Import contains topics outside the M2.6 list.",
                    sample=invalid_topics,
                )
            )
        if len(topic_counts) < 15 or any(
            count > 6 for count in topic_counts.values()
        ):
            errors.append(
                _error(
                    "M26_TOPIC_DISTRIBUTION_INVALID",
                    "M2.6 requires at least 15 topics and at most 6 passages per topic.",
                    sample=topic_counts,
                )
            )
    if not strict_validation:
        errors = [
            error
            for error in errors
            if error["code"] in UNCHECKED_ESSENTIAL_CODES
        ]
    if errors:
        raise ImportValidationError(errors)

    if strict_validation:
        machine_failures: list[dict[str, Any]] = []
        for record in records:
            if record["validation_profile"] == "stored":
                continue
            report = validate_generated_passage(record)
            if report.accepted:
                continue
            for failure in report.failures:
                machine_failures.append(
                    {
                        **failure.as_dict(),
                        "passage_id": record["passage_group_id"],
                    }
                )
        if machine_failures:
            raise ImportValidationError(machine_failures)
    return {
        "name": name.strip(),
        "target_size": target_size,
        "difficulty_profile": (
            difficulty_profile
            if difficulty_profile in DIFFICULTY_PROFILES
            else "standard"
        ),
        "generated_at": package.get("generated_at"),
        "composition": actual_composition,
        "records": records,
        "import_sha256": hashlib.sha256(
            json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }


def _coverage(normalized: dict[str, Any]) -> dict[str, Any]:
    records = normalized["records"]
    questions = [question for record in records for question in record["questions"]]
    difficulty = {str(value): 0 for value in range(1, 6)}
    books = {"选必二": 0, "选必一": 0, "必修": 0, "跨册": 0}
    topics: dict[str, int] = {}
    for question in questions:
        difficulty[str(question["difficulty"])] += 1
        book = _book_tag(question["book_source"])
        if book:
            books[book] += 1
    for record in records:
        topics[record["topic"]] = topics.get(record["topic"], 0) + 1
    return {
        "question_counts": {
            type_: sum(
                len(record["questions"])
                for record in records
                if record["type"] == type_
            )
            for type_ in TYPE_QUESTION_COUNTS
        },
        "passage_counts": normalized["composition"],
        "difficulty_distribution": difficulty,
        "book_distribution": books,
        "topic_distribution": topics,
        "out_of_scope_rate": 0,
        "passage_duplicate_rate": 0,
        "stem_duplicate_rate": 0,
        "grammar_fill_coverage": {},
        "imported": True,
        "switchable": True,
        "import_sha256": normalized["import_sha256"],
        "generated_at": normalized.get("generated_at"),
    }


def preview_import(connection, package: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_import_package(package)
    existing = connection.execute(
        "SELECT id::text AS id FROM question_banks WHERE lower(name)=lower(%s)",
        (normalized["name"],),
    ).fetchone()
    if existing:
        raise ImportValidationError(
            [
                _error(
                    "BANK_NAME_EXISTS",
                    "题库名称已存在，请换一个名称。",
                    sample=normalized["name"],
                )
            ]
        )
    return {
        "valid": True,
        "summary": {
            "name": normalized["name"],
            "target_size": normalized["target_size"],
            "passages": len(normalized["records"]),
            "questions": sum(
                len(record["questions"])
                for record in normalized["records"]
            ),
            "composition": normalized["composition"],
        },
        "errors": [],
    }


def export_bank(connection, bank_id: str) -> dict[str, Any]:
    bank = connection.execute(
        """
        SELECT id::text AS id, name, difficulty_profile
        FROM question_banks
        WHERE id=%s
        """,
        (bank_id,),
    ).fetchone()
    if not bank:
        raise KeyError("BANK_NOT_FOUND")

    passage_rows = connection.execute(
        """
        SELECT passage_group_id, type, content, word_count, topic,
               book_source, difficulty
        FROM passages
        WHERE bank_id=%s
        ORDER BY
            CASE type
                WHEN 'cloze' THEN 1
                WHEN 'grammar_fill' THEN 2
                WHEN 'reading' THEN 3
                WHEN 'gap_fill' THEN 4
                ELSE 5
            END,
            passage_group_id
        """,
        (bank_id,),
    ).fetchall()
    question_rows = connection.execute(
        """
        SELECT passage_group_id, stem, options, answer, explanation,
               knowledge_points, grammar_tags, book_source, difficulty
        FROM questions
        WHERE bank_id=%s
        ORDER BY passage_group_id, id
        """,
        (bank_id,),
    ).fetchall()

    questions_by_passage: dict[str, list[dict[str, Any]]] = {}
    for row in question_rows:
        questions = questions_by_passage.setdefault(row["passage_group_id"], [])
        questions.append(
            {
                "number": len(questions) + 1,
                "stem": row["stem"],
                "options": row["options"],
                "answer": row["answer"],
                "explanation": row["explanation"],
                "knowledge_points": row["knowledge_points"],
                "grammar_tags": row["grammar_tags"],
                "book_source": row["book_source"],
                "difficulty": row["difficulty"],
            }
        )

    composition = {key: 0 for key in TYPE_QUESTION_COUNTS}
    passages = []
    for row in passage_rows:
        composition[row["type"]] += 1
        passage_questions = questions_by_passage.get(row["passage_group_id"], [])
        exported_passage = {
            "validation_profile": "stored",
            "type": row["type"],
            "passage_group_id": row["passage_group_id"],
            "topic": row["topic"],
            "book_source": row["book_source"],
            "difficulty": row["difficulty"],
            "word_count": row["word_count"],
            "passage": row["content"],
            "questions": passage_questions,
        }
        if row["type"] == "gap_fill" and passage_questions:
            exported_passage["options"] = passage_questions[0]["options"]
        passages.append(exported_passage)

    return {
        "format_version": "bank-v1",
        "name": bank["name"],
        "target_size": len(question_rows),
        "difficulty_profile": bank["difficulty_profile"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "composition": composition,
        "passages": passages,
    }


def import_bank(
    connection,
    package: dict[str, Any],
    *,
    strict_validation: bool = True,
) -> dict[str, Any]:
    normalized = normalize_import_package(
        package,
        strict_validation=strict_validation,
    )
    existing = connection.execute(
        "SELECT id::text AS id FROM question_banks WHERE lower(name)=lower(%s)",
        (normalized["name"],),
    ).fetchone()
    if existing:
        raise ImportValidationError(
            [
                _error(
                    "BANK_NAME_EXISTS",
                    "题库名称已存在，请换一个名称。",
                    sample=normalized["name"],
                )
            ]
        )
    active = connection.execute(
        """
        SELECT qb.id::text AS id
        FROM bank_active_state bas
        JOIN question_banks qb ON qb.id=bas.active_bank_id
        WHERE bas.singleton=TRUE
        """
    ).fetchone()
    active_id = active["id"] if active else None
    bank_id = str(uuid4())
    coverage = _coverage(normalized)
    connection.execute(
        """
        INSERT INTO question_banks
            (id, name, target_size, difficulty_profile, status, coverage_snapshot)
        VALUES (%s, %s, %s, %s, 'draft', %s)
        """,
        (
            bank_id,
            normalized["name"],
            normalized["target_size"],
            normalized["difficulty_profile"],
            Jsonb(coverage),
        ),
    )
    short_bank = bank_id.replace("-", "")[:8]
    for record in normalized["records"]:
        connection.execute(
            """
            INSERT INTO passages
                (passage_group_id, bank_id, type, content, word_count, topic,
                 book_source, difficulty, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'published')
            """,
            (
                record["passage_group_id"],
                bank_id,
                record["type"],
                record["passage"],
                len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", record["passage"])),
                record["topic"],
                record["book_source"],
                record["difficulty"],
            ),
        )
        for index, question in enumerate(record["questions"], start=1):
            question_id = (
                f"IMP-{short_bank}-{record['passage_group_id'][:40]}-"
                f"Q{index:02d}"
            )
            connection.execute(
                """
                INSERT INTO questions
                    (id, bank_id, type, passage_group_id, stem, options, answer,
                     explanation, knowledge_points, grammar_tags, book_source,
                     difficulty, status, batch_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'published', 'BANK-IMPORT')
                """,
                (
                    question_id,
                    bank_id,
                    record["type"],
                    record["passage_group_id"],
                    question["stem"],
                    Jsonb(question["options"]),
                    Jsonb(question["answer"]),
                    question["explanation"],
                    question["knowledge_points"],
                    question["grammar_tags"],
                    question["book_source"],
                    question["difficulty"],
                ),
            )
    if active_id:
        connection.execute(
            "UPDATE question_banks SET status='archived', finished_at=now() WHERE id=%s",
            (active_id,),
        )
    connection.execute(
        "UPDATE question_banks SET status='active', finished_at=now() WHERE id=%s",
        (bank_id,),
    )
    connection.execute(
        """
        INSERT INTO bank_switch_log
            (from_bank_id, to_bank_id, operator)
        VALUES (%s, %s, %s)
        """,
        (active_id, bank_id, "bank_import"),
    )
    connection.execute(
        """
        INSERT INTO bank_audit_logs
            (bank_id, action, previous_bank_id, actor, details)
        VALUES (%s, 'imported_and_activated', %s, 'student_ui', %s)
        """,
        (bank_id, active_id, Jsonb(coverage)),
    )
    return {
        "bank_id": bank_id,
        "name": normalized["name"],
        "status": "active",
        "previous_bank_id": active_id,
        "summary": {
            "passages": len(normalized["records"]),
            "questions": normalized["target_size"],
            "composition": normalized["composition"],
        },
    }


def delete_preview(connection, bank_id: str) -> dict[str, Any]:
    bank = connection.execute(
        """
        SELECT qb.id::text AS id, qb.name, qb.status,
               (SELECT count(*) FROM passages p WHERE p.bank_id=qb.id) AS passages,
               (SELECT count(*) FROM questions q WHERE q.bank_id=qb.id) AS questions,
               (SELECT count(*) FROM practice_sessions s WHERE s.bank_id=qb.id) AS sessions,
               (SELECT count(*) FROM practice_reports r WHERE r.bank_id=qb.id) AS reports,
               (SELECT count(*) FROM question_attempts a WHERE a.bank_id=qb.id) AS attempts,
               (SELECT count(*) FROM mistake_items m WHERE m.bank_id=qb.id) AS mistakes
        FROM question_banks qb
        WHERE qb.id=%s
        """,
        (bank_id,),
    ).fetchone()
    if not bank:
        raise KeyError("BANK_NOT_FOUND")
    active = connection.execute(
        "SELECT active_bank_id::text AS id FROM bank_active_state WHERE singleton=TRUE"
    ).fetchone()
    active_id = active["id"] if active else None
    if bank_id == active_id:
        raise ValueError("ACTIVE_BANK_CANNOT_BE_DELETED")
    running_jobs = connection.execute(
        """
        SELECT count(*) AS count
        FROM generation_jobs
        WHERE bank_id=%s
          AND status IN ('queued','running','paused_for_review','paused_for_owner')
        """,
        (bank_id,),
    ).fetchone()["count"]
    return {
        "bank_id": bank["id"],
        "name": bank["name"],
        "status": bank["status"],
        "passages": bank["passages"],
        "questions": bank["questions"],
        "sessions": bank["sessions"],
        "reports": bank["reports"],
        "attempts": bank["attempts"],
        "mistakes": bank["mistakes"],
        "can_delete": running_jobs == 0,
        "blocking_reason": None if running_jobs == 0 else "BANK_GENERATION_IN_PROGRESS",
    }


def delete_bank(connection, bank_id: str) -> dict[str, Any]:
    preview = delete_preview(connection, bank_id)
    if not preview["can_delete"]:
        raise ValueError(preview["blocking_reason"] or "BANK_CANNOT_BE_DELETED")
    connection.execute(
        """
        DELETE FROM error_tag_successes
        WHERE session_id IN (
            SELECT id FROM practice_sessions WHERE bank_id=%s
        )
        OR tag_id IN (
            SELECT id FROM error_tags WHERE bank_id=%s
        )
        """,
        (bank_id, bank_id),
    )
    connection.execute(
        "DELETE FROM saved_answers WHERE session_id IN (SELECT id FROM practice_sessions WHERE bank_id=%s)",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM question_attempts WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM practice_reports WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM report_deletions WHERE session_id IN (SELECT id FROM practice_sessions WHERE bank_id=%s)",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM error_tags WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM session_items WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM practice_sessions WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM mistake_items WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM rejected_questions WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM generation_batches WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM generation_jobs WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM generation_approvals WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM bank_switch_log WHERE from_bank_id=%s OR to_bank_id=%s",
        (bank_id, bank_id),
    )
    connection.execute(
        "DELETE FROM bank_audit_logs WHERE bank_id=%s OR previous_bank_id=%s",
        (bank_id, bank_id),
    )
    connection.execute(
        "DELETE FROM admin_audit_log WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM questions WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM passages WHERE bank_id=%s",
        (bank_id,),
    )
    connection.execute(
        "DELETE FROM question_banks WHERE id=%s",
        (bank_id,),
    )
    return preview
