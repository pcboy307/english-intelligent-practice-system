from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_high_frequency_cloze_words_are_45_whitelisted_open_class_words() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "high-frequency-cloze-words.json").read_text(
            encoding="utf-8"
        )
    )
    whitelist = {
        item["word"].lower(): item
        for item in json.loads(
            (ROOT / "contracts" / "vocabulary-whitelist.json").read_text(
                encoding="utf-8"
            )
        )["entries"]
    }
    words = [item["word"].lower() for item in contract["words"]]

    assert contract["count"] == 45
    assert len(words) == len(set(words)) == 45
    assert set(words) <= set(whitelist)
    assert all(not whitelist[word].get("closed_class") for word in words)
    assert {
        "anxious",
        "confident",
        "curious",
        "reliable",
        "ambitious",
        "achieve",
        "adapt",
        "encourage",
        "persuade",
        "concentrate",
        "gradually",
        "eventually",
        "independently",
        "confidence",
        "opportunity",
    } <= set(words)


def test_m2_quota_allocation_is_internally_exact() -> None:
    quota = json.loads(
        (ROOT / "config" / "m2-quota-allocation.json").read_text(
            encoding="utf-8"
        )
    )

    assert sum(item["passages"] for item in quota["types"].values()) == 47
    assert sum(item["questions"] for item in quota["types"].values()) == 300
    assert sum(quota["difficulty"].values()) == 300
    assert quota["difficulty"] == {
        "1": 45,
        "2": 90,
        "3": 105,
        "4": 45,
        "5": 15,
    }
    assert sum(quota["book_tag_cloze_grammar"].values()) == 150
    assert sum(quota["grammar_tag_targets"].values()) == 60
    assert sum(quota["reading_subtypes"].values()) == 100
    assert sum(quota["gap_cohesion_types"].values()) == 50


def test_vocabulary_normalization_rules_are_frozen_in_a_separate_contract() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "vocabulary-normalization.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract["schema_version"] == "1.0.0"
    assert contract["max_chain_depth"] == 3
    assert {
        "plural_ies_to_y",
        "derivation_ly",
        "derivation_ity_to_ous",
        "derivation_ern_to_base",
    } <= set(contract["allowed_rules"])
    assert contract["irregular_inflections"]["held"] == "hold"
    assert contract["spelling_variants"]["program"][0] == "programme"
