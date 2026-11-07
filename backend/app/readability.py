"""Readability observations for generated English passages."""

from __future__ import annotations

import re


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


def _sentence_count(text: str) -> int:
    return max(
        1,
        len(
            [
                item
                for item in re.split(r"[.!?]+", text)
                if item.strip()
            ]
        ),
    )


def _syllables(word: str) -> int:
    normalized = re.sub(r"[^a-z]", "", word.lower())
    if not normalized:
        return 0
    vowel_groups = re.findall(r"[aeiouy]+", normalized)
    count = len(vowel_groups)
    if normalized.endswith("e") and not normalized.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(1, count)


def flesch_reading_ease(text: str) -> float:
    words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)
    word_count = len(words)
    if word_count == 0:
        raise ValueError("READABILITY_TEXT_REQUIRES_WORDS")
    sentence_count = _sentence_count(text)
    syllable_count = sum(_syllables(word) for word in words)
    return round(
        206.835
        - 1.015 * (word_count / sentence_count)
        - 84.6 * (syllable_count / word_count),
        2,
    )
