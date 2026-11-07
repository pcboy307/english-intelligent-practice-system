"""Question-level validation for grammar and book-tag compatibility."""

from __future__ import annotations

import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = json.loads(
    (ROOT / "contracts" / "curriculum.json").read_text(encoding="utf-8")
)
GRAMMAR_BOOK_TAGS = {
    item["id"]: set(item["allowed_book_tags"])
    for item in CURRICULUM["grammar_whitelist"]
}
ALLOWED_BOOK_TAG_ORDER = CURRICULUM["book_tag_policy"]["allowed_values"]
ALLOWED_BOOK_TAGS = set(ALLOWED_BOOK_TAG_ORDER)
BOOK_TAG_PRIORITY = {
    book_tag: index for index, book_tag in enumerate(ALLOWED_BOOK_TAG_ORDER)
}


def _ordered_book_tags(values) -> list[str]:
    return sorted(values, key=BOOK_TAG_PRIORITY.__getitem__)


class QuestionValidationError(ValueError):
    def __init__(self, code: str, message: str, details: dict):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_dict(self) -> dict:
        return {
            "ok": False,
            "error": self.code,
            "message": self.message,
            **self.details,
        }


def validate_question_book_tag(grammar_tags: list[str], book_tag: str) -> dict:
    if not grammar_tags:
        raise QuestionValidationError(
            "GRAMMAR_TAG_REQUIRED",
            "Question must contain at least one grammar tag.",
            {"book_tag": book_tag, "grammar_tags": []},
        )
    if len(grammar_tags) > CURRICULUM["grammar_tag_policy"][
        "max_grammar_tags_per_question"
    ]:
        raise QuestionValidationError(
            "GRAMMAR_TAG_LIMIT_EXCEEDED",
            "Question contains too many grammar tags.",
            {"book_tag": book_tag, "grammar_tags": grammar_tags},
        )

    unknown_tags = [tag for tag in grammar_tags if tag not in GRAMMAR_BOOK_TAGS]
    if unknown_tags:
        raise QuestionValidationError(
            "GRAMMAR_TAG_UNKNOWN",
            "Question contains grammar tags outside the whitelist.",
            {"book_tag": book_tag, "grammar_tags": grammar_tags, "unknown": unknown_tags},
        )

    tag_allowed_book_tags = {
        tag: _ordered_book_tags(GRAMMAR_BOOK_TAGS[tag]) for tag in grammar_tags
    }
    intersection = set.intersection(
        *(GRAMMAR_BOOK_TAGS[tag] for tag in grammar_tags)
    )
    conflict_pairs = [
        {
            "first": first,
            "first_allowed_book_tags": _ordered_book_tags(GRAMMAR_BOOK_TAGS[first]),
            "second": second,
            "second_allowed_book_tags": _ordered_book_tags(GRAMMAR_BOOK_TAGS[second]),
            "intersection": _ordered_book_tags(
                GRAMMAR_BOOK_TAGS[first] & GRAMMAR_BOOK_TAGS[second]
            ),
        }
        for first, second in itertools.combinations(grammar_tags, 2)
        if not GRAMMAR_BOOK_TAGS[first] & GRAMMAR_BOOK_TAGS[second]
    ]

    if book_tag not in ALLOWED_BOOK_TAGS or book_tag not in intersection:
        reason = (
            "GRAMMAR_TAGS_HAVE_NO_COMMON_BOOK_TAG"
            if not intersection
            else "BOOK_TAG_NOT_IN_INTERSECTION"
        )
        raise QuestionValidationError(
            "BOOK_TAG_INCOMPATIBLE",
            "Rejected: book_tag is incompatible with the grammar tag set.",
            {
                "reason": reason,
                "book_tag": book_tag,
                "grammar_tags": grammar_tags,
                "grammar_tag_allowed_book_tags": tag_allowed_book_tags,
                "allowed_book_tag_intersection": _ordered_book_tags(intersection),
                "conflict_pairs": conflict_pairs,
            },
        )

    return {
        "ok": True,
        "book_tag": book_tag,
        "grammar_tags": grammar_tags,
        "grammar_tag_allowed_book_tags": tag_allowed_book_tags,
        "allowed_book_tag_intersection": _ordered_book_tags(intersection),
    }
