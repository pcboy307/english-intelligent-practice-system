#!/usr/bin/env python3
"""Seed one archived target bank and switch-flow browser fixture."""

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


client = TestClient(app, client=("127.0.0.1", 43100))
EVIDENCE = ROOT / "qa" / "evidence" / "m25-auth" / "switch-fixture.json"


def database_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def direct_session(
    student_id: str,
    question_ids: list[str],
    *,
    submit_session: bool = False,
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
                Jsonb({"switch_browser_acceptance": True}),
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


def answer(
    student_id: str,
    session_id: str,
    question_id: str,
    value: str,
) -> None:
    response = client.put(
        f"/api/v1/practice/{session_id}/answer",
        headers={"X-Student-Id": student_id},
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
            "X-Student-Id": student_id,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"SUBMIT_FAILED:{response.text}")


def create_archived_bank(name: str, size: int) -> dict:
    bank_id = str(uuid.uuid4())
    passage_id = f"M25-SWITCH-UI-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(database_url()) as connection:
        connection.execute(
            """
            INSERT INTO question_banks
                (id, name, target_size, difficulty_profile, status,
                 coverage_snapshot)
            VALUES (%s, %s, %s, 'standard', 'draft', %s)
            """,
            (bank_id, name, size, Jsonb({"switch_browser_acceptance": True})),
        )
        connection.execute(
            """
            INSERT INTO passages
                (passage_group_id, bank_id, type, content, word_count, topic,
                 book_source, difficulty, status)
            VALUES (%s, %s, 'cloze', %s, 40, '切换验收', '必修1 U1', 2,
                    'published')
            """,
            (
                passage_id,
                bank_id,
                " ".join(["word"] * 40),
            ),
        )
        for index in range(1, size + 1):
            connection.execute(
                """
                INSERT INTO questions
                    (id, bank_id, type, passage_group_id, stem, options, answer,
                     explanation, knowledge_points, grammar_tags, book_source,
                     difficulty, status, batch_id)
                VALUES (%s, %s, 'cloze', %s, %s, %s, %s, %s, %s, '{}',
                        '必修1 U1', 2, 'published', 'M25-SWITCH-UI')
                """,
                (
                    f"{passage_id}-Q{index:02d}",
                    bank_id,
                    passage_id,
                    f"Choose for blank ({index}).",
                    Jsonb(["anxious", "calm", "proud", "silent"]),
                    Jsonb("anxious"),
                    "anxious 与题意一致。calm 和 proud 不符合语境。",
                    [f"switch_browser:{index}"],
                ),
            )
        connection.execute(
            """
            UPDATE question_banks
            SET status='archived', finished_at=now()
            WHERE id=%s
            """,
            (bank_id,),
        )
    return {
        "bank_id": bank_id,
        "name": name,
        "question_count": size,
        "passage_id": passage_id,
    }


def main() -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        active = connection.execute(
            """
            SELECT qb.id::text AS id, qb.name
            FROM bank_active_state bas
            JOIN question_banks qb ON qb.id=bas.active_bank_id
            """
        ).fetchone()
    if active["name"] != "M2 Bank #2":
        store.activate_bank(active["id"], operator="fixture_setup")
    store.reload_active_bank()

    student_id = str(uuid.uuid4())
    cloze = [
        question
        for question in store.questions.values()
        if question.type == "cloze"
    ]
    passage_id = cloze[0].passage_group_id
    targets = [
        question for question in cloze if question.passage_group_id == passage_id
    ][:3]
    wrong_session = direct_session(student_id, [question.id for question in targets])
    for question in targets:
        wrong = next(
            option
            for option in question.options or []
            if str(option).casefold() != str(question.answer).casefold()
        )
        answer(student_id, wrong_session, question.id, wrong)
    submit(student_id, wrong_session)

    in_progress_session = direct_session(student_id, [targets[0].id])
    target_bank = create_archived_bank(
        f"M2.5 UI切换验收题库-{uuid.uuid4().hex[:6]}",
        5,
    )
    banks = client.get(
        "/api/v1/banks",
        headers={"X-Student-Id": student_id},
    ).json()
    coverage = client.get(
        "/api/v1/stats/coverage?bank_id=active",
        headers={"X-Student-Id": student_id},
    ).json()
    mistakes = client.get(
        "/api/v1/mistakes?status=open",
        headers={"X-Student-Id": student_id},
    ).json()
    evidence = {
        "student_id": student_id,
        "active_bank": active,
        "target_bank": target_bank,
        "wrong_session_id": wrong_session,
        "in_progress_session_id": in_progress_session,
        "coverage": coverage,
        "mistakes": mistakes,
        "banks": banks,
    }
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
