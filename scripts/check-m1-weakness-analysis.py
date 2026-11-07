#!/usr/bin/env python3
"""Exercise graded questions against the live local LLM analysis adapter."""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app, store


OUTPUT = ROOT / "qa" / "evidence" / "m1" / "weakness-analysis.json"


def wrong_answer(question) -> str:
    if not question.options:
        return "wrong"
    for option in question.options:
        if option.casefold() != str(question.answer).casefold():
            return option
    raise AssertionError("QUESTION_HAS_NO_WRONG_OPTION")


def main() -> None:
    client = TestClient(app, client=("127.0.0.1", 43000))
    headers = {"X-Student-Id": str(uuid.uuid4())}
    started = client.post(
        "/api/v1/practice/start",
        headers=headers,
        json={"duration_minutes": 30},
    )
    started.raise_for_status()
    session = started.json()
    wrong_ids = {
        item["question_id"]
        for item in session["items"]
        if item["type"] in {"grammar_fill", "reading"}
    }
    wrong_ids = set(sorted(wrong_ids)[:6])
    for item in session["items"]:
        question = store.questions[item["question_id"]]
        answer = (
            wrong_answer(question)
            if item["question_id"] in wrong_ids
            else str(question.answer)
        )
        answered = client.put(
            f"/api/v1/practice/{session['session_id']}/answer",
            headers=headers,
            json={
                "question_id": item["question_id"],
                "answer": answer,
                "client_revision": 0,
            },
        )
        if answered.status_code != 204:
            raise RuntimeError(
                f"ANSWER_FAILED: {answered.status_code} {answered.text}"
            )

    submitted = client.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        timeout=90,
    )
    if submitted.status_code != 200:
        raise RuntimeError(
            f"SUBMIT_FAILED: {submitted.status_code} {submitted.text}"
        )
    report = submitted.json()
    analysis = report["weakness_analysis"]
    result = {
        "session_id": session["session_id"],
        "question_count": report["question_count"],
        "report_title": report["report_title"],
        "wrong_question_ids": sorted(wrong_ids),
        "weakness_analysis_source": report["weakness_analysis_source"],
        "weakness_analysis": analysis,
        "analysis_length": len(analysis),
        "contains_chinese": bool(re.search(r"[\u4e00-\u9fff]", analysis)),
        "at_most_100_chars": len(analysis) <= 100,
        "question_results_have_stem_and_options": all(
            item["stem"] and item["options"] for item in report["question_results"]
        ),
        "passes": (
            report["weakness_analysis_source"] == "llm"
            and bool(re.search(r"[\u4e00-\u9fff]", analysis))
            and len(analysis) <= 100
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passes"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
