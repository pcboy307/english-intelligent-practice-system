from __future__ import annotations

import pytest

from backend.app.generation import (
    GateCategory,
    build_cost_report,
    validate_generated_passage,
)
from backend.app.m2_pilot import load_pilot_schedule


BASE_WORDS = (
    "Students read a short book about healthy food and daily exercise. "
    "The teacher asks them to explain one idea with a clear example. "
)


def reading_payload(*, passage: str | None = None) -> dict:
    text = passage or BASE_WORDS
    return {
        "type": "reading",
        "passage_group_id": "M2-PILOT-READING-01",
        "topic": "运动与健康",
        "book_source": "选必二 U3",
        "difficulty": 3,
        "passage": text,
        "questions": [
            {
                "stem": f"What is the main idea of sentence {index}?",
                "options": ["A clear example.", "A new school.", "A long trip.", "A price list."],
                "answer": "A clear example.",
                "explanation": "The text names a clear example. The other choices are absent. This tests detail reading.",
                "knowledge_points": [f"reading_detail_{index}"],
                "grammar_tags": [tag],
                "book_source": "选必二 U3",
                "difficulty": 3,
            }
            for index, tag in enumerate(
                [
                    "tense_system",
                    "noun_clauses",
                    "passive_voice_tenses",
                    "word_formation",
                ],
                start=1,
            )
        ],
    }


def categories(report) -> set[str]:
    return {failure.category for failure in report.failures}


def test_accepts_a_structurally_complete_in_scope_passage() -> None:
    report = validate_generated_passage(reading_payload())

    assert report.accepted is True
    assert report.failures == []


def test_rejects_reading_passage_over_250_words() -> None:
    passage = " ".join(["student"] * 251)

    report = validate_generated_passage(reading_payload(passage=passage))

    assert report.accepted is False
    assert GateCategory.WORD_COUNT in categories(report)


def test_rejects_question_count_mismatch() -> None:
    payload = reading_payload()
    payload["questions"] = payload["questions"][:3]

    report = validate_generated_passage(payload)

    assert GateCategory.QUESTION_COUNT in categories(report)


def test_rejects_non_whitelist_word_and_unknown_ratio() -> None:
    passage = BASE_WORDS + " The club studies photosynthesis every Friday afternoon."

    report = validate_generated_passage(reading_payload(passage=passage))

    assert GateCategory.VOCABULARY_SCOPE in categories(report)
    assert GateCategory.UNKNOWN_RATIO in categories(report)


def test_accepts_glossed_professional_word_as_the_documented_exception() -> None:
    passage = BASE_WORDS + " They discuss photosynthesis（光合作用）in class."

    report = validate_generated_passage(reading_payload(passage=passage))

    assert GateCategory.VOCABULARY_SCOPE not in categories(report)
    assert report.metrics["glossed_terms"] == ["photosynthesis"]


def test_vocabulary_audit_resolves_inflections_and_derivations_with_an_audit_trail() -> None:
    passage = (
        BASE_WORDS
        + " Students discuss difficulties, curiosity, and western traditions. "
        "They successfully gained valuable experience from the program."
    )

    report = validate_generated_passage(reading_payload(passage=passage))

    assert GateCategory.VOCABULARY_SCOPE not in categories(report)
    assert report.metrics["unknown_words"] == []
    resolutions = {
        item["original"]: item
        for item in report.metrics["vocabulary_resolutions"]
    }
    assert resolutions["difficulties"]["matched_entry"] == "difficult"
    assert resolutions["difficulties"]["rules"] == [
        "plural_ies_to_y",
        "y_to_root",
    ]
    assert resolutions["curiosity"]["matched_entry"] == "curious"
    assert resolutions["curiosity"]["rules"] == ["derivation_ity_to_ous"]
    assert resolutions["western"]["matched_entry"] == "west"
    assert resolutions["western"]["rules"] == ["derivation_ern_to_base"]
    assert resolutions["successfully"]["matched_entry"] == "success"
    assert resolutions["successfully"]["rules"] == [
        "derivation_ly",
        "derivation_ful",
    ]
    assert resolutions["valuable"]["matched_entry"] == "value"
    assert resolutions["valuable"]["rules"] == [
        "derivation_able_restore_e"
    ]
    assert resolutions["program"]["matched_entry"] == "programme"
    assert resolutions["program"]["rules"] == [
        "spelling_variant_programme"
    ]


def test_rejects_grammar_tag_outside_the_21_id_whitelist() -> None:
    payload = reading_payload()
    payload["questions"][0]["grammar_tags"] = ["invented_tag"]

    report = validate_generated_passage(payload)

    assert GateCategory.GRAMMAR_TAG in categories(report)


def test_rejects_book_tag_conflict_using_existing_intersection_validator() -> None:
    payload = reading_payload()
    payload["questions"][0]["grammar_tags"] = [
        "partial_inversion_basic",
        "articles",
    ]
    payload["questions"][0]["book_source"] = "必修二 U1"

    report = validate_generated_passage(payload)

    assert GateCategory.BOOK_TAG in categories(report)
    failure = next(
        item for item in report.failures if item.category == GateCategory.BOOK_TAG
    )
    assert failure.details["code"] == "BOOK_TAG_INCOMPATIBLE"


def test_rejects_empty_options_and_answer_not_present_in_options() -> None:
    payload = reading_payload()
    payload["questions"][0]["options"][1] = ""
    payload["questions"][1]["answer"] = "Not an option."

    report = validate_generated_passage(payload)

    structure = [
        item for item in report.failures if item.category == GateCategory.STRUCTURE
    ]
    assert len(structure) >= 2


def test_cost_report_uses_total_tokens_per_question_and_linear_extrapolation() -> None:
    report = build_cost_report(
        [
            {
                "type": "cloze",
                "question_count": 15,
                "prompt_tokens": 1000,
                "completion_tokens": 2000,
                "elapsed_seconds": 12.5,
                "failed_retries": 1,
            },
            {
                "type": "grammar_fill",
                "question_count": 10,
                "prompt_tokens": 800,
                "completion_tokens": 1500,
                "elapsed_seconds": 9.0,
                "failed_retries": 0,
            },
            {
                "type": "reading",
                "question_count": 4,
                "prompt_tokens": 600,
                "completion_tokens": 900,
                "elapsed_seconds": 6.0,
                "failed_retries": 2,
            },
        ],
        target_sizes=(300, 2000),
    )

    assert report["totals"] == {
        "passages": 3,
        "questions": 29,
        "prompt_tokens": 2400,
        "completion_tokens": 4400,
        "total_tokens": 6800,
        "elapsed_seconds": 27.5,
        "failed_retries": 3,
    }
    assert report["per_question"] == {
        "prompt_tokens": pytest.approx(2400 / 29),
        "completion_tokens": pytest.approx(4400 / 29),
        "total_tokens": pytest.approx(6800 / 29),
        "elapsed_seconds": pytest.approx(27.5 / 29),
    }
    assert report["extrapolations"]["300"]["total_tokens"] == pytest.approx(
        6800 / 29 * 300
    )
    assert report["extrapolations"]["2000"]["total_tokens"] == pytest.approx(
        6800 / 29 * 2000
    )


def test_rejects_record_that_ignores_the_assigned_grammar_tag() -> None:
    schedule = load_pilot_schedule()["passages"][2]
    payload = reading_payload(
        passage=(
            "Food can carry family memories across places and generations. "
            "Students explain the story behind each dish before guests taste it."
        )
    )
    payload.update(
        {
            "passage_group_id": schedule["passage_group_id"],
            "topic": schedule["topic"],
            "book_source": schedule["book_source"],
            "difficulty": schedule["difficulty"],
        }
    )
    for index, (question, assignment) in enumerate(
        zip(payload["questions"], schedule["questions"], strict=True)
    ):
        question.update(
            {
                "book_source": assignment["book_source"],
                "difficulty": assignment["difficulty"],
                "grammar_tags": list(assignment["grammar_tags"]),
            }
        )
        if index == 0:
            question["grammar_tags"] = ["tense_system"]

    report = validate_generated_passage(
        payload,
        expected_schedule=schedule,
    )

    assert GateCategory.GRAMMAR_TAG in categories(report)
