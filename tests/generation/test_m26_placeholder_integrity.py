from __future__ import annotations

import json

from backend.app.generation import (
    validate_fill_placeholder_shape,
    validate_generated_passage,
    validate_rendered_passage,
)


PLACEHOLDER = "______"


def _question(
    answer: str,
    *,
    options: list[str] | None = None,
    answer_text: str | None = None,
) -> dict:
    values = options or [
        answer,
        "unrelated",
        "separate",
        "different",
    ]
    return {
        "stem": "Choose the best word.",
        "options": values,
        "answer": answer_text or values[0],
        "explanation": "The answer fits the context. One distractor is too broad. Another distractor is unrelated.",
        "knowledge_points": ["context"],
        "grammar_tags": ["tense_system"],
        "book_source": "必修一 U1",
        "difficulty": 3,
    }


def _cloze_record(first_slot: str) -> dict:
    slots = [first_slot] + [
        f"({index}) {PLACEHOLDER}" for index in range(2, 16)
    ]
    answers = [
        "anxious",
        "careful",
        "patient",
        "honest",
        "curious",
        "brave",
        "calm",
        "ready",
        "kind",
        "clear",
        "strong",
        "helpful",
        "friendly",
        "quiet",
        "bright",
    ]
    return {
        "type": "cloze",
        "passage_group_id": "M2.6-TEST-CLOZE-01",
        "topic": "health",
        "book_source": "必修一 U1",
        "difficulty": 3,
        "passage": "Students read a story. " + " ".join(slots) + ".",
        "questions": [_question(answer) for answer in answers],
    }


def _failure_codes(record: dict) -> set[str]:
    report = validate_generated_passage(record)
    assert report.accepted is False
    return {failure.message.split(":", 1)[0] for failure in report.failures}


def test_rejects_answer_word_printed_at_its_own_blank() -> None:
    record = _cloze_record("(1) anxious")

    assert "PLACEHOLDER_ANSWER_WORD_LEAK" in _failure_codes(record)


def test_rejects_blank_marker_followed_by_an_ordinary_word() -> None:
    record = _cloze_record("(1) suddenly")

    assert "PLACEHOLDER_MISSING" in _failure_codes(record)


def test_rejects_placeholder_with_a_remaining_word_fragment() -> None:
    record = _cloze_record("(1) graduat______")

    assert "PLACEHOLDER_FRAGMENT" in _failure_codes(record)


def test_accepts_a_uniform_placeholder_after_every_marker() -> None:
    passage = " ".join(
        f"({index}) {PLACEHOLDER}"
        for index in range(1, 16)
    )

    assert validate_fill_placeholder_shape("cloze", passage) == []


def test_rejects_an_inflected_answer_form_elsewhere_in_the_passage() -> None:
    record = _cloze_record(f"(1) {PLACEHOLDER}")
    record["passage"] += " The student waited anxiously."

    assert "ANSWER_WORD_APPEARS_IN_PASSAGE" in _failure_codes(record)


def test_rejects_gap_option_text_leaking_into_the_passage() -> None:
    leaked = "Regular walking can improve both mood and health."
    options = [
        leaked,
        "A short pause can help a learner recover attention.",
        "Friends often make a difficult task easier to finish.",
        "Small daily choices can build a lasting habit.",
        "Clear goals help students decide what to do next.",
        "Good sleep supports memory and steady concentration.",
        "A quiet place reduces distractions during study.",
    ]
    record = {
        "type": "gap_fill",
        "passage_group_id": "M2.6-TEST-GAP-01",
        "topic": "health",
        "book_source": "必修一 U1",
        "difficulty": 3,
        "passage": (
            "Students discussed healthy routines. "
            "Regular walking can improve both mood and health. "
            "(1) ______ (2) ______ (3) ______ (4) ______ (5) ______"
        ),
        "questions": [
            {
                **_question("A", options=options, answer_text="A"),
                "stem": f"Choose the sentence for blank ({index}).",
            }
            for index in range(1, 6)
        ],
    }

    assert "GAP_OPTION_TEXT_LEAK" in _failure_codes(record)


def test_revalidates_the_text_after_the_json_render_boundary() -> None:
    record = _cloze_record(f"(1) {PLACEHOLDER}")
    rendered = json.loads(json.dumps(record, ensure_ascii=False))
    rendered["passage"] = rendered["passage"].replace(
        f"(1) {PLACEHOLDER}",
        "(1) anxious",
        1,
    )

    report = validate_rendered_passage(record, rendered["passage"])

    assert report.accepted is False
    assert any(
        failure.message.startswith("PLACEHOLDER_ANSWER_WORD_LEAK")
        for failure in report.failures
    )
