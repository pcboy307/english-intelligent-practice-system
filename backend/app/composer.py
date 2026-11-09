from __future__ import annotations

from collections import Counter, defaultdict


def assemble_demo_paper(
    questions: list,
    paper_number: int,
    covered_at: dict[str, list],
) -> tuple[list, dict]:
    """Assemble one paper using only the two configured selection rules.

    Rule 1: select one cloze, one grammar-fill and one reading or seven-choice
    passage, preferring passages not covered by this student.
    Rule 2: when coverage ties, prefer three distinct topics.
    """
    grouped: dict[str, dict[str, list]] = defaultdict(
        lambda: defaultdict(list)
    )
    bank_passages: dict[str, list] = defaultdict(list)
    for question in questions:
        grouped[question.type][question.passage_group_id].append(question)
        bank_passages[question.passage_group_id].append(question)

    if not grouped["cloze"] or not grouped["grammar_fill"]:
        raise ValueError("NO_VALID_PAPER_ASSEMBLY")
    if not grouped["reading"] and not grouped["gap_fill"]:
        raise ValueError("NO_VALID_PAPER_ASSEMBLY")

    candidates = []
    for cloze_id, cloze_questions in grouped["cloze"].items():
        for grammar_id, grammar_questions in grouped["grammar_fill"].items():
            extra_types = ("reading", "gap_fill")
            for extra_type in extra_types:
                for extra_id, extra_questions in grouped[extra_type].items():
                    passages = (
                        cloze_questions,
                        grammar_questions,
                        extra_questions,
                    )
                    unseen_passage_count = sum(
                        not any(
                            covered_at.get(question.id)
                            for question in passage_questions
                        )
                        for passage_questions in passages
                    )
                    selected_questions = (
                        cloze_questions + grammar_questions + extra_questions
                    )
                    topic_count = len(
                        {
                            question.topic
                            for question in selected_questions
                        }
                    )
                    candidates.append(
                        {
                            "questions": selected_questions,
                            "unseen_passage_count": unseen_passage_count,
                            "topic_count": topic_count,
                            "paper_mode": extra_type,
                            "groups": (cloze_id, grammar_id, extra_id),
                            "extra_type": extra_type,
                        }
                    )

    best_unseen = max(
        candidate["unseen_passage_count"] for candidate in candidates
    )
    coverage_tier = [
        candidate
        for candidate in candidates
        if candidate["unseen_passage_count"] == best_unseen
    ]
    best_topic_count = max(
        candidate["topic_count"] for candidate in coverage_tier
    )
    topic_tier = [
        candidate
        for candidate in coverage_tier
        if candidate["topic_count"] == best_topic_count
    ]
    topic_tier.sort(
        key=lambda candidate: (
            0 if candidate["extra_type"] == "reading" else 1,
            candidate["groups"],
        )
    )
    best = topic_tier[(paper_number - 1) % len(topic_tier)]

    selected_questions = sorted(
        best["questions"],
        key=lambda question: (
            question.passage_order,
            question.question_order,
        ),
    )
    coverage_rows = []
    for question in selected_questions:
        seen_times = covered_at.get(question.id, [])
        coverage_rows.append(
            {
                "question_id": question.id,
                "type": question.type,
                "passage_group_id": question.passage_group_id,
                "seen_count": len(seen_times),
                "last_seen_at": (
                    max(seen_times).isoformat() if seen_times else None
                ),
                "unseen": not bool(seen_times),
            }
        )

    active_bank_question_count = len(questions)
    active_bank_passage_count = len(bank_passages)
    covered_bank_question_count = sum(
        bool(covered_at.get(question.id)) for question in questions
    )
    covered_bank_passage_count = sum(
        any(covered_at.get(question.id) for question in passage_questions)
        for passage_questions in bank_passages.values()
    )
    selected_unseen_question_count = sum(
        not bool(covered_at.get(question.id))
        for question in selected_questions
    )
    selected_topics = sorted(
        {question.topic for question in selected_questions}
    )
    log = {
        "paper_number": paper_number,
        "paper_mode": best["paper_mode"],
        "paper_label": (
            "阅读理解卷"
            if best["paper_mode"] == "reading"
            else "七选五卷"
        ),
        "question_count": len(selected_questions),
        "question_type_counts": dict(
            Counter(question.type for question in selected_questions)
        ),
        "topics": selected_topics,
        "selected_distinct_topic_count": best["topic_count"],
        "selected_passage_groups": list(best["groups"]),
        "selection_basis": "unseen_passages_then_distinct_topics",
        "selection_rules": [
            "one_cloze_one_grammar_fill_one_reading_or_seven_choice",
            "prefer_uncovered_passages_then_three_distinct_topics",
        ],
        "selected_unseen_passage_count": best["unseen_passage_count"],
        "selected_unseen_question_count": selected_unseen_question_count,
        "selected_covered_question_count": (
            len(selected_questions) - selected_unseen_question_count
        ),
        "selected_new_coverage_ratio": round(
            selected_unseen_question_count / len(selected_questions),
            4,
        ),
        "question_coverage": coverage_rows,
        "active_bank_question_count": active_bank_question_count,
        "active_bank_passage_count": active_bank_passage_count,
        "covered_bank_question_count": covered_bank_question_count,
        "uncovered_bank_question_count": (
            active_bank_question_count - covered_bank_question_count
        ),
        "covered_bank_passage_count": covered_bank_passage_count,
        "uncovered_bank_passage_count": (
            active_bank_passage_count - covered_bank_passage_count
        ),
        "bank_coverage_ratio": round(
            covered_bank_question_count / active_bank_question_count,
            4,
        ),
    }
    return selected_questions, log
