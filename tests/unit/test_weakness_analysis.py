from __future__ import annotations

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
