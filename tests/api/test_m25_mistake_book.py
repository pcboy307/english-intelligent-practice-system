from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

os.environ.setdefault("WEAKNESS_ANALYSIS_DISABLED", "1")

from backend.app.main import app, store

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "db" / "migrations" / "002_mistake_book.sql"
client = TestClient(app, client=("127.0.0.1", 42000))


def database_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def apply_migration() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    with psycopg.connect(database_url(), autocommit=True) as connection:
        connection.execute(sql)


def student_headers() -> dict[str, str]:
    return {"X-Student-Id": str(uuid.uuid4())}


def direct_session(
    headers: dict[str, str],
    question_ids: list[str],
    *,
    session_kind: str = "practice",
) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    student_id = headers["X-Student-Id"]
    bank_id = store.bank["bank_id"]
    with psycopg.connect(database_url()) as connection:
        connection.execute(
            """
            INSERT INTO practice_sessions
                (id, student_id, bank_id, bank_name, bank_version,
                 duration_minutes, status, started_at, deadline,
                 composition_note, session_kind)
            VALUES (%s, %s, %s, %s, 1, 30, 'in_progress', %s, %s, %s, %s)
            """,
            (
                session_id,
                student_id,
                bank_id,
                store.bank["name"],
                now,
                now + timedelta(minutes=30),
                Jsonb({"test_fixture": True}),
                session_kind,
            ),
        )
        for ordinal, question_id in enumerate(question_ids):
            connection.execute(
                """
                INSERT INTO session_items
                    (session_id, question_id, bank_id, ordinal)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, question_id, bank_id, ordinal),
            )
    return session_id


def answer(
    headers: dict[str, str],
    session_id: str,
    question_id: str,
    value: str,
) -> None:
    response = client.put(
        f"/api/v1/practice/{session_id}/answer",
        headers=headers,
        json={
            "question_id": question_id,
            "answer": value,
            "client_revision": 0,
        },
    )
    assert response.status_code == 204, response.text


def submit(headers: dict[str, str], session_id: str) -> dict:
    response = client.post(
        f"/api/v1/practice/{session_id}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def wrong_answer(question_id: str) -> str:
    question = store.questions[question_id]
    if question.type == "gap_fill":
        return "B" if str(question.answer).upper() != "B" else "C"
    assert question.options
    for option in question.options:
        if str(option).casefold() != str(question.answer).casefold():
            return option
    raise AssertionError("no wrong option")


def mistake_row(headers: dict[str, str], question_id: str) -> dict | None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return connection.execute(
            """
            SELECT *
            FROM mistake_items
            WHERE student_id=%s AND bank_id=%s AND question_id=%s
            """,
            (
                headers["X-Student-Id"],
                store.bank["bank_id"],
                question_id,
            ),
        ).fetchone()


def create_review(headers: dict[str, str], passage_id: str) -> dict:
    response = client.post(
        f"/api/v1/mistakes/review/{passage_id}",
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_m25_migration_is_idempotent_and_preserves_existing_rows() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        before = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM practice_sessions) AS sessions,
              (SELECT count(*) FROM saved_answers) AS answers
            """
        ).fetchone()

    apply_migration()
    apply_migration()

    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        after = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM practice_sessions) AS sessions,
              (SELECT count(*) FROM saved_answers) AS answers
            """
        ).fetchone()
        tables = {
            row["table_name"]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='public'
                """
            ).fetchall()
        }
        session_kind = connection.execute(
            """
            SELECT data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='practice_sessions'
              AND column_name='session_kind'
            """
        ).fetchone()

    assert before == after
    assert {
        "question_attempts",
        "mistake_items",
        "report_deletions",
        "bank_switch_log",
    } <= tables
    assert session_kind == {
        "data_type": "character varying",
        "column_default": "'practice'::character varying",
        "is_nullable": "NO",
    }


def test_m25_coverage_tokens_and_openapi_paths_exist() -> None:
    tokens = json.loads(
        (ROOT / "contracts" / "design-tokens.json").read_text(encoding="utf-8")
    )
    assert tokens["color"]["coverage_repeat"] != tokens["color"]["coverage_once"]
    assert tokens["color"]["coverage_once"] != tokens["color"]["coverage_none"]

    openapi = (
        ROOT / "contracts" / "openapi.yaml"
    ).read_text(encoding="utf-8")
    declared_paths = set(
        re.findall(r"(?m)^  (/[^:]+):\s*$", openapi)
    )
    assert {
        "/mistakes",
        "/mistakes/{passage_id}",
        "/mistakes/review/{passage_id}",
        "/stats/coverage",
        "/maintenance/clear-mistakes/preview",
        "/maintenance/clear-mistakes",
        "/maintenance/reset-coverage/preview",
        "/maintenance/reset-coverage",
    } <= declared_paths


def test_m25_wrong_answer_records_attempt_and_opens_mistake() -> None:
    headers = student_headers()
    question_id = next(
        qid for qid, question in store.questions.items() if question.type == "cloze"
    )
    question = store.questions[question_id]
    session_id = direct_session(headers, [question_id])
    chosen = wrong_answer(question_id)
    answer(headers, session_id, question_id, chosen)
    submit(headers, session_id)

    mistake = mistake_row(headers, question_id)
    assert mistake is not None
    assert mistake["status"] == "open"
    assert mistake["wrong_count"] == 1
    assert mistake["correct_streak"] == 0
    assert mistake["passage_id"] == question.passage_group_id
    assert mistake["question_type"] == "cloze"

    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        attempt = connection.execute(
            """
            SELECT session_id, bank_id, question_id, passage_id, question_type,
                   chosen_option, correct_option, is_correct, attempt_kind
            FROM question_attempts
            WHERE student_id=%s AND session_id=%s AND question_id=%s
            """,
            (headers["X-Student-Id"], session_id, question_id),
        ).fetchone()
    assert attempt == {
        "session_id": uuid.UUID(session_id),
        "bank_id": uuid.UUID(store.bank["bank_id"]),
        "question_id": question_id,
        "passage_id": question.passage_group_id,
        "question_type": "cloze",
        "chosen_option": chosen,
        "correct_option": str(question.answer),
        "is_correct": False,
        "attempt_kind": "practice",
    }


def test_m25_two_correct_reviews_master_then_wrong_reopens() -> None:
    headers = student_headers()
    question_id = next(
        qid for qid, question in store.questions.items() if question.type == "cloze"
    )
    question = store.questions[question_id]
    passage_id = question.passage_group_id

    first_session = direct_session(headers, [question_id])
    answer(headers, first_session, question_id, wrong_answer(question_id))
    submit(headers, first_session)

    first_review = create_review(headers, passage_id)
    assert first_review["composition_note"]["session_kind"] == "review"
    assert question_id in {
        item["question_id"] for item in first_review["items"]
    }
    answer(headers, first_review["session_id"], question_id, str(question.answer))
    submit(headers, first_review["session_id"])
    row = mistake_row(headers, question_id)
    assert row["status"] == "open"
    assert row["correct_streak"] == 1

    second_review = create_review(headers, passage_id)
    answer(headers, second_review["session_id"], question_id, str(question.answer))
    submit(headers, second_review["session_id"])
    row = mistake_row(headers, question_id)
    assert row["status"] == "mastered"
    assert row["correct_streak"] == 2
    assert row["mastered_at"] is not None

    open_list = client.get("/api/v1/mistakes", headers=headers)
    assert open_list.status_code == 200, open_list.text
    serialized = json.dumps(open_list.json(), ensure_ascii=False)
    assert question_id not in serialized

    wrong_session = direct_session(headers, [question_id])
    answer(headers, wrong_session, question_id, wrong_answer(question_id))
    submit(headers, wrong_session)
    row = mistake_row(headers, question_id)
    assert row["status"] == "open"
    assert row["correct_streak"] == 0
    assert row["wrong_count"] == 2


@pytest.mark.parametrize("reset_with_wrong", [True, False])
def test_m25_review_streak_rules(reset_with_wrong: bool) -> None:
    headers = student_headers()
    question_id = next(
        qid for qid, question in store.questions.items() if question.type == "cloze"
    )
    question = store.questions[question_id]
    passage_id = question.passage_group_id

    session_id = direct_session(headers, [question_id])
    answer(headers, session_id, question_id, wrong_answer(question_id))
    submit(headers, session_id)

    review = create_review(headers, passage_id)
    answer(headers, review["session_id"], question_id, str(question.answer))
    submit(headers, review["session_id"])
    assert mistake_row(headers, question_id)["correct_streak"] == 1

    next_review = create_review(headers, passage_id)
    next_answer = (
        wrong_answer(question_id) if reset_with_wrong else str(question.answer)
    )
    answer(headers, next_review["session_id"], question_id, next_answer)
    submit(headers, next_review["session_id"])
    row = mistake_row(headers, question_id)
    if reset_with_wrong:
        assert row["correct_streak"] == 0
        assert row["status"] == "open"
    else:
        assert row["correct_streak"] == 2
        assert row["status"] == "mastered"


def test_m25_cloze_keeps_three_items_and_review_limits_answerable_blanks() -> None:
    headers = student_headers()
    cloze = [
        question
        for question in store.questions.values()
        if question.type == "cloze"
    ]
    passage_id = cloze[0].passage_group_id
    targets = [
        question for question in cloze if question.passage_group_id == passage_id
    ][:3]
    session_id = direct_session(headers, [question.id for question in targets])
    for question in targets:
        answer(headers, session_id, question.id, wrong_answer(question.id))
    submit(headers, session_id)

    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        count = connection.execute(
            """
            SELECT count(*) AS count
            FROM mistake_items
            WHERE student_id=%s AND passage_id=%s AND status='open'
            """,
            (headers["X-Student-Id"], passage_id),
        ).fetchone()["count"]
    assert count == 3

    review = create_review(headers, passage_id)
    review_ids = {item["question_id"] for item in review["items"]}
    assert review_ids == {question.id for question in targets}
    detail = client.get(f"/api/v1/mistakes/{passage_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert len(payload["questions"]) == 15
    assert {item["question_id"] for item in payload["target_items"]} == review_ids
    assert sum(item["locked"] for item in payload["questions"]) == 12


def test_m25_seven_mistake_is_one_passage_and_review_has_five_blanks() -> None:
    headers = student_headers()
    gap = [
        question
        for question in store.questions.values()
        if question.type == "gap_fill"
    ]
    passage_id = gap[0].passage_group_id
    targets = [question for question in gap if question.passage_group_id == passage_id]
    session_id = direct_session(headers, [question.id for question in targets])
    answer(headers, session_id, targets[0].id, wrong_answer(targets[0].id))
    for question in targets[1:]:
        answer(headers, session_id, question.id, str(question.answer))
    submit(headers, session_id)

    key = f"seven:{passage_id}"
    mistake = mistake_row(headers, key)
    assert mistake is not None
    assert mistake["question_type"] == "seven"
    assert mistake["wrong_count"] == 1

    review = create_review(headers, passage_id)
    assert len(review["items"]) == 5
    assert {item["question_id"] for item in review["items"]} == {
        question.id for question in targets
    }


def test_m25_mistake_state_is_isolated_by_student() -> None:
    first_headers = student_headers()
    second_headers = student_headers()
    question_id = next(
        qid for qid, question in store.questions.items() if question.type == "reading"
    )

    first_session = direct_session(first_headers, [question_id])
    answer(first_headers, first_session, question_id, wrong_answer(question_id))
    submit(first_headers, first_session)

    assert mistake_row(first_headers, question_id)["wrong_count"] == 1
    assert mistake_row(second_headers, question_id) is None

    second_session = direct_session(second_headers, [question_id])
    question = store.questions[question_id]
    answer(second_headers, second_session, question_id, str(question.answer))
    submit(second_headers, second_session)
    assert mistake_row(second_headers, question_id) is None
    assert mistake_row(first_headers, question_id)["wrong_count"] == 1
