from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from backend.app.deepseek_generation import (
    CostLedger,
    DeepSeekResponse,
    RequestRecord,
    run_repair_loop,
)
from backend.app.m2_pilot import load_pilot_schedule


ROOT = Path(__file__).resolve().parents[2]


def load_rework_module():
    path = ROOT / "scripts" / "rework-m2b-cloze.py"
    spec = importlib.util.spec_from_file_location("rework_m2b_cloze", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_cloze_gate_failure_is_fed_back_into_repair_prompt() -> None:
    module = load_rework_module()
    assignment = {
        "question_index": 12,
        **load_pilot_schedule()["passages"][0]["questions"][11],
    }
    assignments = [assignment]
    rejected = {
        "question_index": 12,
        "stem": "Everyone can take (12) ______ mistakes while learning.",
        "options": ["taken", "take", "taking", "takes"],
        "answer": "take",
        "knowledge_points": ["verb meaning in context"],
        "grammar_tags": ["articles"],
        "book_source": assignment["book_source"],
        "difficulty": assignment["difficulty"],
        "invalid": False,
        "invalid_reason": "",
    }
    accepted = {
        **rejected,
        "stem": "It is normal to (12) ______ mistakes while learning.",
        "options": ["take", "grab", "make", "have"],
    }

    class FakeClient:
        def __init__(self) -> None:
            self.prompts = []
            self.requests = []

        def chat_json(self, purpose, prompt, **_kwargs):
            self.prompts.append(prompt)
            data = {
                "questions": [
                    rejected if len(self.prompts) == 1 else accepted
                ]
            }
            self.requests.append(
                RequestRecord(
                    purpose=purpose,
                    attempt=1,
                    status="ok",
                    prompt_tokens=100,
                    completion_tokens=20,
                    elapsed_seconds=0.1,
                    finish_reason="stop",
                )
            )
            return DeepSeekResponse(
                data=data,
                finish_reason="stop",
                prompt_tokens=100,
                completion_tokens=20,
                elapsed_seconds=0.1,
                request_id=f"request-{len(self.prompts)}",
            )

    client = FakeClient()
    ledger = CostLedger(
        {
            "price_input_per_1m_cny": 2.0,
            "price_output_per_1m_cny": 8.0,
            "budget_cap_cny": {"pilot": 10.0},
        }
    )

    result = run_repair_loop(
        client=client,
        ledger=ledger,
        purpose="questions:cloze:lexical-rework",
        prompt="Generate lexical cloze questions.",
        validate=lambda data: module.validate_question_batch(assignments, data),
        max_repair_retries=1,
    )

    assert result == [accepted]
    assert len(client.prompts) == 2
    serialized_errors = client.prompts[1].split(
        "The previous response was rejected.", 1
    )[1].split("Fix these exact errors and return the complete JSON object again:", 1)[1]
    repair_feedback = json.loads(serialized_errors)[0]
    assert "H7_OPTION_ECHOES_STEM" in repair_feedback
    assert '"question_index": 12' in repair_feedback
    assert json.dumps(rejected["stem"]) in repair_feedback
    assert json.dumps(rejected["options"], ensure_ascii=False) in repair_feedback


def test_existing_accepted_questions_are_resumed_by_index(tmp_path) -> None:
    module = load_rework_module()
    evidence_path = tmp_path / "cloze-rework.json"
    accepted_questions = [
        {"question_index": 1, "stem": "First question"},
        {"question_index": 13, "stem": "Thirteenth question"},
    ]
    evidence_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "accepted_questions": accepted_questions,
            }
        ),
        encoding="utf-8",
    )

    resumed = module.load_resume_questions(evidence_path)

    assert resumed == {
        1: accepted_questions[0],
        13: accepted_questions[1],
    }


def test_collocation_phrase_includes_words_after_the_blank() -> None:
    path = ROOT / "scripts" / "rewrite-m2b-cloze-v3.py"
    spec = importlib.util.spec_from_file_location("rewrite_m2b_cloze_v3", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    phrase = module.collocation_phrase(
        "They worked hard to (6) ______ their main goal.",
        6,
        "achieve",
    )

    assert phrase == "achieve their main goal"
