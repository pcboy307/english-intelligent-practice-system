from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module():
    path = ROOT / "scripts" / "build-m2-full-schedule.py"
    spec = importlib.util.spec_from_file_location("build_m2_full_schedule", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_has_exact_m2_quotas_and_coverage() -> None:
    module = load_module()
    schedule = module.build_schedule()
    passages = schedule["passages"]
    questions = [
        {**question, "type": passage["type"]}
        for passage in passages
        for question in passage["questions"]
    ]

    assert len(passages) == 47
    assert len(questions) == 300
    assert Counter(item["type"] for item in questions) == {
        "cloze": 90,
        "grammar_fill": 60,
        "reading": 100,
        "gap_fill": 50,
    }
    assert Counter(item["difficulty"] for item in questions) == {
        1: 45,
        2: 90,
        3: 105,
        4: 45,
        5: 15,
    }
    book_counts = Counter(
        module.book_tag(item["book_source"])
        for item in questions
        if item["type"] in {"cloze", "grammar_fill"}
    )
    assert book_counts == {
        "选必二": 68,
        "选必一": 45,
        "必修": 30,
        "跨册": 7,
    }
    elective = sum(
        module.book_tag(item["book_source"]) in {"选必一", "选必二"}
        for item in questions
        if item["type"] in {"reading", "gap_fill"}
    )
    assert elective >= 75
    targets = Counter(
        item["cloze_target"]
        for item in questions
        if item["type"] == "cloze"
    )
    assert len(targets) == 45
    assert set(targets.values()) == {2}
    grammar_counts = Counter(
        tag
        for item in questions
        if item["type"] == "grammar_fill"
        for tag in item["grammar_tags"]
    )
    assert len(grammar_counts) == 21
    assert sum(grammar_counts.values()) == 60
    assert set(grammar_counts.values()) <= {2, 3}
    assert Counter(
        item["reading_type"]
        for item in questions
        if item["type"] == "reading"
    ) == {
        "main_idea": 20,
        "detail": 20,
        "inference": 20,
        "vocabulary_in_context": 20,
        "purpose_or_attitude": 20,
    }
    assert Counter(
        item["cohesion_type"]
        for item in questions
        if item["type"] == "gap_fill"
    ) == {
        "pronoun_reference": 13,
        "logical_connector": 13,
        "lexical_repetition": 12,
        "semantic_contrast": 12,
    }
