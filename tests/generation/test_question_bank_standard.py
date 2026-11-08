from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STANDARD = ROOT / "docs" / "question-bank-generation-standard-v2.md"


def test_question_bank_standard_freezes_the_adjudicated_contract() -> None:
    assert STANDARD.exists()
    text = STANDARD.read_text(encoding="utf-8")

    required_phrases = [
        '"format_version": "bank-v1"',
        '"format_version": "m26-v1"',
        "72 篇 / 500 题",
        "225",
        "150",
        "100",
        "25",
        "280–320",
        "220–260",
        "350–420",
        "320–380",
        "①–⑩",
        "(1)–(15)",
        "整篇正文内的出现次数必须为 0",
        "一次只生成一篇",
        "可解性",
        "Pro/人工门禁",
        "stored",
        "导出题库评审模式",
        "必修1 U1",
        "选必一 U1",
        "选必二 U1",
        "跨册综合",
        "question.number",
        "gap_fill",
        "answer",
        "cloze_tier",
    ]
    for phrase in required_phrases:
        assert phrase in text, phrase

    assert "不得直接出现在该空附近" not in text
    assert "schema_version" not in text
    assert "M2.6 推荐范围" not in text


def test_legacy_multi_file_prompt_is_not_the_active_standard() -> None:
    old = ROOT / "docs" / "llm-question-bank-single-file-prompt.md"
    assert not old.exists()
