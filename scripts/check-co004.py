"""End-to-end checks for CO-004 against the running local API."""

from __future__ import annotations

import json
import re
import uuid

import httpx


BASE = "http://127.0.0.1:8000/api/v1"
CHINESE = re.compile(r"[\u4e00-\u9fff]")
ENGLISH_PARAGRAPH = re.compile(r"\b[A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){5,}\b")


def main() -> None:
    student_id = str(uuid.uuid4())
    headers = {"X-Student-Id": student_id}
    with httpx.Client(timeout=20) as client:
        started = client.post(
            f"{BASE}/practice/start",
            headers=headers,
            json={"duration_minutes": 30},
        )
        started.raise_for_status()
        session = started.json()
        serialized = json.dumps(session)
        items = session["items"]

        group_order = []
        for item in items:
            if not group_order or group_order[-1] != item["passage_group_id"]:
                group_order.append(item["passage_group_id"])

        grammar = [item for item in items if item["type"] == "grammar_fill"]
        group_ranges = []
        for group_id in group_order:
            positions = [
                index
                for index, item in enumerate(items)
                if item["passage_group_id"] == group_id
            ]
            assert positions == list(range(positions[0], positions[-1] + 1))
            group_ranges.append(
                {
                    "passage_group_id": group_id,
                    "first": positions[0] + 1,
                    "last": positions[-1] + 1,
                    "questions": len(positions),
                }
            )

        submitted = client.post(
            f"{BASE}/practice/{session['session_id']}/submit",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        submitted.raise_for_status()
        report = submitted.json()

        review = client.get(
            f"{BASE}/practice/{session['session_id']}/review",
            headers=headers,
        )
        review.raise_for_status()
        review_items = review.json()["items"]

        explanations = [item["explanation"] for item in report["question_results"]]
        result = {
            "session_id": session["session_id"],
            "question_count": len(items),
            "passage_groups": len(group_order),
            "group_ranges": group_ranges,
            "all_questions_have_options": all(item["options"] for item in items),
            "grammar_question_count": len(grammar),
            "grammar_options_all_four": all(len(item["options"]) == 4 for item in grammar),
            "pre_submit_has_answer": '"answer"' in serialized,
            "pre_submit_has_explanation": '"explanation"' in serialized,
            "report_explanations": len(explanations),
            "report_explanations_with_chinese": sum(
                bool(CHINESE.search(value)) for value in explanations
            ),
            "report_english_paragraphs": sum(
                bool(ENGLISH_PARAGRAPH.search(value)) for value in explanations
            ),
            "review_items": len(review_items),
            "review_contains_explanation": "explanation" in json.dumps(review.json()),
        }
        assert result["question_count"] == 30
        assert result["passage_groups"] == 3
        assert result["all_questions_have_options"]
        assert result["grammar_question_count"] == 10
        assert result["grammar_options_all_four"]
        assert not result["pre_submit_has_answer"]
        assert not result["pre_submit_has_explanation"]
        assert result["report_explanations_with_chinese"] == 30
        assert result["report_english_paragraphs"] == 0
        assert result["review_items"] == 30
        assert not result["review_contains_explanation"]
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
