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


def test_deepseek_contract_uses_environment_key_and_safe_budget_defaults() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "generation-model.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract["provider"] == "deepseek"
    assert contract["base_url"] == "https://api.deepseek.com/v1"
    assert contract["api_key_env"] == "DEEPSEEK_API_KEY"
    assert "api_key" not in contract
    assert contract["max_tokens"] == 8192
    assert contract["thinking"] == {"type": "disabled"}
    assert contract["temperature"] == 0.5
    assert contract["transport"] == "json_object"
    assert contract["prompt_version"] == "m2-gen-v2"
    assert contract["budget_cap_cny"] == {"pilot": 10, "bulk": 100}
    assert contract["request_retries_max"] == 3
    assert contract["repair_retries_max"] == 1
    assert contract["circuit_breaker_consecutive_failures"] == 5
    assert contract["budget_stop_ratio"] == 0.8
