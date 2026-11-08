from __future__ import annotations

import json
from pathlib import Path

from backend.app.generation import (
    GateCategory,
    _cloze_structure_categories,
    validate_generated_passage,
)
from backend.app.bank_transfer import (
    M26_BOOK_TARGETS,
    M26_COMPOSITION_TARGETS,
    M26_DIFFICULTY_TARGETS,
)


ROOT = Path(__file__).resolve().parents[2]


PLACEHOLDER = "______"


def _question(
    index: int,
    *,
    answer: str = "answer",
    options: list[str] | None = None,
    reading_type: str | None = None,
    cohesion_type: str | None = None,
    grammar_category: str | None = None,
) -> dict:
    values = options or [answer, "distinct", "separate", "different"]
    question = {
        "stem": f"Question {index}.",
        "options": values,
        "answer": values[0] if answer == "answer" else answer,
        "explanation": "The answer fits. One distractor is wrong. Another distractor is wrong.",
        "knowledge_points": [f"point_{index}"],
        "grammar_tags": ["tense_system"],
        "book_source": "必修1 U1",
        "difficulty": 3,
    }
    if reading_type is not None:
        question["reading_type"] = reading_type
        question["evidence_sentence"] = "Students learn through steady practice."
    if cohesion_type is not None:
        question["cohesion_type"] = cohesion_type
    if grammar_category is not None:
        question["grammar_category"] = grammar_category
    return question


def _base_record(type_: str, passage: str, questions: list[dict]) -> dict:
    return {
        "validation_profile": "m26",
        "type": type_,
        "passage_group_id": f"M26-TEST-{type_.upper()}",
        "topic": "科技",
        "book_source": "必修1 U1",
        "difficulty": 3,
        "passage": passage,
        "questions": questions,
    }


def _failure_codes(report) -> set[str]:
    return {failure.message.split(":", 1)[0] for failure in report.failures}


def test_m26_generation_params_match_the_approved_spreadsheet() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "m26-generation-params-v2.json").read_text(
            encoding="utf-8"
        )
    )
    params = contract["rules"]

    assert params["cloze"]["word_count"] == {"minimum": 280, "maximum": 320}
    assert params["cloze"]["long_sentence_minimum_words"] == 25
    assert params["cloze"]["long_sentence_minimum_count"] == 4
    assert params["cloze"]["structure_categories_minimum_count"] == 3
    assert params["cloze"]["near_synonym_minimum_questions"] == 3
    assert params["cloze"]["flesch_reading_ease"] == {
        "minimum": 45,
        "maximum": 60,
    }
    assert params["grammar_fill"]["word_count"] == {
        "minimum": 220,
        "maximum": 260,
    }
    assert params["grammar_fill"]["required_categories"] == [
        "non_finite_perfect_passive",
        "preposition_plus_which",
        "what_noun_clause",
        "subjunctive",
        "inversion",
    ]
    assert params["reading"]["word_count"] == {
        "minimum": 350,
        "maximum": 420,
    }
    assert params["reading"]["average_sentence_words_minimum"] == 20
    assert params["reading"]["paragraph_function_minimum_questions"] == 1
    assert params["reading"]["flesch_reading_ease"] == {
        "minimum": 45,
        "maximum": 60,
    }
    assert params["gap_fill"]["word_count"] == {
        "minimum": 320,
        "maximum": 380,
    }
    assert contract["generation_standard"] == (
        "docs/question-bank-generation-standard-v2.md"
    )
    assert contract["standard_version"] == 2
    assert contract["run_controls"] == {
        "passages_per_model_response": 1,
        "merge_valid_passages_before_full_import": True,
        "m26_v1_requires_full_quota": True,
        "m26_v1_requires_m26_profile_for_every_passage": True,
        "difficulty_scope": "question",
        "book_distribution_scope": "all_questions",
    }
    assert contract["composition"] == {
        "target_size": 500,
        "passages": {
            "cloze": 12,
            "grammar_fill": 12,
            "reading": 40,
            "gap_fill": 8,
        },
        "difficulty": {
            "1": 60,
            "2": 120,
            "3": 190,
            "4": 95,
            "5": 35,
        },
        "book_distribution": {
            "选必二": 225,
            "选必一": 150,
            "必修": 100,
            "跨册": 25,
        },
        "allowed_topics": [
            "科技",
            "环境",
            "健康心理",
            "文化艺术",
            "旅行地理",
            "志愿公益",
            "职业创业",
            "家庭代际",
            "体育竞技",
            "社会伦理",
            "人物传记",
            "自然科普",
            "历史遗产",
            "媒体信息",
            "城市交通",
        ],
    }
    assert M26_COMPOSITION_TARGETS == contract["composition"]["passages"]
    assert M26_DIFFICULTY_TARGETS == {
        int(key): value
        for key, value in contract["composition"]["difficulty"].items()
    }
    assert M26_BOOK_TARGETS == contract["composition"]["book_distribution"]
    assert sum(M26_BOOK_TARGETS.values()) == 500


def test_m26_cloze_uses_the_new_280_to_320_word_profile() -> None:
    fillers = " ".join(["Students learn through steady practice every day."] * 42)
    slots = " ".join(f"({index}) {PLACEHOLDER}" for index in range(1, 16))
    passage = f"{fillers} {slots}"
    record = _base_record(
        "cloze",
        passage,
        [
            _question(index, answer=f"unusedword{index}")
            for index in range(1, 16)
        ],
    )

    report = validate_generated_passage(record)

    assert GateCategory.WORD_COUNT not in {
        failure.category for failure in report.failures
    }


def test_m26_cloze_rejects_the_previous_short_profile() -> None:
    fillers = " ".join(["Students learn through steady practice every day."] * 39)
    slots = " ".join(f"({index}) {PLACEHOLDER}" for index in range(1, 16))
    record = _base_record(
        "cloze",
        f"{fillers} {slots}",
        [
            _question(index, answer=f"unusedword{index}")
            for index in range(1, 16)
        ],
    )

    report = validate_generated_passage(record)

    assert GateCategory.WORD_COUNT in {
        failure.category for failure in report.failures
    }


def test_m26_cloze_structure_detector_requires_three_distinct_categories() -> None:
    passage = (
        "Having been warned about the risk, the student paused before speaking. "
        "The claim that practice is enough, however, was questioned by the group. "
        "Only then did the class understand how much evidence they needed."
    )

    categories = _cloze_structure_categories(passage)

    assert {"non_finite", "noun_clause", "inversion_or_ellipsis"} <= set(
        categories
    )


def test_m26_rejects_an_extra_numbered_cloze_placeholder() -> None:
    fillers = " ".join(["Students learn through steady practice every day."] * 42)
    slots = " ".join(f"({index}) {PLACEHOLDER}" for index in range(1, 17))
    record = _base_record(
        "cloze",
        f"{fillers} {slots}",
        [
            _question(index, answer=f"unusedword{index}")
            for index in range(1, 16)
        ],
    )

    report = validate_generated_passage(record)

    assert "PLACEHOLDER_COUNT_INVALID" in _failure_codes(report)
    assert "UNEXPECTED_PLACEHOLDER_MARKER" in _failure_codes(report)


def test_m26_rejects_blanks_inside_a_reading_passage() -> None:
    passage = (
        "Students learn through steady practice. ______ ______ "
        "The teacher explains a clear method and checks every example."
    )
    record = _base_record(
        "reading",
        passage,
        [
            _question(1, reading_type="main_idea"),
            _question(2, reading_type="inference"),
            _question(3, reading_type="purpose_or_attitude"),
            _question(4, reading_type="paragraph_function"),
        ],
    )

    report = validate_generated_passage(record)

    assert "UNEXPECTED_PLACEHOLDER" in _failure_codes(report)


def test_m26_rejects_lowercase_answer_at_sentence_start() -> None:
    passage = (
        "The first sentence ends here. ① ______ continues the next sentence. "
        "② ______ and ③ ______ are mid-sentence choices, followed by "
        "④ ______, ⑤ ______, ⑥ ______, ⑦ ______, ⑧ ______, ⑨ ______, "
        "and ⑩ ______."
    )
    record = _base_record(
        "grammar_fill",
        passage,
        [
            _question(1, answer="lowercase answer"),
            *[
                _question(index, answer=f"answer {index}")
                for index in range(2, 11)
            ],
        ],
    )

    report = validate_generated_passage(record)

    assert "ANSWER_SENTENCE_CAPITALIZATION" in _failure_codes(report)


def test_m26_rejects_comma_between_relative_clause_subject_and_verb() -> None:
    passage = (
        "The first sentence ends here. ① ______, reminded everyone of the past. "
        "② ______ and ③ ______ are mid-sentence choices, followed by "
        "④ ______, ⑤ ______, ⑥ ______, ⑦ ______, ⑧ ______, ⑨ ______, "
        "and ⑩ ______."
    )
    questions = [
        _question(
            1,
            answer="the bridge which was built",
            grammar_category="relative_clause",
        ),
        *[
            _question(index, answer=f"answer {index}")
            for index in range(2, 11)
        ],
    ]
    record = _base_record("grammar_fill", passage, questions)

    report = validate_generated_passage(record)

    assert (
        "RELATIVE_CLAUSE_COMMA_SEPARATES_SUBJECT"
        in _failure_codes(report)
    )


def test_m26_rejects_a_reading_option_copied_from_the_passage() -> None:
    copied = "Students learn through steady practice."
    passage = (
        "Students learn through steady practice. "
        "The teacher explains a clear method and checks every example."
    )
    record = _base_record(
        "reading",
        passage,
        [
            _question(
                1,
                options=[copied, "A different answer.", "A third answer.", "A fourth answer."],
                reading_type="main_idea",
            ),
            _question(2, reading_type="inference"),
            _question(3, reading_type="purpose_or_attitude"),
            _question(4, reading_type="vocabulary_in_context"),
        ],
    )

    report = validate_generated_passage(record)

    assert "R14_READING_OPTION_COPIED" in _failure_codes(report)


def test_m26_reading_requires_a_paragraph_function_question() -> None:
    passage = (
        "Students learn through steady practice. "
        "The teacher explains a clear method and checks every example."
    )
    record = _base_record(
        "reading",
        passage,
        [
            _question(1, reading_type="main_idea"),
            _question(2, reading_type="inference"),
            _question(3, reading_type="purpose_or_attitude"),
            _question(4, reading_type="vocabulary_in_context"),
        ],
    )

    report = validate_generated_passage(record)

    assert "R14_PARAGRAPH_FUNCTION_MISSING" in _failure_codes(report)


def test_m26_grammar_fill_requires_all_five_mandatory_categories() -> None:
    passage = " ".join(f"({index}) {PLACEHOLDER}" for index in range(1, 11))
    record = _base_record(
        "grammar_fill",
        passage,
        [
            _question(
                index,
                grammar_category=f"optional_{index}",
            )
            for index in range(1, 11)
        ],
    )

    report = validate_generated_passage(record)

    assert "R12_GRAMMAR_REQUIRED_CATEGORIES" in _failure_codes(report)


def test_m26_gap_fill_requires_three_cohesion_types() -> None:
    passage = " ".join(f"({index}) {PLACEHOLDER}" for index in range(1, 6))
    options = [
        "First useful sentence for the blank.",
        "Second useful sentence for the blank.",
        "Third useful sentence for the blank.",
        "Fourth useful sentence for the blank.",
        "Fifth useful sentence for the blank.",
        "Sixth useful sentence for the blank.",
        "Seventh useful sentence for the blank.",
    ]
    record = _base_record(
        "gap_fill",
        passage,
        [
            _question(
                index,
                answer="A",
                options=options,
                cohesion_type="pronoun_reference",
            )
            for index in range(1, 6)
        ],
    )

    report = validate_generated_passage(record)

    assert "R12_COHESION_TYPES" in _failure_codes(report)
