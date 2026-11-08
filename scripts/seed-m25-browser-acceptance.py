#!/usr/bin/env python3
"""Create deterministic browser-review fixtures for M2.5 acceptance."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("WEAKNESS_ANALYSIS_DISABLED", "1")

from backend.app.main import app, store  # noqa: E402


client = TestClient(app, client=("127.0.0.1", 43000))
EVIDENCE = ROOT / "qa" / "evidence" / "m25" / "browser-fixture.json"


def database_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def headers(student_id: str) -> dict[str, str]:
    return {"X-Student-Id": student_id}


def direct_session(
    student_id: str,
    question_ids: list[str],
) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url()) as connection:
        connection.execute(
            """
            INSERT INTO practice_sessions
                (id, student_id, bank_id, bank_name, bank_version,
                 duration_minutes, status, started_at, deadline,
                 composition_note, session_kind)
            VALUES (%s, %s, %s, %s, 1, 30, 'in_progress', %s, %s, %s,
                    'practice')
            """,
            (
                session_id,
                student_id,
                store.bank["bank_id"],
                store.bank["name"],
                now,
                now + timedelta(minutes=30),
                Jsonb({"browser_acceptance": True}),
            ),
        )
        for ordinal, question_id in enumerate(question_ids):
            connection.execute(
                """
                INSERT INTO session_items
                    (session_id, question_id, bank_id, ordinal)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, question_id, store.bank["bank_id"], ordinal),
            )
    return session_id


def wrong_answer(question_id: str) -> str:
    question = store.get_question(store.bank["bank_id"], question_id)
    assert question.options
    for option in question.options:
        if str(option).casefold() != str(question.answer).casefold():
            return option
    raise RuntimeError(f"NO_WRONG_OPTION:{question_id}")


def answer(
    student_id: str,
    session_id: str,
    question_id: str,
    value: str,
) -> None:
    response = client.put(
        f"/api/v1/practice/{session_id}/answer",
        headers=headers(student_id),
        json={
            "question_id": question_id,
            "answer": value,
            "client_revision": 0,
        },
    )
    if response.status_code != 204:
        raise RuntimeError(f"ANSWER_FAILED:{response.text}")


def submit(student_id: str, session_id: str) -> None:
    response = client.post(
        f"/api/v1/practice/{session_id}/submit",
        headers={
            **headers(student_id),
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"SUBMIT_FAILED:{response.text}")


def create_history_bank() -> dict:
    bank_id = str(uuid.uuid4())
    passage_id = f"M25-HISTORY-{uuid.uuid4().hex[:8]}"
    question_id = f"{passage_id}-Q01"
    with psycopg.connect(database_url()) as connection:
        connection.execute(
            """
            INSERT INTO question_banks
                (id, name, target_size, difficulty_profile, status,
                 coverage_snapshot)
            VALUES (%s, 'M2.5 历史验收题库', 1, 'standard', 'draft', %s)
            """,
            (bank_id, Jsonb({"browser_acceptance": True})),
        )
        connection.execute(
            """
            INSERT INTO passages
                (passage_group_id, bank_id, type, content, word_count, topic,
                 book_source, difficulty, status)
            VALUES (%s, %s, 'cloze', %s, 40, '历史验收', '必修1 U1', 2,
                    'published')
            """,
            (
                passage_id,
                bank_id,
                "At first, the learner felt (1) ______ about the new task. "
                "A patient teacher helped the learner stay calm and try again.",
            ),
        )
        connection.execute(
            """
            INSERT INTO questions
                (id, bank_id, type, passage_group_id, stem, options, answer,
                 explanation, knowledge_points, grammar_tags, book_source,
                 difficulty, status, batch_id)
            VALUES (%s, %s, 'cloze', %s,
                    'Choose the best word for blank (1).',
                    %s, %s,
                    'anxious 表示起初紧张。calm 和 proud 不符合语境。',
                    %s, '{}', '必修1 U1', 2, 'published', 'M25-BROWSER')
            """,
            (
                question_id,
                bank_id,
                passage_id,
                Jsonb(["anxious", "calm", "proud", "silent"]),
                Jsonb("anxious"),
                ["browser_acceptance:history"],
            ),
        )
        connection.execute(
            """
            UPDATE question_banks
            SET status='ready', finished_at=now()
            WHERE id=%s
            """,
            (bank_id,),
        )
    return {
        "bank_id": bank_id,
        "name": "M2.5 历史验收题库",
        "passage_id": passage_id,
        "question_id": question_id,
    }


def main() -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    m2 = next(
        row
        for row in (
            psycopg.connect(database_url(), row_factory=dict_row)
            .execute(
                "SELECT id::text AS id, name FROM question_banks WHERE name='M2 Bank #2'"
            )
            .fetchall()
        )
    )
    if store.bank["bank_id"] != m2["id"]:
        store.activate_bank(m2["id"], operator="browser_acceptance")

    student_id = str(uuid.uuid4())
    cloze = [
        question
        for question in store.questions.values()
        if question.type == "cloze"
    ]
    passage_id = cloze[0].passage_group_id
    passage_questions = [
        question
        for question in cloze
        if question.passage_group_id == passage_id
    ]
    targets = passage_questions[:3]

    practice_session = direct_session(
        student_id,
        [question.id for question in targets],
    )
    for question in targets:
        answer(
            student_id,
            practice_session,
            question.id,
            wrong_answer(question.id),
        )
    submit(student_id, practice_session)

    repeat_session = direct_session(student_id, [targets[0].id])
    answer(
        student_id,
        repeat_session,
        targets[0].id,
        str(targets[0].answer),
    )
    submit(student_id, repeat_session)

    history = create_history_bank()
    try:
        store.activate_bank(history["bank_id"], operator="browser_acceptance")
        history_session = direct_session(
            student_id,
            [history["question_id"]],
        )
        answer(
            student_id,
            history_session,
            history["question_id"],
            "calm",
        )
        submit(student_id, history_session)
    finally:
        store.activate_bank(m2["id"], operator="browser_acceptance")

    mistakes = client.get(
        "/api/v1/mistakes?status=open",
        headers=headers(student_id),
    ).json()
    coverage = client.get(
        "/api/v1/stats/coverage?bank_id=active",
        headers=headers(student_id),
    ).json()
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        counts = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM practice_sessions
               WHERE student_id=%s) AS sessions,
              (SELECT count(*) FROM question_attempts
               WHERE student_id=%s) AS attempts,
              (SELECT count(*) FROM mistake_items
               WHERE student_id=%s AND status='open') AS open_mistakes
            """,
            (student_id, student_id, student_id),
        ).fetchone()
    evidence = {
        "student_id": student_id,
        "active_bank": m2,
        "current_passage_id": passage_id,
        "current_question_ids": [question.id for question in targets],
        "practice_session_id": practice_session,
        "repeat_session_id": repeat_session,
        "history": history,
        "history_session_id": history_session,
        "mistakes": mistakes,
        "coverage": coverage,
        "counts": counts,
    }
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
