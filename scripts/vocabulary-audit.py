#!/usr/bin/env python3
"""Audit the frozen vocabulary source against samples and passage fixtures."""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZATION_CONTRACT = json.loads(
    (ROOT / "contracts" / "vocabulary-normalization.json").read_text(
        encoding="utf-8"
    )
)

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
    "began": "begin",
    "knew": "know",
    "fallen": "fall",
    "fell": "fall",
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
    "slept": "sleep",
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

IRREGULAR = NORMALIZATION_CONTRACT["irregular_inflections"]
SPELLING_VARIANTS = {
    original: tuple(rule)
    for original, rule in NORMALIZATION_CONTRACT["spelling_variants"].items()
}
ALLOWED_RULES = set(NORMALIZATION_CONTRACT["allowed_rules"])
MAX_CHAIN_DEPTH = int(NORMALIZATION_CONTRACT["max_chain_depth"])


def resolution_candidates(token: str) -> list[tuple[str, str]]:
    candidates = [(token, "exact")]
    if token.endswith("'s") and len(token) > 3:
        candidates.append((token[:-2], "possessive_s"))
    if token in SPELLING_VARIANTS:
        candidates.append(SPELLING_VARIANTS[token])
    if token in IRREGULAR:
        candidates.append((IRREGULAR[token], "irregular_inflection"))
    if token.endswith("ies") and len(token) > 4:
        candidates.append((token[:-3] + "y", "plural_ies_to_y"))
    if token.endswith("ied") and len(token) > 4:
        candidates.append((token[:-3] + "y", "past_ied_to_y"))
    if token.endswith("ing") and len(token) >= 5:
        stem = token[:-3]
        candidates.extend(
            [
                (stem, "inflection_ing"),
                (stem + "e", "inflection_ing_restore_e"),
                (
                    stem[:-1]
                    if len(stem) > 2 and stem[-1] == stem[-2]
                    else stem,
                    "inflection_ing_undouble",
                ),
            ]
        )
    if token.endswith("ed") and len(token) >= 4:
        stem = token[:-2]
        candidates.extend(
            [
                (stem, "inflection_ed"),
                (stem + "e", "inflection_ed_restore_e"),
                (
                    stem[:-1]
                    if len(stem) > 2 and stem[-1] == stem[-2]
                    else stem,
                    "inflection_ed_undouble",
                ),
            ]
        )
    if token.endswith("es") and len(token) >= 4:
        candidates.append((token[:-2], "plural_es"))
    if token.endswith("s") and len(token) > 3:
        candidates.append((token[:-1], "plural_s"))
    if token.endswith("er") and len(token) > 3:
        candidates.extend(
            [
                (token[:-2], "suffix_er"),
                (token[:-2] + "e", "comparative_er_restore_e"),
            ]
        )
    if token.endswith("est") and len(token) > 5:
        candidates.extend(
            [
                (token[:-3], "comparative_est"),
                (token[:-3] + "e", "comparative_est_restore_e"),
            ]
        )
    if token.endswith("ier") and len(token) > 4:
        candidates.append((token[:-3] + "y", "comparative_ier_to_y"))
    if token.endswith("iest") and len(token) > 5:
        candidates.append((token[:-4] + "y", "comparative_iest_to_y"))
    if token.endswith("ly") and len(token) > 4:
        candidates.extend(
            [
                (token[:-2], "derivation_ly"),
                (token[:-2] + "e", "derivation_ly_restore_e"),
            ]
        )
    if token.endswith("ply") and len(token) > 4:
        candidates.append((token[:-1] + "e", "derivation_ply_to_le"))
    if token.endswith("less") and len(token) > 6:
        candidates.append((token[:-4], "derivation_less"))
    if token.endswith("ful") and len(token) > 5:
        candidates.append((token[:-3], "derivation_ful"))
    if token.endswith("able") and len(token) > 6:
        candidates.extend(
            [
                (token[:-4], "derivation_able"),
                (token[:-4] + "e", "derivation_able_restore_e"),
            ]
        )
    if token.endswith("ness") and len(token) > 6:
        candidates.append((token[:-4], "derivation_ness"))
        if token.endswith("iness") and len(token) > 7:
            candidates.append((token[:-4] + "y", "derivation_ness_to_y"))
    if token.endswith("ity") and len(token) > 5:
        candidates.extend(
            [
                (token[:-3], "derivation_ity"),
                (token[:-3] + "e", "derivation_ity_to_e"),
            ]
        )
        if token.endswith("osity") and len(token) > 7:
            candidates.append(
                (token[:-5] + "ous", "derivation_ity_to_ous")
            )
    if token.endswith("ship") and len(token) > 5:
        candidates.append((token[:-4], "derivation_ship"))
    if token.endswith("ment") and len(token) > 5:
        candidates.extend(
            [
                (token[:-4], "derivation_ment"),
                (token[:-4] + "e", "derivation_ment_restore_e"),
            ]
        )
    if token.endswith("tion") and len(token) > 6:
        candidates.extend(
            [
                (token[:-4], "derivation_tion"),
                (token[:-4] + "te", "derivation_tion_to_te"),
            ]
        )
    if token.endswith("ern") and len(token) > 5:
        candidates.append((token[:-3], "derivation_ern_to_base"))
    if token.endswith("al") and len(token) > 5:
        candidates.append((token[:-2], "derivation_al"))
    if token.endswith("ism") and len(token) > 5:
        candidates.append((token[:-3], "derivation_ism"))
    if token.endswith("ation") and len(token) > 7:
        candidates.extend(
            [
                (token[:-5], "derivation_ation"),
                (token[:-5] + "e", "derivation_ation_restore_e"),
            ]
        )
    if token.endswith("ance") and len(token) > 6:
        candidates.append((token[:-3] + "t", "derivation_ance_to_ant"))
    if token.endswith("th") and len(token) > 4:
        candidates.append((token[:-2], "derivation_th"))
    if token.endswith("or") and len(token) > 4:
        candidates.extend(
            [
                (token[:-2], "agent_or"),
                (token[:-2] + "e", "agent_or_restore_e"),
            ]
        )

    expanded = list(candidates)
    for candidate, _rule in candidates:
        if candidate.endswith("y") and len(candidate) > 3:
            expanded.append((candidate[:-1], "y_to_root"))
    unique = []
    seen = set()
    for candidate, rule in expanded:
        key = (candidate, rule)
        if key not in seen:
            seen.add(key)
            unique.append((candidate, rule))
    return [
        (candidate, rule)
        for candidate, rule in unique
        if rule == "exact" or rule in ALLOWED_RULES
    ]


def candidate_lemmas(token: str) -> list[str]:
    return list(
        dict.fromkeys(
            candidate for candidate, _rule in resolution_candidates(token)
        )
    )


def resolve_with_audit(
    token: str,
    words: set[str],
) -> tuple[str, list[str]]:
    queue = deque([(token, [])])
    visited = {token}
    while queue:
        current, applied_rules = queue.popleft()
        for candidate, rule in resolution_candidates(current):
            next_rules = (
                applied_rules
                if rule == "exact"
                else [*applied_rules, rule]
            )
            if candidate in words:
                if (
                    token.endswith("ies")
                    and next_rules
                    and next_rules[0] != "plural_ies_to_y"
                ):
                    next_rules = ["plural_ies_to_y", *next_rules]
                return candidate, next_rules
            if (
                rule != "exact"
                and candidate != current
                and candidate not in visited
                and len(next_rules) < MAX_CHAIN_DEPTH
            ):
                visited.add(candidate)
                queue.append((candidate, next_rules))
    return token, []


def resolve(token: str, words: set[str]) -> str:
    return resolve_with_audit(token, words)[0]


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
    resolutions = []
    unknown = []
    for token in denominator_tokens:
        matched, rules = resolve_with_audit(token, words)
        if matched not in words:
            unknown.append(token)
        elif rules:
            resolutions.append(
                {
                    "original": token,
                    "matched_entry": matched,
                    "rules": rules,
                }
            )
    ratio = len(unknown) / len(denominator_tokens) if denominator_tokens else 0.0
    return {
        "raw_tokens": len(tokens),
        "phrase_hits": phrase_hits,
        "single_word_denominator": len(denominator_tokens),
        "unknown": unknown,
        "unknown_ratio": ratio,
        "resolutions": resolutions,
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
