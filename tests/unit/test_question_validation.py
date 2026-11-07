from __future__ import annotations

import pytest

from backend.app.question_validation import (
    QuestionValidationError,
    validate_question_book_tag,
)


@pytest.mark.parametrize("book_tag", ["必修", "选必二"])
def test_empty_intersection_is_rejected_with_conflicting_ids(book_tag: str) -> None:
    with pytest.raises(QuestionValidationError) as raised:
        validate_question_book_tag(
            ["partial_inversion_basic", "articles"],
            book_tag,
        )

    error = raised.value
    assert error.code == "BOOK_TAG_INCOMPATIBLE"
    assert error.details["allowed_book_tag_intersection"] == []
    assert error.details["conflict_pairs"] == [
        {
            "first": "partial_inversion_basic",
            "first_allowed_book_tags": ["选必二"],
            "second": "articles",
            "second_allowed_book_tags": ["必修"],
            "intersection": [],
        }
    ]


def test_compatible_double_tag_is_accepted() -> None:
    result = validate_question_book_tag(
        ["tense_system", "noun_clauses"],
        "选必二",
    )

    assert result["ok"] is True
    assert result["allowed_book_tag_intersection"] == [
        "必修",
        "选必一",
        "选必二",
        "跨册",
    ]


def test_single_tag_uses_its_own_allowed_set() -> None:
    result = validate_question_book_tag(["articles"], "必修")
    assert result["ok"] is True

    with pytest.raises(QuestionValidationError) as raised:
        validate_question_book_tag(["articles"], "选必二")
    assert raised.value.code == "BOOK_TAG_INCOMPATIBLE"
