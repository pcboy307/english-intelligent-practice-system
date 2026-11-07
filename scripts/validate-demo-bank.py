#!/usr/bin/env python3
"""Validate the deterministic Demo Bank against M1 quality gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.demo_bank import build_demo_questions


NEW_PASSAGES = {
    "DEMO-CLOZE-02",
    "DEMO-GRAMMAR-02",
    "DEMO-READING-01",
    "DEMO-READING-02",
    "DEMO-READING-03",
    "DEMO-READING-04",
    "DEMO-READING-05",
    "DEMO-GAP-02",
}
TYPE_RULES = {
    "cloze": {"questions": 15, "min_words": 170, "max_words": 220},
    "grammar_fill": {"questions": 10, "min_words": 120, "max_words": 180},
    "reading": {"questions": 4, "min_words": 0, "max_words": 250},
    "gap_fill": {"questions": 5, "min_words": 0, "max_words": 220},
}
PROPER_NOUNS = {
    "DEMO-READING-01": ["Guangzhou"],
    "DEMO-READING-04": ["Guangdong"],
}


def _load_vocabulary_audit():
    path = ROOT / "scripts" / "vocabulary-audit.py"
    spec = importlib.util.spec_from_file_location("vocabulary_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("VOCABULARY_AUDIT_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


def validate_demo_bank() -> dict:
    questions = build_demo_questions()
    grouped: dict[str, list] = {}
    for question in questions:
        grouped.setdefault(question.passage_group_id, []).append(question)

    curriculum = json.loads(
        (ROOT / "contracts" / "curriculum.json").read_text(encoding="utf-8")
    )
    allowed_tags = {item["id"] for item in curriculum["grammar_whitelist"]}
    vocabulary = json.loads(
        (ROOT / "contracts" / "vocabulary-whitelist.json").read_text(
            encoding="utf-8"
        )
    )
    all_entries = {entry["word"].lower() for entry in vocabulary["entries"]}
    single_words = {
        word
        for word in all_entries
        if re.fullmatch(r"[a-z]+(?:['-][a-z]+)*", word)
    }
    phrases = all_entries - single_words
    audit = _load_vocabulary_audit()

    passage_results = []
    for group_id, group_questions in sorted(grouped.items()):
        first = group_questions[0]
        rule = TYPE_RULES[first.type]
        word_count = _word_count(first.passage)
        tags = sorted(
            {tag for question in group_questions for tag in question.grammar_tags}
        )
        invalid_tags = sorted(set(tags) - allowed_tags)
        vocabulary_result = audit.count_passage(
            first.passage,
            single_words,
            phrases,
            PROPER_NOUNS.get(group_id),
        )
        advanced_hits = sorted(
            word for word in audit.ADVANCED_SAMPLE if word in single_words
        )
        checks = {
            "question_count": len(group_questions) == rule["questions"],
            "word_count_interval": (
                rule["min_words"] <= word_count <= rule["max_words"]
            ),
            "grammar_tags_within_21_ids": not invalid_tags,
            "unknown_ratio_at_most_3_percent": vocabulary_result["passes"],
        }
        passage_results.append(
            {
                "passage_id": group_id,
                "type": first.type,
                "new_in_this_expansion": group_id in NEW_PASSAGES,
                "word_count": word_count,
                "word_count_interval": [
                    rule["min_words"],
                    rule["max_words"],
                ],
                "question_count": len(group_questions),
                "expected_question_count": rule["questions"],
                "grammar_tags": tags,
                "invalid_grammar_tags": invalid_tags,
                "single_word_denominator": vocabulary_result[
                    "single_word_denominator"
                ],
                "unknown_words": vocabulary_result["unknown"],
                "unknown_ratio": round(vocabulary_result["unknown_ratio"], 6),
                "advanced_sample_hits": advanced_hits,
                "checks": checks,
                "passes": all(checks.values()),
            }
        )

    type_counts = Counter(question.type for question in questions)
    result = {
        "bank_id": questions[0].bank_id,
        "question_count": len(questions),
        "passage_count": len(grouped),
        "question_type_counts": {
            "cloze": type_counts["cloze"],
            "grammar_fill": type_counts["grammar_fill"],
            "reading": type_counts["reading"],
            "gap_fill": type_counts["gap_fill"],
        },
        "new_passage_count": sum(
            1 for item in passage_results if item["new_in_this_expansion"]
        ),
        "generation": {
            "mode": "deterministic_authored_content",
            "llm_calls": 0,
            "llm_tokens": 0,
        },
        "passages": passage_results,
        "passes": (
            len(questions) == 80
            and len(grouped) == 11
            and all(item["passes"] for item in passage_results)
        ),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_demo_bank()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    if not result["passes"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
