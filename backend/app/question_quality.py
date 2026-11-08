"""Lexical and question-type quality gates for generated practice items."""

from __future__ import annotations

import re
from collections import Counter


STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "with",
    "and",
    "or",
    "but",
    "be",
    "is",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "should",
}


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())


def lemma(token: str) -> str:
    value = token.lower()
    irregular = {
        "am": "be",
        "is": "be",
        "are": "be",
        "was": "be",
        "were": "be",
        "been": "be",
        "has": "have",
        "had": "have",
        "does": "do",
        "did": "do",
        "done": "do",
        "went": "go",
        "gone": "go",
        "made": "make",
        "took": "take",
        "taken": "take",
        "wrote": "write",
        "written": "write",
        "saw": "see",
        "seen": "see",
        "built": "build",
        "thought": "think",
        "taught": "teach",
        "paid": "pay",
        "said": "say",
        "told": "tell",
    }
    if value in irregular:
        return irregular[value]
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("ing") and len(value) > 5:
        stem = value[:-3]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem
    if value.endswith("ed") and len(value) > 4:
        stem = value[:-2]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem
    if value.endswith("es") and len(value) > 4:
        return value[:-2]
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    if value.endswith("ly") and len(value) > 5:
        return value[:-2]
    return value


def content_lemmas(text: str) -> list[str]:
    return [
        lemma(token)
        for token in tokens(text)
        if token not in STOPWORDS
    ]


def validate_cloze_options(
    *,
    stem: str,
    options: list[str],
    answer: str,
) -> list[dict]:
    failures = []
    option_lemmas = [content_lemmas(option.replace("should ", "")) for option in options]
    flattened = [item for row in option_lemmas for item in row]
    repeated = sorted(
        token for token, count in Counter(flattened).items() if count > 1
    )
    if repeated:
        failures.append(
            {
                "code": "H6_OPTION_SAME_LEMMA",
                "message": "Cloze options repeat the same lemma.",
                "repeated_lemma": repeated,
            }
        )

    stem_lemmas = set(content_lemmas(stem))
    echoed = sorted(
        {
            item
            for row in option_lemmas
            for item in row
            if item in stem_lemmas
        }
    )
    if echoed:
        failures.append(
            {
                "code": "H7_OPTION_ECHOES_STEM",
                "message": "A cloze option appears in another form in the stem.",
                "echoed_lemma": echoed,
            }
        )
    if answer not in options:
        failures.append(
            {
                "code": "ANSWER_NOT_IN_OPTIONS",
                "message": "Cloze answer must be one of the four options.",
            }
        )
    return failures


READING_META_PATTERNS = [
    re.compile(r"which sentence contains", re.IGNORECASE),
    re.compile(r"哪一句含有"),
    re.compile(r"contains a .* (?:clause|construction|voice)", re.IGNORECASE),
    re.compile(r"含.*(?:从句|语态)"),
]


def validate_reading_question_type(stem: str) -> list[dict]:
    if any(pattern.search(stem) for pattern in READING_META_PATTERNS):
        return [
            {
                "code": "H8_META_LANGUAGE_QUESTION",
                "message": (
                    "Reading question asks for grammar/linguistic structure "
                    "identification."
                ),
            }
        ]
    return []
