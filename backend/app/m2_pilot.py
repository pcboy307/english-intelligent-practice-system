"""Prompt and distribution helpers for the M2.0 generated pilot."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


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


def load_pilot_schedule() -> dict[str, Any]:
    return json.loads(
        (ROOT / "config" / "pilot-schedule.json").read_text(encoding="utf-8")
    )


def validate_pilot_schedule(
    schedule: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, Any]:
    questions = [
        question
        for passage in schedule["passages"]
        for question in passage["questions"]
    ]
    difficulty = Counter(f"d{question['difficulty']}" for question in questions)
    book_tag = Counter(_book_tag(question["book_source"]) for question in questions)
    grammar_tag = Counter(
        tag for question in questions for tag in question["grammar_tags"]
    )
    topic_count = len({passage["topic"] for passage in schedule["passages"]})
    metrics = {
        "question_count": len(questions),
        "difficulty": {
            f"d{index}": difficulty.get(f"d{index}", 0)
            for index in range(1, 6)
        },
        "book_tag": {
            key: book_tag.get(key, 0)
            for key in ("选必二", "选必一", "必修", "跨册")
        },
        "grammar_tag_counts": dict(sorted(grammar_tag.items())),
        "max_grammar_tag_count": max(grammar_tag.values(), default=0),
        "d5_count": difficulty.get("d5", 0),
        "topic_count": topic_count,
    }
    failures = []
    if metrics["question_count"] != targets["question_count"]:
        failures.append("QUESTION_COUNT_MISMATCH")
    if metrics["difficulty"] != targets["difficulty"]:
        failures.append("DIFFICULTY_MISMATCH")
    if metrics["book_tag"] != targets["book_tag"]:
        failures.append("BOOK_TAG_MISMATCH")
    if (
        metrics["max_grammar_tag_count"]
        > targets["max_questions_per_grammar_tag"]
    ):
        failures.append("GRAMMAR_TAG_REPEAT_EXCEEDS_3")
    if metrics["d5_count"] > targets["max_d5_questions"]:
        failures.append("D5_LIMIT_EXCEEDED")
    if topic_count < 3:
        failures.append("TOPIC_COUNT_BELOW_3")
    return {
        "accepted": not failures,
        "failures": failures,
        "metrics": metrics,
    }
