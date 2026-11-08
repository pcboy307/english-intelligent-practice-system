from __future__ import annotations

from backend.app.generation import GateCategory, validate_generated_passage


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


def test_m26_cloze_uses_the_new_250_to_290_word_profile() -> None:
    fillers = " ".join(["Students learn through steady practice every day."] * 36)
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
