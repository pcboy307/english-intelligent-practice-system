"""Generation contracts, seven-gate validation and cost accounting for M2."""

from __future__ import annotations

import importlib.util
import json
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import httpx

from .readability import flesch_reading_ease
from .question_validation import (
    QuestionValidationError,
    validate_question_book_tag,
)


ROOT = Path(__file__).resolve().parents[2]


class GateCategory(StrEnum):
    WORD_COUNT = "word_count"
    STRUCTURE = "structure"
    PLACEHOLDER_INTEGRITY = "placeholder_integrity"
    GAP_OPTION_LEAK = "gap_option_leak"
    VOCABULARY_SCOPE = "vocabulary_scope"
    UNKNOWN_RATIO = "unknown_ratio"
    QUESTION_COUNT = "question_count"
    GRAMMAR_TAG = "grammar_tag"
    BOOK_TAG = "book_tag"
    M26_FORM = "m26_form"
    M26_READING = "m26_reading"
    M26_COHESION = "m26_cohesion"
    M26_VOCABULARY = "m26_vocabulary"


@dataclass(frozen=True)
class GateFailure:
    category: GateCategory
    message: str
    question_index: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "question_index": self.question_index,
            "details": self.details,
        }


@dataclass
class PassageValidationReport:
    accepted: bool
    failures: list[GateFailure]
    metrics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "failures": [failure.as_dict() for failure in self.failures],
            "metrics": self.metrics,
        }


@dataclass
class GenerationResult:
    record: dict[str, Any]
    attempts: list[dict[str, Any]]
    metrics: dict[str, Any]


class GenerationExhausted(RuntimeError):
    def __init__(
        self,
        *,
        attempts: list[dict[str, Any]],
        metrics: dict[str, Any],
    ) -> None:
        super().__init__("GENERATION_GATES_FAILED_AFTER_RETRIES")
        self.attempts = attempts
        self.metrics = metrics


class TokenBudgetExceeded(RuntimeError):
    def __init__(
        self,
        *,
        attempts: list[dict[str, Any]],
        metrics: dict[str, Any],
        token_cap: int,
    ) -> None:
        super().__init__("GENERATION_TOKEN_BUDGET_EXCEEDED")
        self.attempts = attempts
        self.metrics = metrics
        self.token_cap = token_cap


class GenerationClient:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.http_client = http_client or httpx.Client(
            timeout=float(config["timeout_seconds"])
        )

    def generate(
        self,
        passage_type: str,
        prompt: str,
    ) -> tuple[dict[str, Any], int, int, float]:
        payload = {
            "model": self.config["model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You author original high-school English practice material. "
                        "Return one strict JSON object only. Do not use Markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": float(self.config["temperature"]),
            "max_tokens": int(self.config["max_tokens"][passage_type]),
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        started = time.perf_counter()
        response = self.http_client.post(self.config["endpoint"], json=payload)
        response.raise_for_status()
        elapsed = time.perf_counter() - started
        record, prompt_tokens, completion_tokens = parse_model_response(
            response.json()
        )
        return record, prompt_tokens, completion_tokens, elapsed


TYPE_RULES = {
    "cloze": {
        "questions": 15,
        "min_words": 170,
        "max_words": 220,
        "options": 4,
    },
    "grammar_fill": {
        "questions": 10,
        "min_words": 120,
        "max_words": 180,
        "options": 4,
    },
    "reading": {
        "questions": 4,
        "min_words": 1,
        "max_words": 250,
        "options": 4,
    },
    "gap_fill": {
        "questions": 5,
        "min_words": 1,
        "max_words": 220,
        "options": 7,
    },
}

M26_TYPE_RULES = {
    "cloze": {
        "questions": 15,
        "min_words": 200,
        "max_words": 290,
        "options": 4,
    },
    "grammar_fill": {
        "questions": 10,
        "min_words": 1,
        "max_words": 220,
        "options": 4,
    },
    "reading": {
        "questions": 4,
        "min_words": 250,
        "max_words": 380,
        "options": 4,
    },
    "gap_fill": {
        "questions": 5,
        "min_words": 220,
        "max_words": 350,
        "options": 7,
    },
}
M26_READING_TYPES = {
    "main_idea",
    "detail",
    "inference",
    "vocabulary_in_context",
    "purpose_or_attitude",
}
M26_HIGHER_ORDER_READING_TYPES = {
    "main_idea",
    "inference",
    "vocabulary_in_context",
    "purpose_or_attitude",
}
M26_COHESION_TYPES = {
    "pronoun_reference",
    "logical_connector",
    "lexical_repetition",
    "time_order",
    "general_to_specific",
}
READING_META_PATTERN = re.compile(
    r"which sentence contains|哪一句含有|contains a .* (?:clause|construction|voice)|含.*(?:从句|语态)",
    re.IGNORECASE,
)

FILL_PLACEHOLDER = "______"
PLACEHOLDER_TYPES = {"cloze", "grammar_fill", "gap_fill"}
GAP_OPTION_OVERLAP_WORDS = 6
ANSWER_TOKEN_PATTERN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
ANSWER_INFLECTION_RULES = frozenset(
    {
        "exact",
        "irregular_inflection",
        "plural_ies_to_y",
        "past_ied_to_y",
        "inflection_ing",
        "inflection_ing_restore_e",
        "inflection_ing_undouble",
        "inflection_ed",
        "inflection_ed_restore_e",
        "inflection_ed_undouble",
        "plural_es",
        "plural_s",
        "comparative_er_restore_e",
        "comparative_est",
        "comparative_est_restore_e",
        "comparative_ier_to_y",
        "comparative_iest_to_y",
        "possessive_s",
    }
)


@lru_cache(maxsize=1)
def load_curriculum() -> dict[str, Any]:
    return json.loads(
        (ROOT / "contracts" / "curriculum.json").read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def _load_vocabulary_audit_module():
    path = ROOT / "scripts" / "vocabulary-audit.py"
    spec = importlib.util.spec_from_file_location("m2_vocabulary_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("VOCABULARY_AUDIT_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_vocabulary_scope() -> dict[str, Any]:
    vocabulary = json.loads(
        (ROOT / "contracts" / "vocabulary-whitelist.json").read_text(
            encoding="utf-8"
        )
    )
    all_entries = {entry["word"].lower() for entry in vocabulary["entries"]}
    single_words = {
        word
        for word in all_entries
        if re.fullmatch(r"[a-z]+(?:['-][a-z]+)*", word)
    }
    return {
        "all_entries": all_entries,
        "single_words": single_words,
        "phrases": all_entries - single_words,
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


def get_type_rules(
    passage_type: str,
    validation_profile: str = "m2",
) -> dict[str, int]:
    source = M26_TYPE_RULES if validation_profile == "m26" else TYPE_RULES
    return source[passage_type]


def _average_sentence_words(text: str) -> float:
    word_count = _word_count(text)
    sentence_count = _sentence_count(text)
    return word_count / sentence_count if sentence_count else 0.0


def _long_sentence_count(text: str, *, minimum_words: int = 22) -> int:
    return sum(
        _word_count(sentence) >= minimum_words
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    )


def _complex_structure_count(text: str) -> int:
    patterns = (
        r"\b(?:which|who|whom|whose|that|because|although|though|while|since|unless|when|where|after|before|if)\b",
        r"\b(?:to\s+[a-z]+|[a-z]+ing\b|[a-z]+ed\b)",
    )
    return sum(
        any(re.search(pattern, sentence, re.IGNORECASE) for pattern in patterns)
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    )


def _word_windows(text: str, width: int) -> set[tuple[str, ...]]:
    words = [value.casefold() for value in ANSWER_TOKEN_PATTERN.findall(text)]
    return {
        tuple(words[index : index + width])
        for index in range(max(0, len(words) - width + 1))
    }


def _sentence_count(text: str) -> int:
    return len(
        [
            item
            for item in re.split(r"[.!?。！？]+", text)
            if item.strip()
        ]
    )


def _glossed_terms(text: str) -> list[str]:
    pattern = re.compile(
        r"\b([A-Za-z]+(?:['-][A-Za-z]+)*)\s*[（(]\s*[\u4e00-\u9fff]"
    )
    return sorted({match.group(1).lower() for match in pattern.finditer(text)})


def _remove_glossed_terms(text: str, terms: list[str]) -> str:
    result = text
    for term in terms:
        result = re.sub(
            rf"\b{re.escape(term)}\b\s*[（(][^）)]*[）)]",
            " ",
            result,
            flags=re.IGNORECASE,
        )
    return result


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


def _blank_marker(passage_type: str, index: int) -> str:
    if passage_type == "grammar_fill":
        return chr(0x2460 + index - 1)
    return f"({index})"


def _answer_tokens(value: str) -> list[str]:
    return [match.group(0).casefold() for match in ANSWER_TOKEN_PATTERN.finditer(value)]


def _inflection_candidates(value: str) -> set[str]:
    resolver = _load_vocabulary_audit_module()
    candidates = {
        candidate
        for candidate, rule in resolver.resolution_candidates(value.casefold())
        if rule in ANSWER_INFLECTION_RULES
    }
    for suffix in ("er", "est"):
        if value.casefold().endswith(suffix):
            stem = value.casefold()[: -len(suffix)]
            if (
                len(stem) > 2
                and stem[-1] == stem[-2]
                and stem[-1] not in "aeiou"
            ):
                candidates.add(stem[:-1])
    return candidates


def _same_inflection(left: str, right: str) -> bool:
    return bool(
        _inflection_candidates(left)
        & _inflection_candidates(right)
    )


def _answer_occurrence_count(passage: str, answer: str) -> int:
    passage_tokens = _answer_tokens(passage)
    answer_tokens = _answer_tokens(answer)
    if not answer_tokens:
        return 0
    width = len(answer_tokens)
    return sum(
        all(
            _same_inflection(
                passage_tokens[index + offset],
                answer_tokens[offset],
            )
            for offset in range(width)
        )
        for index in range(len(passage_tokens) - width + 1)
    )


def _placeholder_value_after_marker(suffix: str) -> str:
    match = re.match(r"\s*([^\s,.;:!?()\[\]{}]+)", suffix)
    return match.group(1) if match else ""


def _fill_integrity_failures(
    passage_type: str,
    passage: str,
    questions: list[Any],
) -> tuple[list[GateFailure], list[dict[str, Any]]]:
    if passage_type not in PLACEHOLDER_TYPES:
        return [], []

    answers_by_index = {
        index: str(question.get("answer", "")).strip()
        for index, question in enumerate(questions, start=1)
        if isinstance(question, dict)
    }
    failures: list[GateFailure] = []
    rows: list[dict[str, Any]] = []
    expected_count = TYPE_RULES[passage_type]["questions"]

    for index in range(1, expected_count + 1):
        marker = _blank_marker(passage_type, index)
        answer = (
            answers_by_index.get(index, "")
            if passage_type != "gap_fill"
            else ""
        )
        answer_occurrences = _answer_occurrence_count(passage, answer) if answer else 0
        markers = list(re.finditer(re.escape(marker), passage))
        row = {
            "question_index": index,
            "marker": marker,
            "answer": answer,
            "answer_occurrences": answer_occurrences,
            "slot_form": None,
            "valid": False,
        }
        if not markers:
            failures.append(
                GateFailure(
                    GateCategory.PLACEHOLDER_INTEGRITY,
                    "PLACEHOLDER_MARKER_MISSING: marker is absent from the passage.",
                    index,
                    {"marker": marker},
                )
            )
            rows.append(row)
            continue
        if len(markers) > 1:
            failures.append(
                GateFailure(
                    GateCategory.PLACEHOLDER_INTEGRITY,
                    "PLACEHOLDER_MARKER_DUPLICATE: marker appears more than once.",
                    index,
                    {"marker": marker, "count": len(markers)},
                )
            )
            rows.append(row)
            continue

        suffix = passage[markers[0].end() :]
        leading_word_fragment = re.match(r"\s*[A-Za-z]+_+", suffix)
        trailing_word_fragment = re.match(r"\s*_+[A-Za-z]+", suffix)
        if leading_word_fragment or trailing_word_fragment:
            sample = (leading_word_fragment or trailing_word_fragment).group(0).strip()
            row["slot_form"] = sample
            failures.append(
                GateFailure(
                    GateCategory.PLACEHOLDER_INTEGRITY,
                    "PLACEHOLDER_FRAGMENT: a word fragment remains beside the blank.",
                    index,
                    {
                        "marker": marker,
                        "sample": sample,
                        "expected_placeholder": FILL_PLACEHOLDER,
                    },
                )
            )
            rows.append(row)
            continue

        if re.match(rf"\s*{re.escape(FILL_PLACEHOLDER)}(?![A-Za-z0-9_])", suffix):
            row["slot_form"] = FILL_PLACEHOLDER
            row["valid"] = True
        else:
            value = _placeholder_value_after_marker(suffix)
            row["slot_form"] = value or FILL_PLACEHOLDER
            if (
                value
                and answer
                and _same_inflection(value, _answer_tokens(answer)[0])
            ):
                code = "PLACEHOLDER_ANSWER_WORD_LEAK"
                message = (
                    "PLACEHOLDER_ANSWER_WORD_LEAK: answer word occupies its blank."
                )
            elif suffix.lstrip().startswith("_"):
                code = "PLACEHOLDER_FRAGMENT"
                message = (
                    "PLACEHOLDER_FRAGMENT: malformed underline placeholder."
                )
            else:
                code = "PLACEHOLDER_MISSING"
                message = (
                    "PLACEHOLDER_MISSING: blank has no unified underscore placeholder."
                )
            failures.append(
                GateFailure(
                    GateCategory.PLACEHOLDER_INTEGRITY,
                    message,
                    index,
                    {
                        "marker": marker,
                        "slot_form": row["slot_form"],
                        "expected_placeholder": FILL_PLACEHOLDER,
                    },
                )
            )
        rows.append(row)

        if answer_occurrences:
            failures.append(
                GateFailure(
                    GateCategory.PLACEHOLDER_INTEGRITY,
                    "ANSWER_WORD_APPEARS_IN_PASSAGE: answer form occurs in the passage.",
                    index,
                    {
                        "answer": answer,
                        "occurrences": answer_occurrences,
                    },
                )
            )

    return failures, rows


def validate_fill_placeholder_shape(
    passage_type: str,
    passage: str,
) -> list[GateFailure]:
    failures, _ = _fill_integrity_failures(
        passage_type,
        passage,
        [],
    )
    return failures


def _gap_option_leak_failures(
    passage_type: str,
    passage: str,
    questions: list[Any],
) -> list[GateFailure]:
    if passage_type != "gap_fill":
        return []
    passage_tokens = _answer_tokens(passage)
    failures: list[GateFailure] = []
    reported: set[str] = set()
    for question_index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue
        for option in question.get("options") or []:
            if not isinstance(option, str):
                continue
            normalized = option.strip().casefold()
            if not normalized or normalized in reported:
                continue
            option_tokens = _answer_tokens(option)
            overlap = next(
                (
                    option_tokens[start : start + GAP_OPTION_OVERLAP_WORDS]
                    for start in range(
                        len(option_tokens) - GAP_OPTION_OVERLAP_WORDS + 1
                    )
                    if any(
                        passage_tokens[index : index + GAP_OPTION_OVERLAP_WORDS]
                        == option_tokens[
                            start : start + GAP_OPTION_OVERLAP_WORDS
                        ]
                        for index in range(
                            len(passage_tokens)
                            - GAP_OPTION_OVERLAP_WORDS
                            + 1
                        )
                    )
                ),
                None,
            )
            if overlap:
                reported.add(normalized)
                failures.append(
                    GateFailure(
                        GateCategory.GAP_OPTION_LEAK,
                        "GAP_OPTION_TEXT_LEAK: option text occurs in the passage.",
                        question_index,
                        {
                            "option": option,
                            "overlap_words": overlap,
                            "minimum_overlap": GAP_OPTION_OVERLAP_WORDS,
                        },
                    )
                )
    return failures


def validate_gap_option_leak(
    passage: str,
    questions: list[dict[str, Any]],
) -> list[GateFailure]:
    return _gap_option_leak_failures(
        "gap_fill",
        passage,
        questions,
    )


def validate_rendered_passage(
    record: dict[str, Any],
    rendered_passage: str,
) -> PassageValidationReport:
    rendered_record = dict(record)
    rendered_record["passage"] = rendered_passage
    return validate_generated_passage(rendered_record)


def _m26_rule_failures(
    record: dict[str, Any],
    passage: str,
    questions: list[Any],
) -> tuple[list[GateFailure], dict[str, Any]]:
    passage_type = record["type"]
    failures: list[GateFailure] = []
    if not passage.strip():
        return failures, {
            "average_sentence_words": 0.0,
            "long_sentence_count": 0,
            "complex_structure_count": 0,
            "flesch_reading_ease": None,
        }
    metrics: dict[str, Any] = {
        "average_sentence_words": round(_average_sentence_words(passage), 2),
        "long_sentence_count": _long_sentence_count(passage),
        "complex_structure_count": _complex_structure_count(passage),
    }
    if passage_type in {"cloze", "reading"}:
        metrics["flesch_reading_ease"] = flesch_reading_ease(passage)

    if passage_type == "cloze":
        if metrics["average_sentence_words"] < 15:
            failures.append(
                GateFailure(
                    GateCategory.M26_FORM,
                    "R12_CLOZE_SENTENCE_LENGTH: average sentence length is below 15.",
                    details={"actual": metrics["average_sentence_words"]},
                )
            )
        if not 52 <= metrics["flesch_reading_ease"] <= 70:
            failures.append(
                GateFailure(
                    GateCategory.M26_FORM,
                    "R12_CLOZE_FLESCH: Flesch score is outside 52-70.",
                    details={"actual": metrics["flesch_reading_ease"]},
                )
            )
        if metrics["long_sentence_count"] < 3:
            failures.append(
                GateFailure(
                    GateCategory.M26_FORM,
                    "R12_CLOZE_LONG_SENTENCES: fewer than three sentences have at least 22 words.",
                    details={"actual": metrics["long_sentence_count"]},
                )
            )
        if metrics["complex_structure_count"] < 2:
            failures.append(
                GateFailure(
                    GateCategory.M26_FORM,
                    "R12_CLOZE_COMPLEX_STRUCTURES: fewer than two complex structures.",
                    details={"actual": metrics["complex_structure_count"]},
                )
            )

    if passage_type == "grammar_fill":
        categories = {
            str(question.get("grammar_category"))
            for question in questions
            if isinstance(question, dict) and question.get("grammar_category")
        }
        metrics["grammar_categories"] = sorted(categories)
        if len(categories) < 5:
            failures.append(
                GateFailure(
                    GateCategory.M26_FORM,
                    "R12_GRAMMAR_CATEGORIES: fewer than five grammar categories.",
                    details={"actual": sorted(categories)},
                )
            )

    if passage_type == "reading":
        if metrics["average_sentence_words"] < 16:
            failures.append(
                GateFailure(
                    GateCategory.M26_READING,
                    "R12_READING_SENTENCE_LENGTH: average sentence length is below 16.",
                    details={"actual": metrics["average_sentence_words"]},
                )
            )
        if not 48 <= metrics["flesch_reading_ease"] <= 68:
            failures.append(
                GateFailure(
                    GateCategory.M26_READING,
                    "R12_READING_FLESCH: Flesch score is outside 48-68.",
                    details={"actual": metrics["flesch_reading_ease"]},
                )
            )
        reading_types = [
            str(question.get("reading_type", ""))
            for question in questions
            if isinstance(question, dict)
        ]
        metrics["reading_types"] = reading_types
        invalid_types = sorted(set(reading_types) - M26_READING_TYPES)
        if invalid_types:
            failures.append(
                GateFailure(
                    GateCategory.M26_READING,
                    "R14_READING_TYPE_INVALID: unknown reading subtype.",
                    details={"invalid_types": invalid_types},
                )
            )
        higher_order = sum(
            item in M26_HIGHER_ORDER_READING_TYPES
            for item in reading_types
        )
        if reading_types and higher_order / len(reading_types) < 0.6:
            failures.append(
                GateFailure(
                    GateCategory.M26_READING,
                    "R14_READING_TYPE_RATIO: higher-order reading types are below 60 percent.",
                    details={"higher_order": higher_order, "total": len(reading_types)},
                )
            )
        passage_windows = _word_windows(passage, 5)
        for question_index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                continue
            evidence = question.get("evidence_sentence")
            if not isinstance(evidence, str) or evidence not in passage:
                failures.append(
                    GateFailure(
                        GateCategory.M26_READING,
                        "R14_READING_EVIDENCE_NOT_SUBSTRING: evidence is not a passage substring.",
                        question_index,
                    )
                )
            stem = str(question.get("stem", ""))
            if READING_META_PATTERN.search(stem):
                failures.append(
                    GateFailure(
                        GateCategory.M26_READING,
                        "R14_READING_META_LANGUAGE: question asks for grammar recognition.",
                        question_index,
                    )
                )
            answer = str(question.get("answer", ""))
            if 5 <= len(ANSWER_TOKEN_PATTERN.findall(answer)) and (
                _word_windows(answer, 5) & passage_windows
            ):
                failures.append(
                    GateFailure(
                        GateCategory.M26_READING,
                        "R14_READING_OPTION_COPIED: answer copies at least five consecutive passage words.",
                        question_index,
                        {"answer": answer},
                    )
                )

    if passage_type == "gap_fill":
        cohesion_types = {
            str(question.get("cohesion_type"))
            for question in questions
            if isinstance(question, dict) and question.get("cohesion_type")
        }
        metrics["cohesion_types"] = sorted(cohesion_types)
        if len(cohesion_types) < 3:
            failures.append(
                GateFailure(
                    GateCategory.M26_COHESION,
                    "R12_COHESION_TYPES: fewer than three cohesion types.",
                    details={"actual": sorted(cohesion_types)},
                )
            )

    return failures, metrics


def validate_generated_passage(
    record: dict[str, Any],
    *,
    curriculum: dict[str, Any] | None = None,
    vocabulary: dict[str, Any] | None = None,
    expected_schedule: dict[str, Any] | None = None,
) -> PassageValidationReport:
    curriculum = curriculum or load_curriculum()
    vocabulary = vocabulary or load_vocabulary_scope()
    failures: list[GateFailure] = []

    if not isinstance(record, dict):
        return PassageValidationReport(
            accepted=False,
            failures=[
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Generated passage must be a JSON object.",
                )
            ],
            metrics={},
        )

    required = {
        "type",
        "passage_group_id",
        "topic",
        "book_source",
        "difficulty",
        "passage",
        "questions",
    }
    missing = sorted(required - set(record))
    if missing:
        return PassageValidationReport(
            accepted=False,
            failures=[
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Generated passage is missing required fields.",
                    details={"missing": missing},
                )
            ],
            metrics={},
        )

    passage_type = record.get("type")
    if passage_type not in TYPE_RULES:
        return PassageValidationReport(
            accepted=False,
            failures=[
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Unknown passage type.",
                    details={"type": passage_type},
                )
            ],
            metrics={},
        )

    validation_profile = str(record.get("validation_profile", "m2"))
    if validation_profile not in {"m2", "m26"}:
        return PassageValidationReport(
            accepted=False,
            failures=[
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Unknown validation profile.",
                    details={"validation_profile": validation_profile},
                )
            ],
            metrics={},
        )
    rule = get_type_rules(passage_type, validation_profile)
    passage = record.get("passage")
    questions = record.get("questions")
    if not isinstance(passage, str) or not passage.strip():
        failures.append(
            GateFailure(
                GateCategory.STRUCTURE,
                "Passage must be a non-empty string.",
            )
        )
        passage = ""
    if not isinstance(questions, list):
        failures.append(
            GateFailure(
                GateCategory.STRUCTURE,
                "Questions must be a list.",
            )
        )
        questions = []

    word_count = _word_count(passage)
    if not rule["min_words"] <= word_count <= rule["max_words"]:
        failures.append(
            GateFailure(
                GateCategory.WORD_COUNT,
                "Passage word count is outside the type-specific range.",
                details={
                    "word_count": word_count,
                    "minimum": rule["min_words"],
                    "maximum": rule["max_words"],
                },
            )
        )

    if len(questions) != rule["questions"]:
        failures.append(
            GateFailure(
                GateCategory.QUESTION_COUNT,
                "Question count does not match the type-specific structure.",
                details={
                    "actual": len(questions),
                    "expected": rule["questions"],
                },
            )
        )

    placeholder_failures, fill_integrity = _fill_integrity_failures(
        passage_type,
        passage,
        questions,
    )
    failures.extend(placeholder_failures)
    failures.extend(
        _gap_option_leak_failures(passage_type, passage, questions)
    )
    m26_metrics: dict[str, Any] = {}
    if validation_profile == "m26":
        m26_failures, m26_metrics = _m26_rule_failures(
            record,
            passage,
            questions,
        )
        failures.extend(m26_failures)

    glossed_terms = _glossed_terms(passage)
    audit_text = _remove_glossed_terms(passage, glossed_terms)
    audit = _load_vocabulary_audit_module().count_passage(
        audit_text,
        vocabulary["single_words"],
        vocabulary["phrases"],
    )
    unknown_words = audit["unknown"]
    unknown_ratio = audit["unknown_ratio"]
    vocabulary_resolutions = audit["resolutions"]
    unique_unknown_words = sorted(
        {str(word).casefold() for word in unknown_words}
    )
    if unknown_words and (
        validation_profile != "m26" or len(unique_unknown_words) > 3
    ):
        failures.append(
            GateFailure(
                (
                    GateCategory.M26_VOCABULARY
                    if validation_profile == "m26"
                    else GateCategory.VOCABULARY_SCOPE
                ),
                (
                    "R12_VOCABULARY_LIMIT: more than three words are outside the whitelist."
                    if validation_profile == "m26"
                    else "Passage contains words outside the 3413-entry whitelist."
                ),
                details={"unknown_words": unknown_words},
            )
        )
    if unknown_ratio > 0.03 and validation_profile != "m26":
        failures.append(
            GateFailure(
                GateCategory.UNKNOWN_RATIO,
                "Passage unknown-word ratio exceeds 3 percent.",
                details={
                    "unknown_ratio": round(unknown_ratio, 6),
                    "unknown_words": unknown_words,
                    "single_word_denominator": audit[
                        "single_word_denominator"
                    ],
                },
            )
        )

    grammar_ids = {item["id"] for item in curriculum["grammar_whitelist"]}
    if expected_schedule is not None:
        for field in ("passage_group_id", "topic", "book_source", "difficulty"):
            if record.get(field) != expected_schedule.get(field):
                failures.append(
                    GateFailure(
                        GateCategory.STRUCTURE,
                        "Generated passage metadata differs from the pilot schedule.",
                        details={
                            "field": field,
                            "expected": expected_schedule.get(field),
                            "actual": record.get(field),
                        },
                    )
                )
    for index, question in enumerate(questions):
        question_number = index + 1
        if not isinstance(question, dict):
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Question must be a JSON object.",
                    question_number,
                )
            )
            continue

        stem = question.get("stem")
        options = question.get("options")
        answer = question.get("answer")
        explanation = question.get("explanation")
        knowledge_points = question.get("knowledge_points")
        grammar_tags = question.get("grammar_tags")
        book_source = question.get("book_source", record.get("book_source"))
        difficulty = question.get("difficulty", record.get("difficulty"))

        if not isinstance(stem, str) or not stem.strip():
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Question stem must be non-empty.",
                    question_number,
                )
            )
        if not isinstance(options, list) or len(options) != rule["options"]:
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Question options do not match the required structure.",
                    question_number,
                    {
                        "actual": len(options) if isinstance(options, list) else None,
                        "expected": rule["options"],
                    },
                )
            )
            options = []
        if any(not isinstance(option, str) or not option.strip() for option in options):
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Question options may not contain empty values.",
                    question_number,
                )
            )
        if not isinstance(answer, str) or not answer.strip():
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Question answer must be non-empty.",
                    question_number,
                )
            )
        elif passage_type != "gap_fill" and answer not in options:
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Question answer is not one of its options.",
                    question_number,
                    {"answer": answer},
                )
            )
        elif passage_type == "gap_fill" and answer.upper() not in set("ABCDEFG"):
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Gap-fill answer must be a letter from A to G.",
                    question_number,
                    {"answer": answer},
                )
            )
        if not isinstance(explanation, str) or _sentence_count(explanation) < 3:
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Explanation must contain at least three sentences.",
                    question_number,
                )
            )
        if (
            not isinstance(knowledge_points, list)
            or not knowledge_points
            or len(set(knowledge_points)) != len(knowledge_points)
        ):
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Knowledge points must be a non-empty unique list.",
                    question_number,
                )
            )
        if (
            not isinstance(grammar_tags, list)
            or not 1 <= len(grammar_tags) <= 2
            or len(set(grammar_tags)) != len(grammar_tags)
        ):
            failures.append(
                GateFailure(
                    GateCategory.GRAMMAR_TAG,
                    "Grammar tags must contain one or two unique IDs.",
                    question_number,
                )
            )
            grammar_tags = []
        unknown_tags = [
            tag for tag in grammar_tags if tag not in grammar_ids
        ]
        if unknown_tags:
            failures.append(
                GateFailure(
                    GateCategory.GRAMMAR_TAG,
                    "Question contains grammar IDs outside the 21-ID whitelist.",
                    question_number,
                    {"unknown_tags": unknown_tags},
                )
            )
        if not isinstance(difficulty, int) or not 1 <= difficulty <= 5:
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Difficulty must be an integer from 1 to 5.",
                    question_number,
                )
            )
        if not isinstance(book_source, str) or not _book_tag(book_source):
            failures.append(
                GateFailure(
                    GateCategory.STRUCTURE,
                    "Book source must resolve to exactly one book tag.",
                    question_number,
                    {"book_source": book_source},
                )
            )
            continue
        if expected_schedule is not None:
            assignments = expected_schedule.get("questions") or []
            assignment = (
                assignments[index]
                if index < len(assignments)
                else {}
            )
            if book_source != assignment.get("book_source"):
                failures.append(
                    GateFailure(
                        GateCategory.BOOK_TAG,
                        "Question book source differs from the pilot schedule.",
                        question_number,
                        {
                            "expected": assignment.get("book_source"),
                            "actual": book_source,
                        },
                    )
                )
            if difficulty != assignment.get("difficulty"):
                failures.append(
                    GateFailure(
                        GateCategory.STRUCTURE,
                        "Question difficulty differs from the pilot schedule.",
                        question_number,
                        {
                            "expected": assignment.get("difficulty"),
                            "actual": difficulty,
                        },
                    )
                )
            if grammar_tags != assignment.get("grammar_tags"):
                failures.append(
                    GateFailure(
                        GateCategory.GRAMMAR_TAG,
                        "Question grammar tags differ from the pilot schedule.",
                        question_number,
                        {
                            "expected": assignment.get("grammar_tags"),
                            "actual": grammar_tags,
                        },
                    )
                )
        try:
            validate_question_book_tag(grammar_tags, _book_tag(book_source))
        except QuestionValidationError as error:
            failures.append(
                GateFailure(
                    GateCategory.BOOK_TAG,
                    error.message,
                    question_number,
                    {"code": error.code, **error.details},
                )
            )

    return PassageValidationReport(
        accepted=not failures,
        failures=failures,
        metrics={
            "type": passage_type,
            "validation_profile": validation_profile,
            "word_count": word_count,
            "question_count": len(questions),
            "unknown_words": unknown_words,
            "unknown_ratio": round(unknown_ratio, 6),
            "vocabulary_resolutions": vocabulary_resolutions,
            "vocabulary_resolution_count": len(vocabulary_resolutions),
            "vocabulary_resolution_rate": round(
                len(vocabulary_resolutions)
                / audit["single_word_denominator"],
                6,
            )
            if audit["single_word_denominator"]
            else 0.0,
            "glossed_terms": glossed_terms,
            "single_word_denominator": audit["single_word_denominator"],
            "fill_integrity": fill_integrity,
            **m26_metrics,
        },
    )


def parse_model_response(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int, int]:
    content = payload["choices"][0]["message"].get("content") or ""
    stripped = content.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        stripped = fenced.group(1).strip()
    usage = payload.get("usage") or {}
    return (
        json.loads(stripped),
        int(usage.get("prompt_tokens", 0)),
        int(usage.get("completion_tokens", 0)),
    )


def generate_validated_passage(
    passage_type: str,
    generator: Callable[
        [int, list[dict[str, Any]]],
        tuple[dict[str, Any], int, int, float],
    ],
    *,
    max_retries: int = 3,
    token_cap: int | None = None,
    expected_schedule: dict[str, Any] | None = None,
) -> GenerationResult:
    attempts: list[dict[str, Any]] = []
    previous_failures: list[dict[str, Any]] = []
    prompt_tokens = 0
    completion_tokens = 0
    elapsed_seconds = 0.0

    for attempt_number in range(1, max_retries + 2):
        record, prompt, completion, elapsed = generator(
            attempt_number,
            previous_failures,
        )
        prompt_tokens += int(prompt)
        completion_tokens += int(completion)
        elapsed_seconds += float(elapsed)
        total_tokens = prompt_tokens + completion_tokens
        if token_cap is not None and total_tokens > token_cap:
            metrics = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "elapsed_seconds": elapsed_seconds,
                "failed_retries": max(0, attempt_number - 1),
            }
            raise TokenBudgetExceeded(
                attempts=attempts,
                metrics=metrics,
                token_cap=token_cap,
            )
        report = validate_generated_passage(
            record,
            expected_schedule=expected_schedule,
        )
        attempt = {
            "attempt": attempt_number,
            "accepted": report.accepted,
            "failures": [
                failure.as_dict() for failure in report.failures
            ],
            "metrics": report.metrics,
            "prompt_tokens": int(prompt),
            "completion_tokens": int(completion),
            "total_tokens": int(prompt) + int(completion),
            "elapsed_seconds": float(elapsed),
        }
        attempts.append(attempt)
        if report.accepted and report.metrics.get("type") == passage_type:
            return GenerationResult(
                record=record,
                attempts=attempts,
                metrics={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "elapsed_seconds": elapsed_seconds,
                    "failed_retries": len(attempts) - 1,
                },
            )
        if report.accepted and report.metrics.get("type") != passage_type:
            attempt["accepted"] = False
            attempt["failures"].append(
                {
                    "category": GateCategory.STRUCTURE.value,
                    "message": "Generator returned the wrong passage type.",
                    "question_index": None,
                    "details": {
                        "expected": passage_type,
                        "actual": report.metrics.get("type"),
                    },
                }
            )
        previous_failures = attempt["failures"]

    metrics = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "elapsed_seconds": elapsed_seconds,
        "failed_retries": max(0, len(attempts) - 1),
    }
    raise GenerationExhausted(attempts=attempts, metrics=metrics)


def build_cost_report(
    passages: list[dict[str, Any]],
    *,
    target_sizes: tuple[int, ...] = (300, 2000),
) -> dict[str, Any]:
    question_count = sum(int(item["question_count"]) for item in passages)
    prompt_tokens = sum(int(item["prompt_tokens"]) for item in passages)
    completion_tokens = sum(int(item["completion_tokens"]) for item in passages)
    total_tokens = prompt_tokens + completion_tokens
    elapsed_seconds = sum(float(item["elapsed_seconds"]) for item in passages)
    failed_retries = sum(int(item["failed_retries"]) for item in passages)
    if question_count <= 0:
        raise ValueError("QUESTION_COUNT_MUST_BE_POSITIVE")

    per_question = {
        "prompt_tokens": prompt_tokens / question_count,
        "completion_tokens": completion_tokens / question_count,
        "total_tokens": total_tokens / question_count,
        "elapsed_seconds": elapsed_seconds / question_count,
    }
    extrapolations = {
        str(target): {
            "questions": target,
            "passages": round(
                len(passages) / question_count * target,
                3,
            ),
            "prompt_tokens": round(per_question["prompt_tokens"] * target, 3),
            "completion_tokens": round(
                per_question["completion_tokens"] * target,
                3,
            ),
            "total_tokens": round(per_question["total_tokens"] * target, 3),
            "elapsed_seconds": round(
                per_question["elapsed_seconds"] * target,
                3,
            ),
        }
        for target in target_sizes
    }
    return {
        "passages": passages,
        "totals": {
            "passages": len(passages),
            "questions": question_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "elapsed_seconds": elapsed_seconds,
            "failed_retries": failed_retries,
        },
        "per_question": per_question,
        "extrapolations": extrapolations,
    }
