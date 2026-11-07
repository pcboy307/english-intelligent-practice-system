#!/usr/bin/env python3
"""Check whether grammar coverage and full-bank book quotas are jointly feasible."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "qa" / "evidence" / "m0" / "grammar-book-feasibility.json"
GROUPS = ["必修", "选必一", "选必二", "跨册"]
DISTRIBUTION_KEYS = {
    "必修": "必修",
    "选必一": "选必一",
    "选必二": "选必二",
    "跨册": "cross_book",
}


def main() -> None:
    curriculum = json.loads(
        (ROOT / "contracts" / "curriculum.json").read_text(encoding="utf-8")
    )
    grammar = curriculum["grammar_whitelist"]
    grammar_fill_questions = curriculum["question_type_distribution"][
        "standard_2000"
    ]["grammar_fill"]["questions"]
    minimum_per_id = curriculum["quality_gates"][
        "grammar_fill_min_questions_per_grammar_id"
    ]
    max_tags_per_question = curriculum["grammar_tag_policy"][
        "max_grammar_tags_per_question"
    ]
    percentages = curriculum["book_distribution"]["question_point_distribution"]

    targets = {
        group: round(
            grammar_fill_questions * percentages[DISTRIBUTION_KEYS[group]]
        )
        for group in GROUPS
    }
    rows = []
    remaining_slots = {
        group: targets[group] * max_tags_per_question for group in GROUPS
    }
    for group in GROUPS:
        allowed_ids = [
            item["id"] for item in grammar if group in item["allowed_book_tags"]
        ]
        exclusive_ids = [
            item["id"]
            for item in grammar
            if item["allowed_book_tags"] == [group]
        ]
        exclusive_occurrences = len(exclusive_ids) * minimum_per_id
        minimum_questions = (
            0
            if not exclusive_ids
            else max(
                minimum_per_id,
                math.ceil(exclusive_occurrences / max_tags_per_question),
            )
        )
        target = targets[group]
        capacity = target * max_tags_per_question
        rows.append(
            {
                "book_tag": group,
                "usable_id_count": len(allowed_ids),
                "usable_ids": allowed_ids,
                "exclusive_id_count": len(exclusive_ids),
                "exclusive_ids": exclusive_ids,
                "exclusive_coverage_occurrences": exclusive_occurrences,
                "minimum_questions_for_exclusive_ids": minimum_questions,
                "target_questions": target,
                "tag_capacity_at_target": capacity,
                "passes": target >= minimum_questions,
            }
        )

    allocation = {}
    for item in sorted(
        grammar,
        key=lambda value: (len(value["allowed_book_tags"]), value["id"]),
    ):
        need = minimum_per_id
        allocation[item["id"]] = {}
        for group in sorted(
            item["allowed_book_tags"],
            key=lambda value: remaining_slots[value],
            reverse=True,
        ):
            used = min(need, remaining_slots[group])
            if used:
                allocation[item["id"]][group] = used
                remaining_slots[group] -= used
                need -= used
            if need == 0:
                break
        if need:
            raise AssertionError(f"NO_COVERAGE_ALLOCATION:{item['id']}")

    total_required_occurrences = len(grammar) * minimum_per_id
    total_tag_capacity = grammar_fill_questions * max_tags_per_question
    remaining_capacity = sum(
        row["tag_capacity_at_target"]
        - row["exclusive_coverage_occurrences"]
        for row in rows
    )
    remaining_required = total_required_occurrences - sum(
        row["exclusive_coverage_occurrences"] for row in rows
    )
    passes = (
        sum(targets.values()) == grammar_fill_questions
        and total_tag_capacity >= total_required_occurrences
        and remaining_capacity >= remaining_required
        and all(row["passes"] for row in rows)
    )
    result = {
        "grammar_fill_questions": grammar_fill_questions,
        "grammar_id_count": len(grammar),
        "minimum_questions_per_id": minimum_per_id,
        "required_coverage_occurrences": total_required_occurrences,
        "max_grammar_tags_per_question": max_tags_per_question,
        "total_tag_capacity": total_tag_capacity,
        "remaining_capacity_after_exclusive_ids": remaining_capacity,
        "remaining_coverage_occurrences": remaining_required,
        "distribution_targets": targets,
        "rows": rows,
        "coverage_allocation": allocation,
        "remaining_tag_slots_after_allocation": remaining_slots,
        "conclusion": "可达" if passes else "不可达",
        "passes": passes,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not passes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
