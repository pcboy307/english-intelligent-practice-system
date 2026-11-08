from __future__ import annotations

import pytest

from backend.app.cloze_quality import (
    validate_cloze_context,
    validate_cross_audit,
    validate_cross_audit_shape,
)


PASSAGE = (
    "Mia saved every coin for many months. "
    "Her goal was to buy a bicycle, so she was (1) ______ when the shop "
    "finally lowered the price."
)


def question() -> dict:
    return {
        "question_index": 1,
        "stem": (
            "Her goal was to buy a bicycle, so she was (1) ______ when the "
            "shop finally lowered the price."
        ),
        "options": ["delighted", "angry", "bored", "afraid"],
        "answer": "delighted",
        "context_clue": "Mia saved every coin for many months.",
        "clue_argument": (
            "Her long saving plan and the lower price explain why delighted "
            "fits; angry, bored, and afraid do not fit the positive result."
        ),
    }


def passing_audit() -> dict:
    return {
        "coherence": {
            "verdict": "coherent",
            "characters_consistent": True,
            "timeline_present": True,
            "connections_present": True,
            "reason": "One student's experience develops across the passage.",
        },
        "items": [
            {
                "question_index": 1,
                "option_assessments": [
                    {
                        "option_index": 1,
                        "option": "delighted",
                        "grammar_ok": True,
                        "semantic_ok": True,
                        "idiomatic": True,
                        "relation_to_answer": "exact",
                        "reason": "It expresses happiness in this context.",
                    },
                    {
                        "option_index": 2,
                        "option": "angry",
                        "grammar_ok": True,
                        "semantic_ok": False,
                        "idiomatic": True,
                        "relation_to_answer": "confusable",
                        "reason": "A lower price is not a cause of anger here.",
                    },
                    {
                        "option_index": 3,
                        "option": "bored",
                        "grammar_ok": True,
                        "semantic_ok": False,
                        "idiomatic": True,
                        "relation_to_answer": "confusable",
                        "reason": "The sentence describes a positive result.",
                    },
                    {
                        "option_index": 4,
                        "option": "afraid",
                        "grammar_ok": True,
                        "semantic_ok": False,
                        "idiomatic": True,
                        "relation_to_answer": "confusable",
                        "reason": "Nothing in the sentence suggests fear.",
                    },
                ],
                "context_clue_assessment": {
                    "clue_is_verbatim": True,
                    "direct_lexical_relationship": False,
                    "supports_answer": True,
                    "excludes_distractors": True,
                    "reason": "The completed plan explains the positive result.",
                },
                "answer_collocation": {
                    "phrase": "delighted when",
                    "standard": True,
                    "reason": "The pattern is natural in this sentence.",
                },
            }
        ]
    }


def test_context_clue_must_come_from_a_different_passage_sentence() -> None:
    assert validate_cloze_context(PASSAGE, [question()]) == []


def test_context_clue_not_found_in_passage_is_rejected() -> None:
    item = question()
    item["context_clue"] = "Mia wanted to travel around the world."

    failures = validate_cloze_context(PASSAGE, [item])

    assert failures == [
        {
            "question_index": 1,
            "code": "CONTEXT_CLUE_NOT_IN_PASSAGE",
            "context_clue": item["context_clue"],
        }
    ]


def test_context_clue_cannot_reuse_the_blank_sentence() -> None:
    item = question()
    item["context_clue"] = item["stem"]

    failures = validate_cloze_context(PASSAGE, [item])

    assert {failure["code"] for failure in failures} == {
        "CONTEXT_CLUE_IS_BLANK_SENTENCE"
    }


def test_cross_audit_requires_exactly_one_option_to_pass_all_checks() -> None:
    validated = validate_cross_audit(
        [question()],
        passing_audit(),
        expected_collocations={1: "delighted when"},
    )

    assert validated[1]["option_assessments"][0]["option"] == "delighted"


def test_cross_audit_rejects_two_fully_acceptable_options() -> None:
    audit = passing_audit()
    audit["items"][0]["option_assessments"][1]["semantic_ok"] = True

    with pytest.raises(ValueError, match="H10_MULTIPLE_VALID_OPTIONS"):
        validate_cross_audit([question()], audit)


def test_cross_audit_shape_validation_does_not_rewrite_quality_judgments() -> None:
    audit = passing_audit()
    audit["items"][0]["option_assessments"][1]["semantic_ok"] = True

    validated = validate_cross_audit_shape([question()], audit)

    assert validated[1] is audit["items"][0]


def test_cross_audit_rejects_unconfirmed_answer_collocation() -> None:
    audit = passing_audit()
    audit["items"][0]["answer_collocation"]["standard"] = False

    with pytest.raises(ValueError, match="H11_COLLOCATION_NOT_CONFIRMED"):
        validate_cross_audit([question()], audit)


def test_cross_audit_rejects_a_rewritten_collocation_phrase() -> None:
    with pytest.raises(ValueError, match="H11_COLLOCATION_PHRASE_MISMATCH"):
        validate_cross_audit(
            [question()],
            passing_audit(),
            expected_collocations={1: "delighted when the shop"},
        )


def test_cross_audit_rejects_a_non_decisive_context_clue() -> None:
    audit = passing_audit()
    audit["items"][0]["context_clue_assessment"][
        "excludes_distractors"
    ] = False

    with pytest.raises(ValueError, match="CONTEXT_CLUE_NOT_DECISIVE"):
        validate_cross_audit(
            [question()],
            audit,
            expected_collocations={1: "delighted when"},
        )


def test_cross_audit_rejects_direct_synonym_or_root_leak_in_clue() -> None:
    audit = passing_audit()
    audit["items"][0]["context_clue_assessment"][
        "direct_lexical_relationship"
    ] = True

    with pytest.raises(ValueError, match="G13_DIRECT_LEXICAL_RELATIONSHIP"):
        validate_cross_audit(
            [question()],
            audit,
            expected_collocations={1: "delighted when"},
        )


def test_cross_audit_rejects_assembled_sentences_as_non_coherent() -> None:
    audit = passing_audit()
    audit["coherence"]["verdict"] = "assembled"

    with pytest.raises(ValueError, match="G12_PASSAGE_NOT_COHERENT"):
        validate_cross_audit(
            [question()],
            audit,
            expected_collocations={1: "delighted when"},
        )
