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
    book_bucket: str = "选必二",
    difficulty: int = 3,
    grammar_tag: str = "noun_clauses",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=question_id,
        type=type_,
        passage_group_id=passage_id,
        book_bucket=book_bucket,
        book_tag=book_bucket,
        difficulty=difficulty,
        grammar_tags=[grammar_tag],
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


def test_unseen_fallback_beats_seen_exact_quota_candidate() -> None:
    books = ["选必二"] * 13 + ["选必一"] * 9 + ["必修"] * 6 + ["跨册"]
    difficulties = [1] * 12 + [3] * 11 + [4] * 6
    grammar_tags = [
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
    ]
    seen_questions = []
    index = 0
    for type_, passage_id, topic, count in (
        ("cloze", "SEEN-CLOZE", "科技", 15),
        ("grammar_fill", "SEEN-GRAMMAR", "环境", 10),
        ("reading", "SEEN-READING", "健康心理", 4),
    ):
        for order in range(1, count + 1):
            seen_questions.append(
                _question(
                    question_id=f"{passage_id}-Q{order:02d}",
                    type_=type_,
                    passage_id=passage_id,
                    order=order,
                    topic=topic,
                    book_bucket=books[index],
                    difficulty=difficulties[index],
                    grammar_tag=grammar_tags[index % len(grammar_tags)],
                )
            )
            index += 1
    unseen_reading = [
        _question(
            question_id=f"UNSEEN-READING-Q{order:02d}",
            type_="reading",
            passage_id="UNSEEN-READING",
            order=order,
            topic="社会伦理",
            book_bucket="必修",
            difficulty=5,
            grammar_tag=grammar_tags[(index + order) % len(grammar_tags)],
        )
        for order in range(1, 5)
    ]
    questions = seen_questions + unseen_reading
    appearances = {
        question.id: [datetime(2026, 11, 8, tzinfo=timezone.utc)]
        for question in seen_questions
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
    )

    assert "UNSEEN-READING" in {
        question.passage_group_id for question in selected
    }
    assert log["selected_unseen_question_count"] == 4
    assert log["active_bank_question_count"] == 33
    assert log["active_bank_passage_count"] == 4
    assert log["covered_bank_question_count"] == 29
    assert log["uncovered_bank_question_count"] == 4
    assert log["uncovered_safe_candidate_count"] >= 1
