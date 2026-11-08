"""Cloze-specific context evidence and cross-model option auditing."""

from __future__ import annotations

import json
import re
from typing import Any


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentences(passage: str) -> list[str]:
    return [
        _normalized(item)
        for item in re.split(r"(?<=[.!?])\s+", passage)
        if item.strip()
    ]


def validate_cloze_context(
    passage: str,
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    sentences = _sentences(passage)
    for question in questions:
        question_index = question.get("question_index")
        clue = question.get("context_clue")
        argument = question.get("clue_argument")
        blank_token = f"({question_index})"
        blank_sentences = [
            sentence for sentence in sentences if blank_token in sentence
        ]
        if not blank_sentences:
            failures.append(
                {
                    "question_index": question_index,
                    "code": "BLANK_SENTENCE_NOT_FOUND",
                    "blank_token": blank_token,
                }
            )
            continue
        if not isinstance(clue, str) or not clue.strip():
            failures.append(
                {
                    "question_index": question_index,
                    "code": "CONTEXT_CLUE_MISSING",
                }
            )
            continue
        if clue not in passage:
            failures.append(
                {
                    "question_index": question_index,
                    "code": "CONTEXT_CLUE_NOT_IN_PASSAGE",
                    "context_clue": clue,
                }
            )
            continue
        if _normalized(clue) not in sentences:
            failures.append(
                {
                    "question_index": question_index,
                    "code": "CONTEXT_CLUE_NOT_COMPLETE_SENTENCE",
                    "context_clue": clue,
                }
            )
            continue
        if any(_normalized(clue) == sentence for sentence in blank_sentences):
            failures.append(
                {
                    "question_index": question_index,
                    "code": "CONTEXT_CLUE_IS_BLANK_SENTENCE",
                    "context_clue": clue,
                }
            )
            continue
        if not isinstance(argument, str) or not argument.strip():
            failures.append(
                {
                    "question_index": question_index,
                    "code": "CLUE_ARGUMENT_MISSING",
                }
            )
            continue
        missing_distractors = [
            option
            for option in question.get("options", [])
            if option != question.get("answer")
            and option.casefold() not in argument.casefold()
        ]
        if missing_distractors:
            failures.append(
                {
                    "question_index": question_index,
                    "code": "CLUE_ARGUMENT_OMITS_DISTRACTORS",
                    "missing": missing_distractors,
                }
            )
    return failures


def validate_cross_audit_shape(
    questions: list[dict[str, Any]],
    audit: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    items = audit.get("items")
    if not isinstance(items, list):
        raise ValueError("AUDIT_ITEMS_ARRAY_MISSING")
    expected = {question["question_index"] for question in questions}
    actual = [
        item.get("question_index")
        for item in items
        if isinstance(item, dict)
    ]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError(
            f"AUDIT_INDEX_SET_MISMATCH expected={sorted(expected)} "
            f"actual={actual}"
        )

    questions_by_index = {
        question["question_index"]: question for question in questions
    }
    by_index = {}
    for item in items:
        question_index = item["question_index"]
        question = questions_by_index[question_index]
        assessments = item.get("option_assessments")
        if not isinstance(assessments, list) or len(assessments) != 4:
            raise ValueError(
                f"AUDIT_OPTION_ASSESSMENTS_INVALID question_index={question_index}"
            )
        for option_index, (option, assessment) in enumerate(
            zip(question["options"], assessments, strict=True),
            start=1,
        ):
            if (
                not isinstance(assessment, dict)
                or assessment.get("option_index") != option_index
                or assessment.get("option") != option
                or not all(
                    isinstance(assessment.get(field), bool)
                    for field in ("grammar_ok", "semantic_ok", "idiomatic")
                )
                or not isinstance(assessment.get("reason"), str)
                or not assessment["reason"].strip()
                or assessment.get("relation_to_answer")
                not in {
                    "exact",
                    "near_synonym",
                    "confusable",
                    "antonym",
                    "unrelated",
                }
            ):
                raise ValueError(
                    "AUDIT_OPTION_ASSESSMENT_INVALID "
                    f"question_index={question_index} option_index={option_index}"
                )

        clue_assessment = item.get("context_clue_assessment")
        if (
            not isinstance(clue_assessment, dict)
            or not all(
                isinstance(clue_assessment.get(field), bool)
                for field in (
                    "clue_is_verbatim",
                    "direct_lexical_relationship",
                    "supports_answer",
                    "excludes_distractors",
                )
            )
            or not isinstance(clue_assessment.get("reason"), str)
            or not clue_assessment["reason"].strip()
        ):
            raise ValueError(
                "CONTEXT_CLUE_ASSESSMENT_INVALID "
                f"question_index={question_index}"
            )

        collocation = item.get("answer_collocation")
        if (
            not isinstance(collocation, dict)
            or not isinstance(collocation.get("phrase"), str)
            or not collocation["phrase"].strip()
            or not isinstance(collocation.get("standard"), bool)
            or not isinstance(collocation.get("reason"), str)
            or not collocation["reason"].strip()
        ):
            raise ValueError(
                "H11_COLLOCATION_RESULT_INVALID "
                f"question_index={question_index}"
            )
        by_index[question_index] = item
    return by_index


def validate_cross_audit(
    questions: list[dict[str, Any]],
    audit: dict[str, Any],
    *,
    expected_collocations: dict[int, str] | None = None,
) -> dict[int, dict[str, Any]]:
    coherence = audit.get("coherence")
    if (
        not isinstance(coherence, dict)
        or coherence.get("verdict") not in {"coherent", "assembled"}
        or not all(
            isinstance(coherence.get(field), bool)
            for field in (
                "characters_consistent",
                "timeline_present",
                "connections_present",
            )
        )
        or not isinstance(coherence.get("reason"), str)
        or not coherence["reason"].strip()
    ):
        raise ValueError("G12_COHERENCE_AUDIT_INVALID")
    if (
        coherence["verdict"] != "coherent"
        or not all(
            coherence[field]
            for field in (
                "characters_consistent",
                "timeline_present",
                "connections_present",
            )
        )
    ):
        raise ValueError(
            "G12_PASSAGE_NOT_COHERENT "
            f"audit={json.dumps(coherence, ensure_ascii=False)}"
        )

    by_index = validate_cross_audit_shape(questions, audit)
    for question in questions:
        question_index = question["question_index"]
        item = by_index[question_index]
        assessments = item["option_assessments"]
        accepted_indices = [
            option_index
            for option_index, assessment in enumerate(assessments, start=1)
            if all(
                assessment[field]
                for field in ("grammar_ok", "semantic_ok", "idiomatic")
            )
        ]
        if len(accepted_indices) == 0:
            raise ValueError(
                f"H10_NO_VALID_OPTIONS question_index={question_index}"
            )
        if len(accepted_indices) > 1:
            raise ValueError(
                "H10_MULTIPLE_VALID_OPTIONS "
                f"question_index={question_index} "
                f"option_indices={accepted_indices}"
            )
        answer_index = question["options"].index(question["answer"]) + 1
        if accepted_indices != [answer_index]:
            raise ValueError(
                "H10_ANSWER_NOT_VALID "
                f"question_index={question_index} "
                f"answer_index={answer_index} accepted={accepted_indices}"
            )
        collocation = item["answer_collocation"]
        clue_assessment = item["context_clue_assessment"]
        if clue_assessment["direct_lexical_relationship"] is True:
            raise ValueError(
                "G13_DIRECT_LEXICAL_RELATIONSHIP "
                f"question_index={question_index} "
                f"reason={clue_assessment['reason']}"
            )
        if (
            not clue_assessment["clue_is_verbatim"]
            or not clue_assessment["supports_answer"]
            or not clue_assessment["excludes_distractors"]
        ):
            raise ValueError(
                "CONTEXT_CLUE_NOT_DECISIVE "
                f"question_index={question_index} "
                f"assessment={json.dumps(clue_assessment, ensure_ascii=False)}"
            )
        if (
            expected_collocations is not None
            and collocation["phrase"]
            != expected_collocations[question_index]
        ):
            raise ValueError(
                "H11_COLLOCATION_PHRASE_MISMATCH "
                f"question_index={question_index} "
                f"expected={expected_collocations[question_index]!r} "
                f"actual={collocation['phrase']!r}"
            )
        if collocation["standard"] is not True:
            raise ValueError(
                "H11_COLLOCATION_NOT_CONFIRMED "
                f"question_index={question_index} "
                f"phrase={collocation['phrase']!r} "
                f"reason={collocation['reason']}"
            )
    return by_index
