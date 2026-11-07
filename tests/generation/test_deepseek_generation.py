from __future__ import annotations

import json
import os

import httpx
import pytest

from backend.app.deepseek_generation import (
    BudgetThresholdReached,
    CircuitOpen,
    CostLedger,
    DeepSeekClient,
    DeepSeekResponse,
    FinishReasonError,
    RepairExhausted,
    RequestRecord,
    select_v41_model_id,
    TransportRetriesExhausted,
    run_repair_loop,
)
from backend.app.m2_deepseek_pipeline import generate_pilot_passage
from backend.app.m2_pilot import load_pilot_schedule


CONFIG = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model_id": "listed-model-id",
    "api_key_env": "DEEPSEEK_API_KEY",
    "max_tokens": 4096,
    "temperature": 0.5,
    "price_input_per_1m_cny": 2.0,
    "price_output_per_1m_cny": 8.0,
}


def completion(
    content: str,
    *,
    finish_reason: str = "stop",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> dict:
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content},
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def test_client_uses_environment_key_json_mode_and_records_finish_reason(
    monkeypatch,
) -> None:
    captured = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=completion('{"ok": true}', finish_reason="stop"),
        )

    client = DeepSeekClient(
        CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.chat_json("ping", "Return a tiny JSON object.")

    assert response.data == {"ok": True}
    assert response.finish_reason == "stop"
    assert response.prompt_tokens == 100
    assert response.completion_tokens == 50
    assert client.requests[-1].raw_content == '{"ok": true}'
    assert captured["headers"]["authorization"] == "Bearer test-secret"
    assert captured["payload"]["model"] == "listed-model-id"
    assert captured["payload"]["max_tokens"] == 4096
    assert captured["payload"]["temperature"] == 0.5
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["thinking"] == {"type": "disabled"}


def test_ping_request_is_tiny_and_does_not_require_json_output(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=completion("p", finish_reason="length", prompt_tokens=8, completion_tokens=1),
        )

    client = DeepSeekClient(
        CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.ping()

    assert result["finish_reason"] == "length"
    assert result["prompt_tokens"] == 8
    assert captured["payload"]["max_tokens"] == 1
    assert "response_format" not in captured["payload"]


def test_client_rejects_finish_reason_length_before_schema_validation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=completion('{"partial":', finish_reason="length"),
        )

    client = DeepSeekClient(
        CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(FinishReasonError) as raised:
        client.chat_json("passage", "Generate JSON.")

    assert calls == 1
    assert client.requests[-1].status == "finish_reason_length"
    assert raised.value.raw_content == '{"partial":'


def test_client_retries_transport_errors_with_exponential_backoff(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    calls = 0
    sleeps = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json=completion('{"ok": true}'))

    client = DeepSeekClient(
        CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
    )

    response = client.chat_json("questions", "Generate JSON.")

    assert response.data == {"ok": True}
    assert calls == 3
    assert sleeps == [1.0, 2.0]
    assert [item.status for item in client.requests] == [
        "transport_error",
        "transport_error",
        "ok",
    ]


def test_client_opens_circuit_after_five_consecutive_failed_http_attempts(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": "down"})

    client = DeepSeekClient(
        CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(TransportRetriesExhausted):
        client.chat_json("passage", "Generate JSON.")

    with pytest.raises(CircuitOpen):
        client.chat_json("questions", "Generate JSON.")

    assert calls == 5


def test_cost_ledger_calculates_cny_from_separate_input_and_output_tokens() -> None:
    ledger = CostLedger(CONFIG)
    ledger.record(
        purpose="passage",
        prompt_tokens=1_000_000,
        completion_tokens=500_000,
    )

    assert ledger.total_cny == pytest.approx(6.0)
    assert ledger.total_tokens == 1_500_000


def test_cost_ledger_stops_at_eighty_percent_of_budget() -> None:
    config = {
        **CONFIG,
        "budget_cap_cny": {"pilot": 10.0, "bulk": 100.0},
    }
    ledger = CostLedger(config)
    ledger.record(
        purpose="passage",
        prompt_tokens=1_000_000,
        completion_tokens=900_000,
    )

    with pytest.raises(BudgetThresholdReached):
        ledger.assert_below_threshold("pilot")


def test_repair_loop_retries_only_the_failed_step_with_error_feedback() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.prompts = []
            self.requests = []

        def chat_json(self, purpose, prompt):
            self.prompts.append((purpose, prompt))
            questions = [] if len(self.prompts) == 1 else [1]
            self.requests.append(
                RequestRecord(
                    purpose=purpose,
                    attempt=1,
                    status="ok",
                    prompt_tokens=100,
                    completion_tokens=20,
                    elapsed_seconds=0.5,
                    finish_reason="stop",
                )
            )
            return DeepSeekResponse(
                data={"questions": questions},
                finish_reason="stop",
                prompt_tokens=100,
                completion_tokens=20,
                elapsed_seconds=0.5,
                request_id=f"req-{len(self.prompts)}",
            )

    def validate(data):
        if len(data["questions"]) != 1:
            raise ValueError("QUESTION_COUNT_MISMATCH")
        return data

    client = FakeClient()
    ledger = CostLedger({**CONFIG, "budget_cap_cny": {"pilot": 10.0}})
    result = run_repair_loop(
        client=client,
        ledger=ledger,
        purpose="questions-batch-1",
        prompt="Generate five questions.",
        validate=validate,
        max_repair_retries=3,
    )

    assert result == {"questions": [1]}
    assert len(client.prompts) == 2
    assert "QUESTION_COUNT_MISMATCH" in client.prompts[1][1]
    assert ledger.total_tokens == 240
    assert [item.status for item in client.requests] == [
        "validation_error",
        "ok",
    ]


def test_repair_loop_stops_after_three_repairs() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def chat_json(self, _purpose, _prompt):
            self.calls += 1
            return DeepSeekResponse(
                data={"questions": []},
                finish_reason="stop",
                prompt_tokens=1,
                completion_tokens=1,
                elapsed_seconds=0.1,
                request_id=None,
            )

    client = FakeClient()
    ledger = CostLedger({**CONFIG, "budget_cap_cny": {"pilot": 10.0}})

    with pytest.raises(RepairExhausted):
        run_repair_loop(
            client=client,
            ledger=ledger,
            purpose="questions-batch-1",
            prompt="Generate five questions.",
            validate=lambda data: (
                data
                if data["questions"]
                else (_ for _ in ()).throw(ValueError("QUESTION_COUNT_MISMATCH"))
            ),
            max_repair_retries=3,
        )

    assert client.calls == 4


def test_model_discovery_selects_deepseek_v41_flash_alias_from_returned_list() -> None:
    models = [
        {"id": "deepseek-v4-pro", "object": "model"},
        {"id": "deepseek-flash", "object": "model"},
    ]

    assert select_v41_model_id(models) == "deepseek-flash"


def test_model_discovery_rejects_a_list_without_the_v41_alias() -> None:
    with pytest.raises(ValueError, match="DEEPSEEK_V41_MODEL_NOT_FOUND"):
        select_v41_model_id([{"id": "deepseek-v4-pro"}])


def test_split_pipeline_uses_passage_question_and_explanation_requests() -> None:
    schedule = load_pilot_schedule()["passages"][2]
    passage = (
        "Students read a short book about healthy food and daily exercise. "
        "The teacher asks them to explain one idea with a clear example."
    )
    questions = [
        {
            "stem": f"Question {index}",
            "options": ["A clear example.", "A new school.", "A long trip.", "A price list."],
            "answer": "A clear example.",
            "knowledge_points": [f"reading_point_{index}"],
            "grammar_tags": list(assignment["grammar_tags"]),
            "book_source": assignment["book_source"],
            "difficulty": assignment["difficulty"],
        }
        for index, assignment in enumerate(schedule["questions"], start=1)
    ]

    class FakeClient:
        config = {**CONFIG, "budget_cap_cny": {"pilot": 10.0}}

        def __init__(self) -> None:
            self.calls = []

        def chat_json(self, purpose, prompt):
            self.calls.append((purpose, prompt))
            if purpose.startswith("passage:"):
                data = {
                    "passage": passage,
                    "topic": schedule["topic"],
                    "book_source": schedule["book_source"],
                    "difficulty": schedule["difficulty"],
                }
            elif purpose.startswith("questions:"):
                data = {"questions": questions}
            elif purpose.startswith("explanations:"):
                data = {
                    "explanations": [
                        {
                            "question_index": index,
                            "explanation": (
                                "第一句说明答案依据。"
                                "第二句说明干扰项为何不合适。"
                                "第三句说明本题考点。"
                            ),
                        }
                        for index in range(1, 5)
                    ]
                }
            else:
                raise AssertionError(purpose)
            return DeepSeekResponse(
                data=data,
                finish_reason="stop",
                prompt_tokens=100,
                completion_tokens=50,
                elapsed_seconds=0.2,
                request_id=purpose,
            )

    client = FakeClient()
    ledger = CostLedger(client.config)
    result = generate_pilot_passage(
        client=client,
        ledger=ledger,
        schedule_passage=schedule,
    )

    assert result["type"] == "reading"
    assert result["passage_group_id"] == schedule["passage_group_id"]
    assert len(result["questions"]) == 4
    assert all(question["explanation"] for question in result["questions"])
    assert [purpose.split(":")[0] for purpose, _prompt in client.calls] == [
        "passage",
        "questions",
        "explanations",
    ]
