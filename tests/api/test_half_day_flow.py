from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

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
    assert report["bank_name"] == "Demo Bank"
    assert len(report["type_scores"]) == 3
    assert len(report["question_results"]) == 30
    assert all(item["explanation"] for item in report["question_results"])
    store.sessions.clear()
    persisted = client.get(f"/api/v1/reports/{session['session_id']}", headers=headers)
    assert persisted.status_code == 200
    assert persisted.json() == report


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
