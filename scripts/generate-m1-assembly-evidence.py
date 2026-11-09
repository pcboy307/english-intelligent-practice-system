#!/usr/bin/env python3
"""Generate four real Demo Bank assembly logs and the M1 rule decision table."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("WEAKNESS_ANALYSIS_DISABLED", "1")

from fastapi.testclient import TestClient

from backend.app.main import app, store


OUTPUT_DIR = ROOT / "qa" / "evidence" / "m1"
STUDENT_HEADERS = {"X-Student-Id": str(uuid.uuid4())}
CLIENT = TestClient(app, client=("127.0.0.1", 42000))


def start_practice() -> dict:
    response = CLIENT.post(
        "/api/v1/practice/start",
        headers=STUDENT_HEADERS,
        json={"duration_minutes": 30},
    )
    if response.status_code != 201:
        raise RuntimeError(f"START_FAILED: {response.status_code} {response.text}")
    return response.json()


def answer_all_correct(session: dict) -> None:
    for item in session["items"]:
        response = CLIENT.put(
            f"/api/v1/practice/{session['session_id']}/answer",
            headers=STUDENT_HEADERS,
            json={
                "question_id": item["question_id"],
                "answer": store.questions[item["question_id"]].answer,
                "client_revision": 0,
            },
        )
        if response.status_code != 204:
            raise RuntimeError(
                f"ANSWER_FAILED: {response.status_code} {response.text}"
            )


def submit(session: dict) -> dict:
    response = CLIENT.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**STUDENT_HEADERS, "Idempotency-Key": str(uuid.uuid4())},
    )
    if response.status_code != 200:
        raise RuntimeError(f"SUBMIT_FAILED: {response.status_code} {response.text}")
    return response.json()


def write_json(name: str, payload: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    expected_sizes = [29, 30, 29, 30]
    logs = []
    reports = []
    for paper_number, expected_size in enumerate(expected_sizes, start=1):
        session = start_practice()
        if len(session["items"]) != expected_size:
            raise RuntimeError(
                f"PAPER_SIZE_FAILED: expected={expected_size} "
                f"actual={len(session['items'])}"
            )
        log = session["composition_note"]["assembly_log"]
        write_json(f"assembly-{paper_number:02d}.json", log)
        logs.append(log)
        answer_all_correct(session)
        report = submit(session)
        reports.append(
            {
                "paper_number": paper_number,
                "session_id": session["session_id"],
                "report_title": report["report_title"],
                "question_count": report["question_count"],
                "score": report["score"],
                "weakness_analysis_source": report["weakness_analysis_source"],
            }
        )

    concurrent_headers = {"X-Student-Id": str(uuid.uuid4())}
    concurrent_sessions = []
    for _ in range(2):
        response = CLIENT.post(
            "/api/v1/practice/start",
            headers=concurrent_headers,
            json={"duration_minutes": 30},
        )
        if response.status_code != 201:
            raise RuntimeError(
                f"CONCURRENT_START_FAILED: {response.status_code} {response.text}"
            )
        concurrent_sessions.append(response.json())
    concurrent_groups = [
        {item["passage_group_id"] for item in session["items"]}
        for session in concurrent_sessions
    ]
    active_intersection = sorted(concurrent_groups[0] & concurrent_groups[1])
    for session in concurrent_sessions:
        CLIENT.delete(
            f"/api/v1/practice/{session['session_id']}",
            headers=concurrent_headers,
        )

    historical_shared_passages = {
        group_id
        for group_id in {
            item["passage_group_id"] for log in logs for item in log["question_coverage"]
        }
        if sum(
            group_id
            in {
                item["passage_group_id"] for item in log["question_coverage"]
            }
            for log in logs
        )
        > 1
    }
    decisions = {
        "grammar_tag_repetition_lte_3": {
            "passed": all(
                max(log["grammar_tag_counts"].values(), default=0) <= 3
                for log in logs
            ),
            "actual": [
                max(log["grammar_tag_counts"].values(), default=0)
                for log in logs
            ],
            "expected": "every paper <= 3",
        },
        "book_quota": {
            "passed": all(
                log["book_quota_actual"] == log["book_quota_expected"]
                for log in logs
            ),
            "actual": [log["book_quota_actual"] for log in logs],
            "expected": [log["book_quota_expected"] for log in logs],
        },
        "difficulty_distribution_40_40_20": {
            "passed": all(
                log["difficulty_actual"] == log["difficulty_quota_expected"]
                for log in logs
            ),
            "actual": [log["difficulty_actual"] for log in logs],
            "expected": [log["difficulty_quota_expected"] for log in logs],
            "note": (
                "The 40/40/20 percentages are converted with largest remainder "
                "for each actual paper size: 29 -> 12/11/6, 30 -> 12/12/6."
            ),
        },
        "coverage_priority": {
            "passed": all(
                log["selection_basis"] == "coverage"
                for log in logs
            ),
            "actual": [
                {
                    "selected_unseen_question_count": log[
                        "selected_unseen_question_count"
                    ],
                    "selected_new_coverage_ratio": log[
                        "selected_new_coverage_ratio"
                    ],
                }
                for log in logs
            ],
            "expected": "hard-valid candidates are ranked by unseen questions first",
        },
        "same_passage_not_in_two_active_sessions": {
            "passed": not active_intersection,
            "actual_intersection": active_intersection,
            "first_session_groups": sorted(concurrent_groups[0]),
            "second_session_groups": sorted(concurrent_groups[1]),
            "expected": "zero shared passages while both sessions are unfinished",
            "historical_completed_reuse": sorted(historical_shared_passages),
            "note": (
                "11 篇 < 4 套×3 篇，复用不可避免，故按并发维度约束"
            ),
        },
    }
    write_json(
        "four-rule-decisions.json",
        {
            "papers": reports,
            "rules": decisions,
            "passes": all(rule["passed"] for rule in decisions.values()),
        },
    )
    print(
        json.dumps(
            {
                "student_id": STUDENT_HEADERS["X-Student-Id"],
                "paper_sizes": [log["question_count"] for log in logs],
                "paper_labels": [log["paper_label"] for log in logs],
                "rules": decisions,
                "passes": all(rule["passed"] for rule in decisions.values()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not all(rule["passed"] for rule in decisions.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
