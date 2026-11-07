from __future__ import annotations

import json

import httpx

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
            ]
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
    monkeypatch.setattr(analysis.httpx, "post", lambda *args, **kwargs: _Response())

    result = analysis.generate_weakness_analysis([_question_result()], _weak_points())

    assert result["source"] == "llm"
    assert "建议：" in result["text"]
    assert "重做一组同类题" in result["text"]
    assert len(result["text"]) <= 100


def test_http_failure_uses_rule_fallback(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)

    def fail(*args, **kwargs):
        raise httpx.ConnectError("forced failure")

    monkeypatch.setattr(analysis.httpx, "post", fail)

    result = analysis.generate_weakness_analysis([_question_result()], _weak_points())

    assert result["source"] == "fallback"
    assert "一般现在时被动语态" in result["text"]
    assert "先回看错题依据" in result["text"]
    assert len(result["text"]) <= 100


def test_score_wording_names_total_and_correct_count(monkeypatch) -> None:
    monkeypatch.delenv("WEAKNESS_ANALYSIS_DISABLED", raising=False)
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
