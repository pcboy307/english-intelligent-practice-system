from __future__ import annotations

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
    weights = {
        question.id: {
            "weight": 1.0,
            "base_weight": 1.0,
            "recent_three_penalty": 0,
            "i_err": 0,
        }
        for question in questions
    }
    arguments = {
        "questions": questions,
        "paper_number": 1,
        "weight_details": weights,
        "recent_three_ids": set(),
        "active_passage_ids": set(),
        "active_error_ids": set(),
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
