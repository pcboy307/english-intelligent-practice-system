from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.composer import assemble_demo_paper


QUESTION_COUNTS = {
    "cloze": 15,
    "grammar_fill": 10,
    "reading": 4,
    "gap_fill": 5,
}


def _question(
    *,
    question_type: str,
    passage_id: str,
    order: int,
    topic: str,
) -> SimpleNamespace:
    passage_order = {
        "cloze": 1,
        "grammar_fill": 2,
        "reading": 3,
        "gap_fill": 3,
    }[question_type]
    return SimpleNamespace(
        id=f"{passage_id}-Q{order:02d}",
        type=question_type,
        passage_group_id=passage_id,
        topic=topic,
        passage_order=passage_order,
        question_order=order,
    )


def _passage(
    question_type: str,
    passage_id: str,
    topic: str,
) -> list[SimpleNamespace]:
    return [
        _question(
            question_type=question_type,
            passage_id=passage_id,
            order=order,
            topic=topic,
        )
        for order in range(1, QUESTION_COUNTS[question_type] + 1)
    ]


def _covered(questions: list[SimpleNamespace]) -> dict[str, list[datetime]]:
    seen_at = datetime(2026, 11, 8, tzinfo=timezone.utc)
    return {question.id: [seen_at] for question in questions}


def _covered_times(
    questions: list[SimpleNamespace],
    count: int,
) -> dict[str, list[datetime]]:
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    return {
        question.id: [start + timedelta(days=index) for index in range(count)]
        for question in questions
    }


def test_less_covered_passages_are_selected_before_more_covered_passages() -> None:
    covered_passages = (
        _passage("cloze", "CLOZE-COVERED", "science")
        + _passage("grammar_fill", "GRAMMAR-COVERED", "environment")
        + _passage("reading", "READING-COVERED", "health")
    )
    uncovered_passages = (
        _passage("cloze", "CLOZE-UNCOVERED", "science")
        + _passage("grammar_fill", "GRAMMAR-UNCOVERED", "environment")
        + _passage("reading", "READING-UNCOVERED", "society")
    )

    selected, log = assemble_demo_paper(
        covered_passages + uncovered_passages,
        1,
        _covered(covered_passages),
    )

    assert {question.passage_group_id for question in selected} == {
        "CLOZE-UNCOVERED",
        "GRAMMAR-UNCOVERED",
        "READING-UNCOVERED",
    }
    assert log["selection_basis"] == (
        "lowest_passage_coverage_then_distinct_topics"
    )
    assert log["selected_total_passage_coverage_count"] == 0
    assert log["selected_unseen_passage_count"] == 3


def test_three_distinct_topics_break_the_uncovered_passage_tie() -> None:
    questions = (
        _passage("cloze", "CLOZE-SAME-TOPIC", "science")
        + _passage("grammar_fill", "GRAMMAR-SAME-TOPIC", "science")
        + _passage("reading", "READING-SAME-TOPIC", "science")
        + _passage("cloze", "CLOZE-DISTINCT-TOPIC", "science")
        + _passage("grammar_fill", "GRAMMAR-DISTINCT-TOPIC", "environment")
        + _passage("reading", "READING-DISTINCT-TOPIC", "health")
    )

    selected, log = assemble_demo_paper(questions, 1, {})

    assert {question.passage_group_id for question in selected} == {
        "CLOZE-DISTINCT-TOPIC",
        "GRAMMAR-DISTINCT-TOPIC",
        "READING-DISTINCT-TOPIC",
    }
    assert log["selected_distinct_topic_count"] == 3
    assert log["selected_total_passage_coverage_count"] == 0
    assert log["topics"] == ["environment", "health", "science"]


def test_lower_total_coverage_is_preferred_across_mixed_passages() -> None:
    cloze_a = _passage("cloze", "CLOZE-A", "science")
    grammar_a = _passage("grammar_fill", "GRAMMAR-A", "science")
    reading_a = _passage("reading", "READING-A", "science")
    cloze_b = _passage("cloze", "CLOZE-B", "science")
    grammar_b = _passage("grammar_fill", "GRAMMAR-B", "science")
    reading_b = _passage("reading", "READING-B", "science")
    questions = (
        cloze_a
        + grammar_a
        + reading_a
        + cloze_b
        + grammar_b
        + reading_b
    )
    covered_at = {
        **_covered_times(cloze_a, 0),
        **_covered_times(grammar_a, 0),
        **_covered_times(reading_a, 10),
        **_covered_times(cloze_b, 3),
        **_covered_times(grammar_b, 3),
        **_covered_times(reading_b, 3),
    }

    _, log = assemble_demo_paper(questions, 1, covered_at)

    assert log["selected_total_passage_coverage_count"] == 3
    assert log["selected_unseen_passage_count"] == 2
    assert log["selected_passage_groups"] == [
        "CLOZE-A",
        "GRAMMAR-A",
        "READING-B",
    ]
    assert log["selection_basis"] == (
        "lowest_passage_coverage_then_distinct_topics"
    )


def test_old_quota_repetition_and_topic_gate_rules_do_not_block_selection() -> None:
    questions = (
        _passage("cloze", "CLOZE-ONLY", "science")
        + _passage("grammar_fill", "GRAMMAR-ONLY", "science")
        + _passage("reading", "READING-ONLY", "science")
    )
    for question in questions:
        question.book_tag = "必修"
        question.difficulty = 5
        question.grammar_tags = ["noun_clauses"]
        question.knowledge_points = ["same-point"]

    selected, log = assemble_demo_paper(questions, 1, {})

    assert len(selected) == 29
    assert log["selected_distinct_topic_count"] == 1
    assert log["paper_mode"] == "reading"


def test_seven_choice_passage_can_win_when_it_is_uncovered() -> None:
    questions = (
        _passage("cloze", "CLOZE-ONLY", "science")
        + _passage("grammar_fill", "GRAMMAR-ONLY", "environment")
        + _passage("reading", "READING-COVERED", "health")
        + _passage("gap_fill", "GAP-UNCOVERED", "society")
    )
    covered = [
        question
        for question in questions
        if question.passage_group_id == "READING-COVERED"
    ]

    selected, log = assemble_demo_paper(questions, 1, _covered(covered))

    assert {question.passage_group_id for question in selected} == {
        "CLOZE-ONLY",
        "GRAMMAR-ONLY",
        "GAP-UNCOVERED",
    }
    assert len(selected) == 30
    assert log["paper_mode"] == "gap_fill"
