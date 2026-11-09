from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.composer import assemble_demo_paper


def _question(
    *,
    question_id: str,
    type_: str,
    passage_id: str,
    order: int,
    topic: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=question_id,
        type=type_,
        passage_group_id=passage_id,
        book_bucket="选必二",
        book_tag="选必二",
        difficulty=3,
        grammar_tags=["noun_clauses"],
        knowledge_points=[f"{passage_id}:{order}"],
        topic=topic,
        passage_order=order,
        question_order=order,
    )


def _stage_a_questions() -> list[SimpleNamespace]:
    groups = (
        ("cloze", "M26-CLOZE", "科技", 15),
        ("grammar_fill", "M26-GRAMMAR", "环境", 10),
        ("reading", "M26-READING", "健康心理", 4),
    )
    return [
        _question(
            question_id=f"{passage_id}-Q{order:02d}",
            type_=type_,
            passage_id=passage_id,
            order=order,
            topic=topic,
        )
        for type_, passage_id, topic, count in groups
        for order in range(1, count + 1)
    ]


def test_stage_a_sample_bank_uses_explicit_quota_fallback() -> None:
    questions = _stage_a_questions()
    arguments = {
        "questions": questions,
        "paper_number": 1,
        "covered_at": {},
        "active_passage_ids": set(),
        "book_percentages": {
            "选必二": 0.45,
            "选必一": 0.30,
            "必修": 0.20,
            "跨册": 0.05,
        },
        "tie_break_order": ["选必二", "选必一", "必修", "跨册"],
    }

    with pytest.raises(ValueError, match="NO_VALID_PAPER_ASSEMBLY"):
        assemble_demo_paper(**arguments)

    selected, log = assemble_demo_paper(
        **arguments,
        allow_stage_a_sample_fallback=True,
    )

    assert len(selected) == 29
    assert log["fallback_reason"] == "STAGE_A_SAMPLE_QUOTA_FALLBACK"
    assert log["stage_a_sample_fallback"] is True


def test_uncovered_questions_are_preferred_before_covered_questions() -> None:
    questions = _stage_a_questions()
    questions.extend(
        _question(
            question_id=f"M26-READING-B-Q{order:02d}",
            type_="reading",
            passage_id="M26-READING-B",
            order=order,
            topic="社会伦理",
        )
        for order in range(1, 5)
    )
    appearances = {
        question.id: [datetime(2026, 11, 8, tzinfo=timezone.utc)]
        for question in questions
        if question.passage_group_id != "M26-READING-B"
    }

    selected, log = assemble_demo_paper(
        questions,
        1,
        appearances,
        set(),
        {
            "选必二": 0.45,
            "选必一": 0.30,
            "必修": 0.20,
            "跨册": 0.05,
        },
        ["选必二", "选必一", "必修", "跨册"],
        allow_stage_a_sample_fallback=True,
    )

    assert {question.passage_group_id for question in selected} == {
        "M26-CLOZE",
        "M26-GRAMMAR",
        "M26-READING-B",
    }
    assert log["selected_unseen_question_count"] == 4
    assert log["selection_basis"] == "coverage"


def test_when_all_questions_were_covered_the_oldest_seen_is_preferred() -> None:
    questions = _stage_a_questions()
    questions.extend(
        _question(
            question_id=f"M26-READING-B-Q{order:02d}",
            type_="reading",
            passage_id="M26-READING-B",
            order=order,
            topic="社会伦理",
        )
        for order in range(1, 5)
    )
    appearances = {}
    for question in questions:
        seen_at = (
            datetime(2026, 11, 1, tzinfo=timezone.utc)
            if question.passage_group_id == "M26-READING"
            else datetime(2026, 11, 8, tzinfo=timezone.utc)
        )
        appearances[question.id] = [seen_at]

    selected, _ = assemble_demo_paper(
        questions,
        1,
        appearances,
        set(),
        {
            "选必二": 0.45,
            "选必一": 0.30,
            "必修": 0.20,
            "跨册": 0.05,
        },
        ["选必二", "选必一", "必修", "跨册"],
        allow_stage_a_sample_fallback=True,
    )

    assert "M26-READING" in {
        question.passage_group_id for question in selected
    }
