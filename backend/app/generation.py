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

from .question_validation import (
    QuestionValidationError,
    validate_question_book_tag,
)


ROOT = Path(__file__).resolve().parents[2]


class GateCategory(StrEnum):
    WORD_COUNT = "word_count"
    STRUCTURE = "structure"
    VOCABULARY_SCOPE = "vocabulary_scope"
    UNKNOWN_RATIO = "unknown_ratio"
    QUESTION_COUNT = "question_count"
    GRAMMAR_TAG = "grammar_tag"
    BOOK_TAG = "book_tag"


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


def _placeholder_checks(record: dict[str, Any]) -> list[str]:
    passage_type = record["type"]
    passage = record["passage"]
    if passage_type == "cloze":
        return [
            f"cloze blank ({index}) is missing"
            for index in range(1, 16)
            if f"({index})" not in passage
        ]
    if passage_type == "grammar_fill":
        return [
            f"grammar blank {chr(0x2460 + index - 1)} is missing"
            for index in range(1, 11)
            if chr(0x2460 + index - 1) not in passage
        ]
    return []


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

    rule = TYPE_RULES[passage_type]
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

    placeholder_errors = _placeholder_checks(
        {"type": passage_type, "passage": passage}
    )
    for message in placeholder_errors:
        failures.append(
            GateFailure(GateCategory.STRUCTURE, message)
        )

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
    if unknown_words:
        failures.append(
            GateFailure(
                GateCategory.VOCABULARY_SCOPE,
                "Passage contains words outside the 3413-entry whitelist.",
                details={"unknown_words": unknown_words},
            )
        )
    if unknown_ratio > 0.03:
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
