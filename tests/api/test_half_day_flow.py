from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("WEAKNESS_ANALYSIS_DISABLED", "1")

from backend.app.main import app, store


client = TestClient(app, client=("127.0.0.1", 41000))


def student_headers() -> dict[str, str]:
    return {"X-Student-Id": str(uuid.uuid4())}


def start_practice(headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/practice/start",
        headers=headers,
        json={"duration_minutes": 30},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_30_question_start_has_no_answers() -> None:
    headers = student_headers()
    bank = client.get("/api/v1/bank/active", headers=headers)
    assert bank.status_code == 200
    assert bank.json() == {
        "bank_id": store.bank["bank_id"],
        "name": "Demo Bank",
        "status": "active",
    }
    session = start_practice(headers)
    assert len(session["items"]) == 30
    assert session["bank_name"] == "Demo Bank"
    serialized = json.dumps(session)
    assert '"answer"' not in serialized
    assert '"explanation"' not in serialized
    assert {item["type"] for item in session["items"]} == {
        "cloze",
        "grammar_fill",
        "gap_fill",
    }
    assert all(item["options"] for item in session["items"])
    grammar_items = [item for item in session["items"] if item["type"] == "grammar_fill"]
    assert len(grammar_items) == 10
    assert all(len(item["options"] or []) == 4 for item in grammar_items)
    assert 120 <= len(grammar_items[0]["passage"].split()) <= 180
    assert all(label in grammar_items[0]["passage"] for label in "①②③④⑤⑥⑦⑧⑨⑩")
    group_order = [item["passage_group_id"] for item in session["items"]]
    assert len(list(dict.fromkeys(group_order))) == 3
    for group_id in dict.fromkeys(group_order):
        positions = [index for index, value in enumerate(group_order) if value == group_id]
        assert positions == list(range(positions[0], positions[-1] + 1))


def test_submit_returns_report_and_is_idempotent() -> None:
    headers = student_headers()
    session = start_practice(headers)
    for item in session["items"]:
        correct = store.questions[item["question_id"]].answer
        response = client.put(
            f"/api/v1/practice/{session['session_id']}/answer",
            headers=headers,
            json={"question_id": item["question_id"], "answer": correct, "client_revision": 0},
        )
        assert response.status_code == 204, response.text

    key = str(uuid.uuid4())
    first = client.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**headers, "Idempotency-Key": key},
    )
    second = client.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**headers, "Idempotency-Key": key},
    )
    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    report = first.json()
    assert report["score"] == 100.0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-30题-100\.00分", report["report_title"])
    assert report["bank_name"] == "Demo Bank"
    assert report["question_count"] == 30
    assert len(report["weakness_analysis"]) <= 100
    assert len(report["type_scores"]) == 3
    assert report["weak_points"]
    assert report["suggestions"]
    assert len(report["question_results"]) == 30
    assert all(item["stem"] and item["options"] for item in report["question_results"])
    assert all(
        item["explanation"].strip() and item["explanation"].strip() != "暂无解析"
        for item in report["question_results"]
    )
    assert all(
        re.search(r"[\u4e00-\u9fff]", item["explanation"])
        for item in report["question_results"]
    )
    store.sessions.clear()
    persisted = client.get(f"/api/v1/reports/{session['session_id']}", headers=headers)
    assert persisted.status_code == 200
    assert persisted.json() == report
    review = client.get(
        f"/api/v1/practice/{session['session_id']}/review",
        headers=headers,
    )
    assert review.status_code == 200
    assert len(review.json()["items"]) == 30
    assert all("explanation" not in item for item in review.json()["items"])


def test_review_is_blocked_before_submit() -> None:
    headers = student_headers()
    session = start_practice(headers)
    response = client.get(
        f"/api/v1/practice/{session['session_id']}/review",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SESSION_NOT_SUBMITTED"


def test_history_report_can_be_listed_opened_and_deleted() -> None:
    headers = student_headers()
    session = start_practice(headers)
    report = client.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert report.status_code == 200

    history = client.get("/api/v1/reports", headers=headers)
    assert history.status_code == 200
    listed = next(
        item
        for item in history.json()
        if item["session_id"] == session["session_id"]
    )
    assert listed["report_title"] == report.json()["report_title"]
    assert listed["question_count"] == 30

    deleted = client.delete(
        f"/api/v1/reports/{session['session_id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/reports/{session['session_id']}",
        headers=headers,
    ).status_code == 404
    assert client.get(
        f"/api/v1/practice/{session['session_id']}",
        headers=headers,
    ).status_code == 404
    with store.connection() as connection:
        for table, id_column in (
            ("practice_reports", "session_id"),
            ("saved_answers", "session_id"),
            ("session_items", "session_id"),
            ("practice_sessions", "id"),
        ):
            count = connection.execute(
                f"SELECT count(*) AS count FROM {table} WHERE {id_column}=%s",
                (session["session_id"],),
            ).fetchone()["count"]
            assert count == 0


def test_wrong_answer_is_tagged_and_two_different_sessions_clear_it() -> None:
    headers = student_headers()
    first = start_practice(headers)
    target = first["items"][0]["question_id"]
    question = store.questions[target]
    wrong = question.options[0] if question.options else "wrong"
    if wrong.casefold() == str(question.answer).casefold():
        wrong = question.options[1] if question.options else "wrong-2"
    client.put(
        f"/api/v1/practice/{first['session_id']}/answer",
        headers=headers,
        json={"question_id": target, "answer": wrong, "client_revision": 0},
    )
    client.post(
        f"/api/v1/practice/{first['session_id']}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    tags = client.get("/api/v1/error-tags", headers=headers).json()
    tag = next(item for item in tags if item["question_id"] == target)
    assert tag["status"] == "active"

    for expected_streak, expected_status in [(1, "active"), (2, "mastered")]:
        session = start_practice(headers)
        client.put(
            f"/api/v1/practice/{session['session_id']}/answer",
            headers=headers,
            json={"question_id": target, "answer": question.answer, "client_revision": 0},
        )
        client.post(
            f"/api/v1/practice/{session['session_id']}/submit",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        tags = client.get("/api/v1/error-tags", headers=headers).json()
        tag = next(item for item in tags if item["question_id"] == target)
        assert tag["streak"] == expected_streak
        assert tag["status"] == expected_status


def test_admin_cors_and_loopback_guards() -> None:
    token = __import__("backend.app.main", fromlist=["ADMIN_TOKEN"]).ADMIN_TOKEN
    response = client.get(
        "/api/v1/admin/banks",
        headers={
            "X-Admin-Token": token,
            "Origin": "http://localhost:8081",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"

    remote = TestClient(app, client=("192.168.1.5", 41001))
    denied = remote.get("/api/v1/admin/banks", headers={"X-Admin-Token": token})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "ADMIN_LOCAL_ONLY"


def test_database_endpoint_is_absolute_and_name_is_checked() -> None:
    with store.connection() as connection:
        runtime = connection.execute(
            "SELECT inet_server_port() AS port, current_database() AS database_name"
        ).fetchone()
    assert runtime["port"] == 15432
    assert runtime["database_name"] == "english_practice"

    root = Path(__file__).resolve().parents[2]
    environment = {
        **os.environ,
        "DATABASE_URL": "postgresql://postgres@127.0.0.1:5432/english_practice",
    }
    rejected = subprocess.run(
        [sys.executable, "-c", "import backend.app.main"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert (
        "DATABASE_URL_PORT_FORBIDDEN: configured=5432 allowed=15432"
        in rejected.stderr
    )
