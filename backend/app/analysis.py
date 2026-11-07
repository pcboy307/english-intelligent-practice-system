from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
REPORTING_CONFIG = json.loads(
    (ROOT / "config" / "reporting.json").read_text(encoding="utf-8")
)
KNOWLEDGE_POINT_LABELS = REPORTING_CONFIG["weakness_analysis"][
    "knowledge_point_labels"
]


def humanize_knowledge_point(point: str) -> str:
    if point in KNOWLEDGE_POINT_LABELS:
        return KNOWLEDGE_POINT_LABELS[point]
    if "_" not in point:
        return point
    if point.startswith("reading_"):
        return "阅读理解能力"
    if point.startswith("gap_fill_"):
        return "七选五语篇衔接"
    if point.endswith("_noun"):
        return "名词词义与搭配辨析"
    if point.endswith("_verb"):
        return "动词词义与固定搭配辨析"
    if point.endswith("_adjective"):
        return "形容词词义辨析"
    if point.endswith("_adverb"):
        return "副词辨析"
    return "英语基础知识运用"


def _limit(text: str, maximum: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip().strip('"“”')
    if len(cleaned) <= maximum:
        if cleaned.endswith(("。", "！", "？", "；")):
            return cleaned
        return cleaned[: maximum - 1].rstrip("，、；：,. ") + "。"
    prefix = cleaned[: maximum - 1]
    punctuation_positions = [
        prefix.rfind(mark) for mark in ("。", "！", "？", "；")
    ]
    cut = max(punctuation_positions)
    if cut >= int(maximum * 0.6):
        return prefix[: cut + 1]
    return prefix.rstrip("，、；：,. ") + "。"


def _fallback(weak_points: list[dict], maximum: int) -> str:
    names = [
        humanize_knowledge_point(item["knowledge_point"])
        for item in weak_points[:2]
    ]
    focus = "、".join(names) if names else "本套暴露的基础知识"
    return _limit(
        f"你这次主要卡在{focus}。先回看错题依据，再用同类题做三次即时复述，"
        "确认能说出为什么再继续下一组，稳住节奏就会进步。",
        maximum,
    )


def _ensure_explicit_action(text: str, maximum: int) -> str:
    if "建议：" in text:
        return _limit(text, maximum)
    action = "建议：今天重做一组同类题并复述错因。"
    if len(action) >= maximum:
        return _limit(action, maximum)
    prefix = _limit(text, maximum - len(action))
    return prefix + action


def _normalize_score_phrase(text: str, total: int, correct: int) -> str:
    return re.sub(
        r"你?已?全答对\s*\d+\s*题",
        f"{total} 题中答对 {correct} 题",
        text,
    )


def _replace_internal_knowledge_points(text: str, points: list[str]) -> str:
    for point in sorted(set(points), key=len, reverse=True):
        text = text.replace(point, humanize_knowledge_point(point))
    return text


def humanize_analysis_text(text: str) -> str:
    return _replace_internal_knowledge_points(
        text,
        list(KNOWLEDGE_POINT_LABELS),
    )


def generate_weakness_analysis(
    question_results: list[dict],
    weak_points: list[dict],
) -> dict:
    config = REPORTING_CONFIG["weakness_analysis"]
    maximum = int(config["max_chars"])
    fallback = _fallback(weak_points, maximum)
    if not config["enabled"] or os.getenv("WEAKNESS_ANALYSIS_DISABLED") == "1":
        return {"text": fallback, "source": "fallback"}

    wrong_samples = []
    selected_keys = set()
    for item in question_results:
        if item["correct"]:
            continue
        sample_key = (
            item.get("knowledge_points", ["unknown"])[0],
            item.get("type", "unknown"),
        )
        if sample_key in selected_keys:
            continue
        selected_keys.add(sample_key)
        wrong_samples.append(
            {
                "题目": item.get("stem", ""),
                "选项": item.get("options", []),
                "我的答案": item.get("user_answer", ""),
                "正确答案": item.get("correct_answer", ""),
                "知识点": [
                    humanize_knowledge_point(point)
                    for point in item.get("knowledge_points", [])
                ],
            }
        )
        if len(wrong_samples) >= int(config["max_wrong_samples"]):
            break

    answered_count = sum(
        1 for item in question_results if str(item.get("user_answer", "")).strip()
    )
    correct_count = sum(1 for item in question_results if item["correct"])
    prompt_data = {
        "题目数": len(question_results),
        "已答题数": answered_count,
        "未答题数": len(question_results) - answered_count,
        "答对题数": correct_count,
        "薄弱知识点": [
            {
                **item,
                "knowledge_point": humanize_knowledge_point(
                    item["knowledge_point"]
                ),
            }
            for item in weak_points
        ],
        "典型错题": wrong_samples,
    }
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位温和、专业的高中英语老师。只输出一段70至90个汉字的中文分析，"
                    "不要标题、列表或空泛鼓励。必须点出两个最需巩固的知识点，"
                    "说明典型错因，并以“建议：”开头给出今天就能执行的具体练习动作。"
                    "若提及答题数，只能写“共N题，答对M题”，禁止写“全答对N题”。"
                    "若未答题数超过10，应优先指出限时完成和选择策略问题，"
                    "不要把未作答误判为知识遗忘。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_data, ensure_ascii=False),
            },
        ],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        response = httpx.post(
            config["endpoint"],
            json=payload,
            timeout=float(config["timeout_seconds"]),
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"].get("content") or ""
        content = _normalize_score_phrase(
            content,
            len(question_results),
            correct_count,
        )
        content = _replace_internal_knowledge_points(
            content,
            [
                point
                for item in question_results
                for point in item.get("knowledge_points", [])
            ]
            + [item["knowledge_point"] for item in weak_points],
        )
        text = _limit(content, maximum)
        if not re.search(r"[\u4e00-\u9fff]", text):
            raise ValueError("LLM_ANALYSIS_EMPTY")
        text = _ensure_explicit_action(text, maximum)
        return {"text": text, "source": "llm"}
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return {"text": fallback, "source": "fallback"}
