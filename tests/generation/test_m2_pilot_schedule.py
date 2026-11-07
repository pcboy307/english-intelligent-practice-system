from __future__ import annotations

import copy
import json
from pathlib import Path

from backend.app.m2_pilot import validate_pilot_schedule


ROOT = Path(__file__).resolve().parents[2]


def load() -> tuple[dict, dict]:
    generation = json.loads(
        (ROOT / "config" / "generation.json").read_text(encoding="utf-8")
    )
    schedule = json.loads(
        (ROOT / "config" / "pilot-schedule.json").read_text(encoding="utf-8")
    )
    return generation, schedule


def test_pilot_schedule_matches_exact_29_question_paper_constraints() -> None:
    generation, schedule = load()

    result = validate_pilot_schedule(
        schedule,
        generation["pilot"]["paper_targets"],
    )

    assert result["accepted"] is True
    assert result["metrics"]["question_count"] == 29
    assert result["metrics"]["difficulty"] == {
        "d1": 6,
        "d2": 6,
        "d3": 11,
        "d4": 4,
        "d5": 2,
    }
    assert result["metrics"]["book_tag"] == {
        "选必二": 13,
        "选必一": 9,
        "必修": 6,
        "跨册": 1,
    }
    assert result["metrics"]["max_grammar_tag_count"] <= 3
    assert result["metrics"]["topic_count"] == 3


def test_pilot_schedule_rejects_tag_repetition_above_three() -> None:
    generation, schedule = load()
    broken = copy.deepcopy(schedule)
    for question in broken["passages"][0]["questions"][:4]:
        question["grammar_tags"] = ["tense_system"]

    result = validate_pilot_schedule(
        broken,
        generation["pilot"]["paper_targets"],
    )

    assert result["accepted"] is False
    assert "GRAMMAR_TAG_REPEAT_EXCEEDS_3" in result["failures"]
