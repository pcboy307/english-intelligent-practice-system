#!/usr/bin/env python3
"""Audit the frozen vocabulary source against samples and passage fixtures."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BASIC_SAMPLE = [
    "because",
    "important",
    "decide",
    "different",
    "develop",
    "ability",
    "accident",
    "achieve",
    "active",
    "advice",
    "afford",
    "afraid",
    "agree",
    "air",
    "animal",
    "answer",
    "apple",
    "art",
    "ask",
    "bad",
]

ADVANCED_SAMPLE = [
    "ubiquitous",
    "paradigm",
    "meticulous",
    "exacerbate",
    "corroborate",
    "anomaly",
    "synthesize",
    "notwithstanding",
    "albeit",
    "ostensibly",
    "juxtapose",
    "pragmatic",
    "intricate",
    "ambiguity",
    "profound",
    "skeptical",
    "resilient",
    "controversy",
    "hypothetical",
    "disproportionate",
]

IRREGULAR = {
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
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    "children": "child",
    "men": "man",
    "women": "woman",
    "people": "people",
    "leaves": "leaf",
    "lives": "life",
    "wives": "wife",
    "knives": "knife",
    "mice": "mouse",
    "teeth": "tooth",
    "feet": "foot",
    "went": "go",
    "gone": "go",
    "made": "make",
    "took": "take",
    "taken": "take",
    "wrote": "write",
    "written": "write",
    "ate": "eat",
    "eaten": "eat",
    "saw": "see",
    "seen": "see",
    "came": "come",
    "became": "become",
    "gave": "give",
    "given": "give",
    "got": "get",
    "gotten": "get",
    "felt": "feel",
    "built": "build",
    "wore": "wear",
    "worn": "wear",
    "known": "know",
    "sung": "sing",
    "grew": "grow",
    "grown": "grow",
    "bought": "buy",
    "brought": "bring",
    "thought": "think",
    "taught": "teach",
    "caught": "catch",
    "kept": "keep",
    "left": "leave",
    "lost": "lose",
    "meant": "mean",
    "met": "meet",
    "paid": "pay",
    "ran": "run",
    "said": "say",
    "sold": "sell",
    "sent": "send",
    "spent": "spend",
    "stood": "stand",
    "told": "tell",
    "understood": "understand",
    "won": "win",
}

CONTRACTIONS = {
    "aren't": "are not",
    "can't": "can not",
    "couldn't": "could not",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hadn't": "had not",
    "hasn't": "has not",
    "haven't": "have not",
    "he's": "he is",
    "i'd": "i would",
    "i'll": "i will",
    "i'm": "i am",
    "i've": "i have",
    "isn't": "is not",
    "it's": "it is",
    "let's": "let us",
    "she's": "she is",
    "shouldn't": "should not",
    "that's": "that is",
    "there's": "there is",
    "they're": "they are",
    "wasn't": "was not",
    "we're": "we are",
    "we've": "we have",
    "weren't": "were not",
    "what's": "what is",
    "won't": "will not",
    "wouldn't": "would not",
    "you're": "you are",
    "you've": "you have",
}


def candidate_lemmas(token: str) -> list[str]:
    candidates = [token]
    if token in IRREGULAR:
        candidates.append(IRREGULAR[token])
    if token.endswith("ies") and len(token) > 4:
        candidates.append(token[:-3] + "y")
    if token.endswith("ied") and len(token) > 4:
        candidates.append(token[:-3] + "y")
    if token.endswith("ing") and len(token) >= 5:
        stem = token[:-3]
        candidates.extend([stem, stem + "e", stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem])
    if token.endswith("ed") and len(token) >= 4:
        stem = token[:-2]
        candidates.extend([stem, stem + "e", stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem])
    if token.endswith("es") and len(token) > 4:
        candidates.append(token[:-2])
    if token.endswith("s") and len(token) > 3:
        candidates.append(token[:-1])
    if token.endswith("er") and len(token) > 3:
        candidates.append(token[:-2])
    if token.endswith("est") and len(token) > 5:
        candidates.append(token[:-3])
    if token.endswith("ly") and len(token) > 4:
        candidates.append(token[:-2])
    if token.endswith("less") and len(token) > 6:
        candidates.append(token[:-4])
    if token.endswith("ful") and len(token) > 5:
        candidates.append(token[:-3])
    if token.endswith("ness") and len(token) > 6:
        candidates.append(token[:-4])
    return list(dict.fromkeys(candidates))


def resolve(token: str, words: set[str]) -> str:
    for candidate in candidate_lemmas(token):
        if candidate in words:
            return candidate
    return token


def count_passage(
    text: str,
    words: set[str],
    phrases: set[str],
    proper_nouns: list[str] | None = None,
) -> dict:
    normalized_text = text.lower().replace("’", "'")
    for contraction, expansion in CONTRACTIONS.items():
        normalized_text = re.sub(rf"\b{re.escape(contraction)}\b", expansion, normalized_text)
    tokens = re.findall(r"[a-z]+(?:['-][a-z]+)*", normalized_text)
    excluded = {noun.lower() for noun in (proper_nouns or [])}
    phrase_hits: list[str] = []
    consumed = [False] * len(tokens)
    for phrase in sorted(phrases, key=lambda value: len(value.split()), reverse=True):
        phrase_tokens = phrase.split()
        size = len(phrase_tokens)
        for index in range(len(tokens) - size + 1):
            if any(consumed[index:index + size]):
                continue
            if tokens[index:index + size] == phrase_tokens:
                phrase_hits.append(phrase)
                for offset in range(size):
                    consumed[index + offset] = True

    denominator_tokens = [
        token
        for index, token in enumerate(tokens)
        if not consumed[index] and token not in excluded
    ]
    unknown = [token for token in denominator_tokens if resolve(token, words) not in words]
    ratio = len(unknown) / len(denominator_tokens) if denominator_tokens else 0.0
    return {
        "raw_tokens": len(tokens),
        "phrase_hits": phrase_hits,
        "single_word_denominator": len(denominator_tokens),
        "unknown": unknown,
        "unknown_ratio": ratio,
        "passes": ratio <= 0.03,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    vocabulary = json.loads(args.vocabulary.read_text(encoding="utf-8"))
    all_entries = {entry["word"].lower() for entry in vocabulary["entries"]}
    single_words = {
        word for word in all_entries
        if re.fullmatch(r"[a-z]+(?:['-][a-z]+)*", word)
    }
    phrases = all_entries - single_words

    basic = {word: word in single_words for word in BASIC_SAMPLE}
    advanced = {word: word in all_entries for word in ADVANCED_SAMPLE}
    passages = json.loads(args.passages.read_text(encoding="utf-8"))
    passage_results = {
        passage["id"]: count_passage(
            passage["text"],
            single_words,
            phrases,
            passage.get("proper_nouns"),
        )
        for passage in passages
    }

    checks_pass = (
        all(basic.values())
        and not any(advanced.values())
        and all(item["passes"] for item in passage_results.values())
    )
    result = {
        "basic_sample_20": basic,
        "advanced_sample_20": advanced,
        "passage_results": passage_results,
        "checks_pass": checks_pass,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    if not checks_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
