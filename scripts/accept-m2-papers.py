#!/usr/bin/env python3
"""Run ten M2 paper compositions through the real API."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app, store  # noqa: E402


client = TestClient(app, client=("127.0.0.1", 41000))
student_id = str(uuid.uuid4())
headers = {"X-Student-Id": student_id}


def start() -> dict:
    response = client.post(
        "/api/v1/practice/start",
        headers=headers,
        json={"duration_minutes": 30},
    )
    if response.status_code != 201:
        raise RuntimeError(f"START_FAILED:{response.status_code}:{response.text}")
    return response.json()


def finish(session: dict) -> dict:
    for item in session["items"]:
        question = store.questions[item["question_id"]]
        response = client.put(
            f"/api/v1/practice/{session['session_id']}/answer",
            headers=headers,
            json={
                "question_id": item["question_id"],
                "answer": question.answer,
                "client_revision": 0,
            },
        )
        if response.status_code != 204:
            raise RuntimeError(f"ANSWER_FAILED:{response.text}")
    response = client.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    if response.status_code != 200:
        raise RuntimeError(f"SUBMIT_FAILED:{response.status_code}:{response.text}")
    return response.json()


def compact_log(session: dict, report: dict) -> dict:
    log = session["composition_note"]["assembly_log"]
    reasons = Counter(
        reason
        for failure in log.get("hard_constraint_rejections", [])
        for reason in failure.get("reasons", [])
    )
    return {
        "session_id": session["session_id"],
        "question_count": len(session["items"]),
        "score": report["score"],
        "paper_mode": log["paper_mode"],
        "fallback_used": log.get("fallback_used", False),
        "fallback_reason": log.get("fallback_reason"),
        "book_quota_expected": log["book_quota_expected"],
        "book_quota_actual": log["book_quota_actual"],
        "difficulty_quota_expected": log["difficulty_quota_expected"],
        "difficulty_actual": log["difficulty_actual"],
        "grammar_tag_max": max(
            log["grammar_tag_counts"].values(),
            default=0,
        ),
        "topics": log["topics"],
        "selected_passage_groups": sorted(
            set(log["selected_passage_groups"])
        ),
        "hard_constraint_rejection_counts": dict(reasons),
        "valid_skeleton_count": log["valid_skeleton_count"],
        "selection_basis": log["selection_basis"],
        "selected_unseen_question_count": log[
            "selected_unseen_question_count"
        ],
        "selected_new_coverage_ratio": log["selected_new_coverage_ratio"],
        "coverage_witness": log.get("coverage_elimination_witness"),
    }


from collections import Counter  # noqa: E402


def main() -> None:
    if store.bank["name"] != "M2 Bank #2":
        raise RuntimeError(f"ACTIVE_BANK_NOT_M2:{store.bank['name']}")
    papers = []
    for _paper_number in range(10):
        session = start()
        report = finish(session)
        papers.append(compact_log(session, report))

    first = start()
    second = start()
    first_groups = {
        item["passage_group_id"] for item in first["items"]
    }
    second_groups = {
        item["passage_group_id"] for item in second["items"]
    }
    overlap = first_groups & second_groups
    pair_overlap_checks = [
        {
            "pair": 1,
            "first_session": first["session_id"],
            "second_session": second["session_id"],
            "passage_overlap": sorted(overlap),
            "passage_mutex_ok": not overlap,
        }
    ]
    for session in (first, second):
        response = client.delete(
            f"/api/v1/practice/{session['session_id']}",
            headers=headers,
        )
        if response.status_code != 204:
            raise RuntimeError(f"DELETE_FAILED:{response.text}")
    result = {
        "student_id": student_id,
        "paper_count": len(papers),
        "papers": papers,
        "pair_overlap_checks": pair_overlap_checks,
        "all_scores_100": all(item["score"] == 100.0 for item in papers),
        "all_tag_caps_ok": all(
            item["grammar_tag_max"] <= 3 for item in papers
        ),
        "all_passages_exclusive": all(
            item["passage_mutex_ok"] for item in pair_overlap_checks
        ),
        "fallback_paper_count": sum(
            item["fallback_used"] for item in papers
        ),
    }
    output = ROOT / "qa" / "evidence" / "m2" / "composition-10-papers.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if len(papers) != 10 or not result["all_scores_100"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
