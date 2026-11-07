#!/usr/bin/env python3
"""Run reproducible book-tag compatibility acceptance cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.question_validation import (
    QuestionValidationError,
    validate_question_book_tag,
)


CASES = [
    {
        "case": "empty-intersection-book-fixed",
        "grammar_tags": ["partial_inversion_basic", "articles"],
        "book_tag": "必修",
        "expected_code": "BOOK_TAG_INCOMPATIBLE",
    },
    {
        "case": "empty-intersection-book-elective-2",
        "grammar_tags": ["partial_inversion_basic", "articles"],
        "book_tag": "选必二",
        "expected_code": "BOOK_TAG_INCOMPATIBLE",
    },
    {
        "case": "compatible-double-tag",
        "grammar_tags": ["tense_system", "noun_clauses"],
        "book_tag": "选必二",
        "expected_ok": True,
    },
]


def main() -> None:
    output = []
    passed = True
    for case in CASES:
        try:
            result = validate_question_book_tag(
                case["grammar_tags"],
                case["book_tag"],
            )
        except QuestionValidationError as error:
            result = error.as_dict()

        expected_code = case.get("expected_code")
        case_passes = (
            result.get("error") == expected_code
            if expected_code
            else result.get("ok") is case.get("expected_ok")
        )
        output.append(
            {
                "case": case["case"],
                "passes": case_passes,
                "result": result,
            }
        )
        passed = passed and case_passes

    evidence = {"passed": passed, "cases": output}
    output_path = ROOT / "qa" / "evidence" / "m0" / "book-tag-compatibility.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
