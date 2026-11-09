from __future__ import annotations

from math import floor
from collections import Counter
import random


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
    covered_at: dict[str, list],
    active_passage_ids: set[str],
    book_percentages: dict[str, float],
    tie_break_order: list[str],
    *,
    allow_stage_a_sample_fallback: bool = False,
) -> tuple[list, dict]:
    paper_mode = "reading" if paper_number % 2 == 1 else "gap_fill"
    extra_count = 4 if paper_mode == "reading" else 5
    question_count = 15 + 10 + extra_count
    expected_books = allocate_largest_remainder(
        question_count, book_percentages, tie_break_order
    )
    expected_difficulty = allocate_difficulty(question_count)

    grouped: dict[str, dict[str, list]] = {}
    bank_passages: dict[str, list] = {}
    for question in questions:
        grouped.setdefault(question.type, {}).setdefault(
            question.passage_group_id, []
        ).append(question)
        bank_passages.setdefault(question.passage_group_id, []).append(question)
    active_bank_question_count = len(questions)
    active_bank_passage_count = len(bank_passages)
    covered_bank_question_count = sum(
        1 for question in questions if covered_at.get(question.id)
    )
    covered_bank_passage_count = sum(
        any(covered_at.get(question.id) for question in passage_questions)
        for passage_questions in bank_passages.values()
    )

    failures = []
    safe_candidates = []
    stage_a_candidates = []
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
                knowledge_repeat_excess = max(
                    0,
                    max(knowledge_counts.values(), default=0) - 3,
                )
                if knowledge_repeat_excess:
                    reasons.append("KNOWLEDGE_POINT_REPEAT_EXCEEDS_3")
                if len({question.topic for question in candidate}) < 3:
                    reasons.append("TOPIC_COUNT_BELOW_3")
                unseen_count = sum(
                    1 for question in candidate if not covered_at.get(question.id)
                )
                unseen_passage_count = sum(
                    not any(covered_at.get(question.id) for question in passage_questions)
                    for passage_questions in (
                        cloze_questions,
                        grammar_questions,
                        extra_questions,
                    )
                )
                seen_times = [
                    max(covered_at[question.id])
                    for question in candidate
                    if covered_at.get(question.id)
                ]
                latest_covered_at = max(seen_times, default=None)
                latest_covered_epoch = (
                    latest_covered_at.timestamp()
                    if latest_covered_at is not None
                    else float("-inf")
                )
                deviation = sum(
                    abs(actual_books[key] - expected_books[key])
                    for key in expected_books
                ) + sum(
                    abs(actual_difficulty[key] - expected_difficulty[key])
                    for key in expected_difficulty
                ) + knowledge_repeat_excess
                if (
                    "ACTIVE_PASSAGE_CONFLICT" not in reasons
                    and "GRAMMAR_TAG_REPEAT_EXCEEDS_3" not in reasons
                    and "TOPIC_COUNT_BELOW_3" not in reasons
                ):
                    safe_candidates.append(
                        {
                            "groups": groups,
                            "questions": candidate,
                            "deviation": deviation,
                            "unseen_count": unseen_count,
                            "unseen_passage_count": unseen_passage_count,
                            "latest_covered_at": latest_covered_at,
                            "latest_covered_epoch": latest_covered_epoch,
                            "quota_exact": not any(
                                reason
                                in {
                                    "BOOK_QUOTA_MISMATCH",
                                    "DIFFICULTY_MISMATCH",
                                }
                                for reason in reasons
                            ),
                            "reasons": list(reasons),
                        }
                    )
                if (
                    allow_stage_a_sample_fallback
                    and "ACTIVE_PASSAGE_CONFLICT" not in reasons
                    and "TOPIC_COUNT_BELOW_3" not in reasons
                ):
                    stage_a_candidates.append(
                        {
                            "groups": groups,
                            "questions": candidate,
                            "deviation": deviation,
                            "unseen_count": unseen_count,
                            "unseen_passage_count": unseen_passage_count,
                            "latest_covered_at": latest_covered_at,
                            "latest_covered_epoch": latest_covered_epoch,
                            "quota_exact": not any(
                                reason
                                in {
                                    "BOOK_QUOTA_MISMATCH",
                                    "DIFFICULTY_MISMATCH",
                                }
                                for reason in reasons
                            ),
                            "reasons": list(reasons),
                        }
                    )
                if reasons:
                    failures.append(
                        {
                            "groups": groups,
                            "reasons": reasons,
                        }
                    )

    fallback_used = False
    fallback_reason = None
    coverage_elimination_witness = None
    candidate_pool = safe_candidates
    used_stage_a_fallback = False
    if not candidate_pool and allow_stage_a_sample_fallback:
        candidate_pool = stage_a_candidates
        used_stage_a_fallback = True
    if not candidate_pool:
        raise ValueError("NO_VALID_PAPER_ASSEMBLY")

    best = min(
        candidate_pool,
        key=lambda item: (
            -item["unseen_passage_count"],
            -item["unseen_count"],
            item["deviation"],
            item["latest_covered_epoch"],
            item["groups"],
        ),
    )
    selected = {
        "questions": sorted(
            best["questions"],
            key=lambda question: (
                question.passage_order,
                question.question_order,
            ),
        ),
        "deviation": best["deviation"],
        "groups": best["groups"],
        "unseen_count": best["unseen_count"],
        "unseen_passage_count": best["unseen_passage_count"],
        "latest_covered_at": best["latest_covered_at"],
        "latest_covered_epoch": best["latest_covered_epoch"],
        "quota_exact": best["quota_exact"],
    }
    lower_coverage = min(
        (
            item
            for item in candidate_pool
            if item["unseen_count"] < best["unseen_count"]
            or item["unseen_passage_count"] < best["unseen_passage_count"]
            or item["groups"] != best["groups"]
        ),
        key=lambda item: (
            item["unseen_passage_count"],
            item["unseen_count"],
            item["groups"],
        ),
        default=None,
    )
    coverage_elimination_witness = {
        "selected_unseen_question_count": best["unseen_count"],
        "selected_unseen_passage_count": best["unseen_passage_count"],
        "rejected_unseen_passage_count": (
            lower_coverage["unseen_passage_count"]
            if lower_coverage
            else None
        ),
        "rejected_unseen_question_count": (
            lower_coverage["unseen_count"] if lower_coverage else None
        ),
        "rejected_candidate_groups": (
            lower_coverage["groups"] if lower_coverage else None
        ),
    }
    fallback_used = used_stage_a_fallback or not best["quota_exact"]
    if used_stage_a_fallback:
        fallback_reason = "STAGE_A_SAMPLE_QUOTA_FALLBACK"
    elif not best["quota_exact"]:
        fallback_reason = "COVERAGE_WITH_QUOTA_DEVIATION"

    result_questions = selected["questions"]
    tags = Counter(tag for question in result_questions for tag in question.grammar_tags)
    knowledge_points = Counter(
        point
        for question in result_questions
        for point in question.knowledge_points
    )
    coverage_rows = []
    for question in result_questions:
        seen_times = covered_at.get(question.id, [])
        coverage_rows.append(
            {
                "question_id": question.id,
                "type": question.type,
                "passage_group_id": question.passage_group_id,
                "book_tag": question.book_tag,
                "seen_count": len(seen_times),
                "last_seen_at": (
                    max(seen_times).isoformat() if seen_times else None
                ),
                "unseen": not bool(seen_times),
            }
        )
    selected_unseen = selected["unseen_count"]
    selected_covered = len(result_questions) - selected_unseen
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
        "selection_basis": "coverage",
        "selected_unseen_question_count": selected_unseen,
        "selected_unseen_passage_count": selected["unseen_passage_count"],
        "selected_covered_question_count": selected_covered,
        "selected_new_coverage_ratio": round(
            selected_unseen / len(result_questions),
            4,
        ),
        "selected_latest_covered_at": (
            selected["latest_covered_at"].isoformat()
            if selected["latest_covered_at"] is not None
            else None
        ),
        "question_coverage": coverage_rows,
        "active_bank_question_count": active_bank_question_count,
        "active_bank_passage_count": active_bank_passage_count,
        "covered_bank_passage_count": covered_bank_passage_count,
        "uncovered_bank_passage_count": (
            active_bank_passage_count - covered_bank_passage_count
        ),
        "covered_bank_question_count": covered_bank_question_count,
        "uncovered_bank_question_count": (
            active_bank_question_count - covered_bank_question_count
        ),
        "bank_coverage_ratio": round(
            covered_bank_question_count / active_bank_question_count,
            4,
        ),
        "uncovered_safe_candidate_count": sum(
            item["unseen_passage_count"] > 0 for item in safe_candidates
        ),
        "hard_constraint_triggered": bool(failures),
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "fallback_candidate_count": sum(
            not item["quota_exact"] for item in safe_candidates
        ),
        "stage_a_sample_candidate_count": len(stage_a_candidates),
        "stage_a_sample_fallback": (
            fallback_reason == "STAGE_A_SAMPLE_QUOTA_FALLBACK"
        ),
        "coverage_elimination_witness": coverage_elimination_witness,
        "hard_constraint_rejections": failures,
        "valid_skeleton_count": sum(
            item["quota_exact"] for item in safe_candidates
        ),
    }
    return result_questions, log
