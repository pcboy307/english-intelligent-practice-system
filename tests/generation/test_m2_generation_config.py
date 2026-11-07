from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pilot_config_declares_model_budget_and_exact_29_question_shape() -> None:
    config = json.loads(
        (ROOT / "config" / "generation.json").read_text(encoding="utf-8")
    )

    assert config["model"]["identifier"] == "qwen3.5:4b-q4_K_M"
    assert config["model"]["max_retries"] == 3
    assert config["budget"]["pilot_total_token_cap"] > 0
    assert config["pilot"]["target_size"] == 300
    assert config["pilot"]["batch_id"] == "M2.0-PILOT"
    assert config["pilot"]["passages"] == [
        {"type": "cloze", "questions": 15},
        {"type": "grammar_fill", "questions": 10},
        {"type": "reading", "questions": 4},
    ]
