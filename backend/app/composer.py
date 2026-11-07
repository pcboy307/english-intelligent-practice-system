from __future__ import annotations

from math import floor
from collections import Counter


def allocate_largest_remainder(
    total: int,
    percentages: dict[str, float],
    tie_break_order: list[str],
) -> dict[str, int]:
    """Allocate integer slots from percentages using largest remainder.

    Self-tests:
    29 -> 13/9/6/1 with percentages 45/30/20/5
    30 -> 14/9/6/1
    42 -> 19/13/8/2
    """
    if total < 0:
        raise ValueError("TOTAL_MUST_BE_NON_NEGATIVE")
    if abs(sum(percentages.values()) - 1.0) > 1e-9:
        raise ValueError("PERCENTAGES_MUST_SUM_TO_ONE")

    raw = {key: total * value for key, value in percentages.items()}
    allocated = {key: floor(value) for key, value in raw.items()}
    remainder = total - sum(allocated.values())
    priority = {key: index for index, key in enumerate(tie_break_order)}
    ranked = sorted(
        percentages,
        key=lambda key: (-(raw[key] - allocated[key]), priority.get(key, 999)),
    )
    for key in ranked[:remainder]:
        allocated[key] += 1
    if sum(allocated.values()) != total:
        raise AssertionError("LARGEST_REMAINDER_ALLOCATION_FAILED")
    return allocated


def allocate_difficulty(total: int) -> dict[str, int]:
    return allocate_largest_remainder(
        total,
        {"easy": 0.40, "medium": 0.40, "hard": 0.20},
        ["easy", "medium", "hard"],
    )


def _difficulty_band(value: int) -> str:
    if value <= 2:
        return "easy"
    if value == 3:
        return "medium"
    return "hard"


def assemble_demo_paper(
    questions: list,
    paper_number: int,
    weight_details: dict[str, dict],
    recent_three_ids: set[str],
    active_passage_ids: set[str],
    active_error_ids: set[str],
    book_percentages: dict[str, float],
    tie_break_order: list[str],
) -> tuple[list, dict]:
    paper_mode = "reading" if paper_number % 2 == 1 else "gap_fill"
    extra_count = 4 if paper_mode == "reading" else 5
    question_count = 15 + 10 + extra_count
    expected_books = allocate_largest_remainder(
        question_count, book_percentages, tie_break_order
    )
    expected_difficulty = allocate_difficulty(question_count)

    grouped: dict[str, dict[str, list]] = {}
    for question in questions:
        grouped.setdefault(question.type, {}).setdefault(
            question.passage_group_id, []
        ).append(question)

    failures = []
    valid = []
    for cloze_group, cloze_questions in grouped["cloze"].items():
        for grammar_group, grammar_questions in grouped["grammar_fill"].items():
            for extra_group, extra_questions in grouped[paper_mode].items():
                candidate = cloze_questions + grammar_questions + extra_questions
                groups = [cloze_group, grammar_group, extra_group]
                reasons = []
                if active_passage_ids.intersection(groups):
                    reasons.append("ACTIVE_PASSAGE_CONFLICT")
                actual_books = Counter(question.book_bucket for question in candidate)
                if dict(actual_books) != expected_books:
                    reasons.append("BOOK_QUOTA_MISMATCH")
                actual_difficulty = Counter(
                    _difficulty_band(question.difficulty) for question in candidate
                )
                if dict(actual_difficulty) != expected_difficulty:
                    reasons.append("DIFFICULTY_MISMATCH")
                tag_counts = Counter(
                    tag for question in candidate for tag in question.grammar_tags
                )
                if max(tag_counts.values(), default=0) > 3:
                    reasons.append("GRAMMAR_TAG_REPEAT_EXCEEDS_3")
                knowledge_counts = Counter(
                    point
                    for question in candidate
                    for point in question.knowledge_points
                )
                if max(knowledge_counts.values(), default=0) > 3:
                    reasons.append("KNOWLEDGE_POINT_REPEAT_EXCEEDS_3")
                if len({question.topic for question in candidate}) < 3:
                    reasons.append("TOPIC_COUNT_BELOW_3")
                error_ratio = sum(
                    1 for question in candidate if question.id in active_error_ids
                ) / len(candidate)
                if error_ratio > 0.60:
                    reasons.append("ERROR_POOL_EXCEEDS_60_PERCENT")
                if reasons:
                    failures.append(
                        {
                            "groups": groups,
                            "reasons": reasons,
                        }
                    )
                    continue
                score = sum(
                    weight_details[question.id]["weight"] for question in candidate
                ) / len(candidate)
                valid.append(
                    {
                        "groups": groups,
                        "questions": sorted(
                            candidate,
                            key=lambda question: (
                                question.passage_order,
                                question.question_order,
                            ),
                        ),
                        "score": round(score, 6),
                    }
                )

    if not valid:
        raise ValueError("NO_VALID_PAPER_ASSEMBLY")

    selected = sorted(
        valid,
        key=lambda item: (-item["score"], item["groups"]),
    )[0]
    result_questions = selected["questions"]
    tags = Counter(tag for question in result_questions for tag in question.grammar_tags)
    knowledge_points = Counter(
        point
        for question in result_questions
        for point in question.knowledge_points
    )
    weight_rows = []
    for question in result_questions:
        detail = weight_details[question.id]
        weight_rows.append(
            {
                "question_id": question.id,
                "type": question.type,
                "passage_group_id": question.passage_group_id,
                "book_tag": question.book_tag,
                "weight": detail["weight"],
                "base_weight": detail["base_weight"],
                "recent_three_penalty": detail["recent_three_penalty"],
                "appeared_in_recent_three": question.id in recent_three_ids,
            }
        )
    log = {
        "paper_number": paper_number,
        "paper_mode": paper_mode,
        "paper_label": "29 题阅读场" if paper_mode == "reading" else "30 题七选五场",
        "question_count": len(result_questions),
        "question_type_counts": dict(Counter(q.type for q in result_questions)),
        "book_quota_expected": expected_books,
        "book_quota_actual": dict(Counter(q.book_bucket for q in result_questions)),
        "difficulty_quota_expected": expected_difficulty,
        "difficulty_actual": dict(
            Counter(_difficulty_band(q.difficulty) for q in result_questions)
        ),
        "grammar_tag_counts": dict(sorted(tags.items())),
        "knowledge_point_counts": dict(sorted(knowledge_points.items())),
        "topics": sorted({question.topic for question in result_questions}),
        "selected_passage_groups": [q.passage_group_id for q in result_questions],
        "recent_three_question_weights": [
            row for row in weight_rows if row["appeared_in_recent_three"]
        ],
        "question_weights": weight_rows,
        "error_pool_ratio": round(
            sum(
                1
                for question in result_questions
                if question.id in active_error_ids
            )
            / len(result_questions),
            4,
        ),
        "hard_constraint_triggered": bool(failures),
        "hard_constraint_rejections": failures,
        "valid_skeleton_count": len(valid),
    }
    return result_questions, log
