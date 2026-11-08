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
from backend.app.composer import allocate_difficulty, allocate_largest_remainder


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


def answer_all_correct(session: dict, headers: dict[str, str]) -> None:
    for item in session["items"]:
        correct = store.questions[item["question_id"]].answer
        response = client.put(
            f"/api/v1/practice/{session['session_id']}/answer",
            headers=headers,
            json={
                "question_id": item["question_id"],
                "answer": correct,
                "client_revision": 0,
            },
        )
        assert response.status_code == 204, response.text


def submit_session(session: dict, headers: dict[str, str]) -> dict:
    response = client.post(
        f"/api/v1/practice/{session['session_id']}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_first_paper_has_reading_mode_and_no_answers() -> None:
    headers = student_headers()
    bank = client.get("/api/v1/bank/active", headers=headers)
    assert bank.status_code == 200
    assert bank.json() == {
        "bank_id": store.bank["bank_id"],
        "name": store.bank["name"],
        "status": "active",
    }
    session = start_practice(headers)
    assert len(session["items"]) == 29
    assert session["bank_name"] == store.bank["name"]
    serialized = json.dumps(session)
    assert '"answer"' not in serialized
    assert '"explanation"' not in serialized
    assert {item["type"] for item in session["items"]} == {
        "cloze",
        "grammar_fill",
        "reading",
    }
    assert all(item["options"] for item in session["items"])
    assert all(
        item["book_tag"] in {"必修", "选必一", "选必二", "跨册"}
        for item in session["items"]
    )
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
    answer_all_correct(session, headers)

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
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-29题-100\.00分", report["report_title"])
    assert report["bank_name"] == store.bank["name"]
    assert report["question_count"] == 29
    assert len(report["weakness_analysis"]) <= 300
    assert len(report["type_scores"]) == 3
    assert report["weak_points"]
    assert report["suggestions"]
    assert len(report["question_results"]) == 29
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
    assert len(review.json()["items"]) == 29
    assert all("explanation" not in item for item in review.json()["items"])
    assert all(item["correct_answer"] for item in review.json()["items"])


def test_review_is_blocked_before_submit() -> None:
    headers = student_headers()
    session = start_practice(headers)
    response = client.get(
        f"/api/v1/practice/{session['session_id']}/review",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SESSION_NOT_SUBMITTED"


def test_exit_deletes_unsubmitted_session_without_report() -> None:
    headers = student_headers()
    session = start_practice(headers)
    exited = client.delete(
        f"/api/v1/practice/{session['session_id']}",
        headers=headers,
    )
    assert exited.status_code == 204
    assert client.get(
        f"/api/v1/practice/{session['session_id']}",
        headers=headers,
    ).status_code == 404
    with store.connection() as connection:
        rows = {
            table: connection.execute(
                f"SELECT count(*) AS count FROM {table} WHERE {id_column}=%s",
                (session["session_id"],),
            ).fetchone()["count"]
            for table, id_column in (
                ("practice_reports", "session_id"),
                ("saved_answers", "session_id"),
                ("session_items", "session_id"),
                ("practice_sessions", "id"),
            )
        }
    assert rows == {
        "practice_reports": 0,
        "saved_answers": 0,
        "session_items": 0,
        "practice_sessions": 0,
    }


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
    assert listed["question_count"] == 29

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
    ).status_code == 200
    with store.connection() as connection:
        expected_counts = {
            "practice_reports": 1,
            "saved_answers": 0,
            "session_items": len(session["items"]),
            "practice_sessions": 1,
        }
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
            assert count == expected_counts[table]
        deletion = connection.execute(
            """
            SELECT student_id, deleted_at
            FROM report_deletions
            WHERE session_id=%s
            """,
            (session["session_id"],),
        ).fetchone()
    assert deletion is not None
    assert str(deletion["student_id"]) == headers["X-Student-Id"]


def test_wrong_answer_is_tagged_and_two_different_sessions_clear_it() -> None:
    headers = student_headers()
    first = start_practice(headers)
    target = first["items"][0]["question_id"]
    question = store.questions[target]
    wrong = question.options[0] if question.options else "wrong"
    if wrong.casefold() == str(question.answer).casefold():
        wrong = question.options[1] if question.options else "wrong-2"
    for item in first["items"]:
        answer = wrong if item["question_id"] == target else store.questions[item["question_id"]].answer
        client.put(
            f"/api/v1/practice/{first['session_id']}/answer",
            headers=headers,
            json={"question_id": item["question_id"], "answer": answer, "client_revision": 0},
        )
    submit_session(first, headers)
    tags = client.get("/api/v1/error-tags", headers=headers).json()
    tag = next(item for item in tags if item["question_id"] == target)
    assert tag["status"] == "active"

    for expected_streak, expected_status in [(1, "active"), (2, "mastered")]:
        for _attempt in range(8):
            session = start_practice(headers)
            answer_all_correct(session, headers)
            submit_session(session, headers)
            if any(item["question_id"] == target for item in session["items"]):
                break
        else:
            raise AssertionError("target question was not selected in eight sessions")
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
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert rejected.returncode != 0
    assert (
        "DATABASE_URL_PORT_FORBIDDEN: configured=5432 allowed=15432"
        in rejected.stderr
    )


def test_four_generated_papers_meet_all_hard_constraints() -> None:
    headers = student_headers()
    logs = []
    expected_sizes = [29, 30, 29, 30]
    book_percentages = {"选必二": 0.45, "选必一": 0.30, "必修": 0.20, "cross_book": 0.05}
    tie_order = ["选必二", "选必一", "必修", "cross_book"]

    for paper_number, expected_size in enumerate(expected_sizes, start=1):
        _, _, _, _, active_groups, _ = store._student_state(headers["X-Student-Id"])
        assert active_groups == set()
        session = start_practice(headers)
        assert len(session["items"]) == expected_size
        log = session["composition_note"]["assembly_log"]
        assert log["paper_label"] == ("29 题阅读场" if paper_number % 2 else "30 题七选五场")
        assert log["question_count"] == expected_size
        if not log.get("fallback_used", False):
            assert log["book_quota_expected"] == allocate_largest_remainder(
                expected_size,
                book_percentages,
                tie_order,
            )
            assert log["book_quota_actual"] == log["book_quota_expected"]
            assert log["difficulty_actual"] == allocate_difficulty(
                expected_size
            )
        else:
            assert sum(log["book_quota_actual"].values()) == expected_size
            assert sum(log["difficulty_actual"].values()) == expected_size
        assert max(log["grammar_tag_counts"].values(), default=0) <= 3
        assert log["error_pool_ratio"] <= 0.60
        assert all(
            item["book_tag"] in {"必修", "选必一", "选必二", "跨册"}
            for item in log["question_weights"]
        )
        assert len(log["question_weights"]) == expected_size
        logs.append(log)
        answer_all_correct(session, headers)
        submit_session(session, headers)

    for log in logs[2:]:
        if not log.get("fallback_used", False):
            assert log["recent_three_question_weights"]
            assert all(
                item["weight"] < item["base_weight"]
                for item in log["recent_three_question_weights"]
            )


def test_two_unfinished_sessions_do_not_share_a_passage() -> None:
    headers = student_headers()
    first = start_practice(headers)
    second = start_practice(headers)
    first_groups = {item["passage_group_id"] for item in first["items"]}
    second_groups = {item["passage_group_id"] for item in second["items"]}
    assert first_groups.isdisjoint(second_groups)
    client.delete(f"/api/v1/practice/{first['session_id']}", headers=headers)
    client.delete(f"/api/v1/practice/{second['session_id']}", headers=headers)
