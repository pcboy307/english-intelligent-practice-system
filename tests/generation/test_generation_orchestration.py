from __future__ import annotations

import pytest
import httpx

from backend.app.generation import (
    GenerationClient,
    GenerationExhausted,
    TokenBudgetExceeded,
    generate_validated_passage,
    parse_model_response,
)


BASE_WORDS = (
    "Students read a short book about healthy food and daily exercise. "
    "The teacher asks them to explain one idea with a clear example. "
)


def valid_reading() -> dict:
    return {
        "type": "reading",
        "passage_group_id": "M2-PILOT-READING-01",
        "topic": "运动与健康",
        "book_source": "选必二 U3",
        "difficulty": 3,
        "passage": BASE_WORDS,
        "questions": [
            {
                "stem": f"What is the main idea of sentence {index}?",
                "options": ["A clear example.", "A new school.", "A long trip.", "A price list."],
                "answer": "A clear example.",
                "explanation": "The text names a clear example. The other choices are absent. This tests detail reading.",
                "knowledge_points": [f"reading_detail_{index}"],
                "grammar_tags": [tag],
                "book_source": "选必二 U3",
                "difficulty": 3,
            }
            for index, tag in enumerate(
                [
                    "tense_system",
                    "noun_clauses",
                    "passive_voice_tenses",
                    "word_formation",
                ],
                start=1,
            )
        ],
    }


def test_model_response_parses_json_fence_and_usage() -> None:
    record, prompt_tokens, completion_tokens = parse_model_response(
        {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"type": "reading", "questions": []}\n```'
                    }
                }
            ],
            "usage": {"prompt_tokens": 123, "completion_tokens": 456},
        }
    )

    assert record == {"type": "reading", "questions": []}
    assert prompt_tokens == 123
    assert completion_tokens == 456


def test_generation_retries_after_gate_failure_and_records_attempt_cost() -> None:
    calls = []

    def generator(_attempt, failures):
        calls.append([failure["category"] for failure in failures])
        if len(calls) == 1:
            invalid = valid_reading()
            invalid["questions"] = invalid["questions"][:3]
            return invalid, 100, 200, 1.5
        return valid_reading(), 120, 220, 1.7

    result = generate_validated_passage(
        "reading",
        generator,
        max_retries=3,
    )

    assert result.record["passage_group_id"] == "M2-PILOT-READING-01"
    assert len(result.attempts) == 2
    assert result.attempts[0]["accepted"] is False
    assert "question_count" in {item["category"] for item in result.attempts[0]["failures"]}
    assert result.attempts[1]["accepted"] is True
    assert result.metrics == {
        "prompt_tokens": 220,
        "completion_tokens": 420,
        "total_tokens": 640,
        "elapsed_seconds": 3.2,
        "failed_retries": 1,
    }
    assert calls == [[], ["question_count"]]


def test_generation_stops_after_three_failed_retries() -> None:
    calls = 0

    def generator(_attempt, _failures):
        nonlocal calls
        calls += 1
        invalid = valid_reading()
        invalid["questions"] = []
        return invalid, 10, 20, 0.2

    with pytest.raises(GenerationExhausted) as raised:
        generate_validated_passage(
            "reading",
            generator,
            max_retries=3,
        )

    assert calls == 4
    assert raised.value.attempts[-1]["accepted"] is False
    assert raised.value.metrics["failed_retries"] == 3


def test_generation_client_requests_json_and_disables_model_thinking() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"type": "reading", "questions": []}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    client = GenerationClient(
        {
            "endpoint": "http://127.0.0.1:11435/v1/chat/completions",
            "model": "qwen-local",
            "temperature": 0.2,
            "timeout_seconds": 10,
            "max_tokens": {"cloze": 6000, "grammar_fill": 5000, "reading": 3500, "gap_fill": 4000},
        },
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    record, prompt_tokens, completion_tokens, elapsed = client.generate(
        "reading",
        "Generate one passage.",
    )

    assert record == {"type": "reading", "questions": []}
    assert (prompt_tokens, completion_tokens) == (20, 10)
    assert elapsed >= 0
    assert captured["payload"]["model"] == "qwen-local"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }
    assert captured["payload"]["max_tokens"] == 3500


def test_generation_stops_immediately_when_token_cap_is_crossed() -> None:
    calls = 0

    def generator(_attempt, _failures):
        nonlocal calls
        calls += 1
        invalid = valid_reading()
        invalid["questions"] = []
        return invalid, 60000, 1000, 1.0

    with pytest.raises(TokenBudgetExceeded):
        generate_validated_passage(
            "reading",
            generator,
            max_retries=3,
            token_cap=100000,
        )

    assert calls == 2
