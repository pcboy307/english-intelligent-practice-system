from __future__ import annotations

import json

import httpx
import pytest

from backend.app import analysis


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "薄弱点在于现在完成时和一般现在时被动语态，"
                            "错因是把动作时间与被动词关系判断错了。"
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
        }


class _ScoreResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "你已全答对 23 题，薄弱点在于现在完成时和被动语态，"
                            "错因是忽略动作时间。建议：今天重做同类题并复述错因。"
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
        }


class _LongResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "建议：先复习现在完成时和一般现在时被动语态。"
                            "你需要逐题标记时间状语、主语与谓语关系，再对比正确选项和干扰项。"
                            "完成十道同类题后，用三分钟复述每道题为什么这样判断。"
                            "如果仍然出错，就把错题按时态、语态和句子结构分类，"
                            "每天选两组重新作答，并记录第二次判断依据是否更清楚。"
                            "坚持把判断过程说出来，比只记答案更能稳定提升。"
                        )
                    }
                }
            ]
        }


def _question_result() -> dict:
    return {
        "correct": False,
        "stem": "The box ___ every Friday.",
        "options": ["checks", "is checked", "checked", "checking"],
        "user_answer": "checks",
        "correct_answer": "is checked",
        "knowledge_points": ["一般现在时被动语态"],
        "type": "grammar_fill",
    }


def _weak_points() -> list[dict]:
    return [
        {"knowledge_point": "一般现在时被动语态"},
        {"knowledge_point": "现在完成时"},
    ]


def test_llm_text_without_action_gets_explicit_action(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    monkeypatch.setattr(
        analysis,
        "GENERATION_MODEL_CONFIG",
        {**analysis.GENERATION_MODEL_CONFIG, "model_id": "deepseek-flash"},
    )
    monkeypatch.setattr(analysis.httpx, "post", lambda *args, **kwargs: _Response())

    result = analysis.generate_weakness_analysis([_question_result()], _weak_points())

    assert result["source"] == "llm"
    assert "建议：" in result["text"]
    assert "重做一组同类题" in result["text"]
    assert len(result["text"]) <= 300


def test_http_failure_uses_rule_fallback(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    monkeypatch.setattr(
        analysis,
        "GENERATION_MODEL_CONFIG",
        {**analysis.GENERATION_MODEL_CONFIG, "model_id": "deepseek-flash"},
    )

    def fail(*args, **kwargs):
        raise httpx.ConnectError("forced failure")

    monkeypatch.setattr(analysis.httpx, "post", fail)

    result = analysis.generate_weakness_analysis([_question_result()], _weak_points())

    assert result["source"] == "fallback"
    assert "一般现在时被动语态" in result["text"]
    assert "先回看错题依据" in result["text"]
    assert len(result["text"]) <= 300


def test_score_wording_names_total_and_correct_count(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    monkeypatch.setattr(
        analysis,
        "GENERATION_MODEL_CONFIG",
        {**analysis.GENERATION_MODEL_CONFIG, "model_id": "deepseek-flash"},
    )
    monkeypatch.setattr(analysis.httpx, "post", lambda *args, **kwargs: _ScoreResponse())
    results = [_question_result() for _ in range(6)]
    results.extend(
        {**_question_result(), "correct": True, "user_answer": "is checked"}
        for _ in range(23)
    )

    result = analysis.generate_weakness_analysis(results, _weak_points())

    assert "全答对" not in result["text"]
    assert "29 题中答对 23 题" in result["text"]


def test_internal_knowledge_point_ids_are_not_sent_to_llm(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    monkeypatch.setattr(
        analysis,
        "GENERATION_MODEL_CONFIG",
        {**analysis.GENERATION_MODEL_CONFIG, "model_id": "deepseek-flash"},
    )
    captured: dict = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(analysis.httpx, "post", fake_post)
    question = {
        **_question_result(),
        "knowledge_points": ["team_noun", "material_noun"],
    }

    analysis.generate_weakness_analysis(
        [question],
        [
            {"knowledge_point": "team_noun"},
            {"knowledge_point": "material_noun"},
        ],
    )

    prompt = json.dumps(captured["json"], ensure_ascii=False)
    assert "team_noun" not in prompt
    assert "material_noun" not in prompt
    assert "名词词义辨析（团队）" in prompt
    assert "名词词义辨析（材料）" in prompt


def test_weakness_analysis_calls_deepseek_with_environment_key(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    monkeypatch.setattr(
        analysis,
        "GENERATION_MODEL_CONFIG",
        {**analysis.GENERATION_MODEL_CONFIG, "model_id": "deepseek-flash"},
    )
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(analysis.httpx, "post", fake_post)

    result = analysis.generate_weakness_analysis([_question_result()], _weak_points())

    assert result["source"] == "llm"
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["json"]["model"] == "deepseek-flash"
    assert "qwen" not in json.dumps(captured["json"], ensure_ascii=False).lower()
    assert result["provider"] == "deepseek"
    assert result["usage"] == {"prompt_tokens": 1000, "completion_tokens": 200}
    assert result["cost_cny"] == pytest.approx(0.0036)


def test_qwen_remains_available_as_a_comparison_provider(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(analysis.httpx, "post", fake_post)

    result = analysis.generate_weakness_analysis(
        [_question_result()],
        _weak_points(),
        provider_override="qwen",
    )

    assert result["source"] == "llm"
    assert result["provider"] == "qwen"
    assert result["cost_cny"] == 0.0
    assert captured["url"] == "http://127.0.0.1:11435/v1/chat/completions"
    assert "headers" not in captured


def test_fallback_uses_natural_knowledge_point_labels(monkeypatch) -> None:
    monkeypatch.setenv("WEAKNESS_ANALYSIS_DISABLED", "1")

    result = analysis.generate_weakness_analysis(
        [_question_result()],
        [
            {"knowledge_point": "team_noun"},
            {"knowledge_point": "material_noun"},
        ],
    )

    assert result["source"] == "fallback"
    assert "team_noun" not in result["text"]
    assert "material_noun" not in result["text"]
    assert "名词词义辨析（团队）" in result["text"]
    assert "名词词义辨析（材料）" in result["text"]


def test_stored_analysis_text_is_humanized_on_read() -> None:
    result = analysis.humanize_analysis_text(
        "薄弱点是 team_noun、material_noun 和 manner_adverb。"
    )

    assert "team_noun" not in result
    assert "material_noun" not in result
    assert "manner_adverb" not in result
    assert "名词词义辨析（团队）" in result
    assert "名词词义辨析（材料）" in result
    assert "方式副词辨析" in result


def test_analysis_allows_more_than_100_characters_up_to_300(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
    monkeypatch.setattr(analysis.httpx, "post", lambda *args, **kwargs: _LongResponse())

    result = analysis.generate_weakness_analysis(
        [_question_result()],
        _weak_points(),
        provider_override="qwen",
    )

    assert 100 < len(result["text"]) <= 300
