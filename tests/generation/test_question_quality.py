from __future__ import annotations

from backend.app.question_quality import (
    validate_cloze_options,
    validate_reading_question_type,
)


def test_cloze_rejects_same_lemma_inflections() -> None:
    failures = validate_cloze_options(
        stem="Some experiments fail many times before they (3) ______.",
        options=["change", "changing", "changed", "to change"],
        answer="changed",
    )

    assert {item["code"] for item in failures} >= {"H6_OPTION_SAME_LEMMA"}


def test_cloze_rejects_answer_word_already_present_in_stem() -> None:
    failures = validate_cloze_options(
        stem="We worked on a project to help (7) ______ people.",
        options=["should help", "help", "helped", "helping"],
        answer="help",
    )

    assert {item["code"] for item in failures} >= {
        "H6_OPTION_SAME_LEMMA",
        "H7_OPTION_ECHOES_STEM",
    }


def test_cloze_accepts_distinct_words_from_one_semantic_field() -> None:
    failures = validate_cloze_options(
        stem="Some days are full of joy, while others seem dark and (1) ______.",
        options=["hopeless", "hopeful", "careless", "careful"],
        answer="hopeless",
    )

    assert not [
        failure
        for failure in failures
        if failure["code"] in {"H6_OPTION_SAME_LEMMA", "H7_OPTION_ECHOES_STEM"}
    ]


def test_reading_rejects_meta_language_grammar_identification() -> None:
    failures = validate_reading_question_type(
        "Which sentence from the passage contains a passive voice construction?"
    )

    assert failures == [
        {
            "code": "H8_META_LANGUAGE_QUESTION",
            "message": "Reading question asks for grammar/linguistic structure identification.",
        }
    ]


def test_reading_accepts_meaning_based_inference_question() -> None:
    failures = validate_reading_question_type(
        "What can be inferred about the writer's attitude toward school clubs?"
    )

    assert failures == []
