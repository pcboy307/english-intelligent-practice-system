"""Reproduce the PostgreSQL persistence evidence required by CO-003."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.demo_bank import build_demo_questions


BASE = "http://127.0.0.1:8000/api/v1"
PSQL = r"C:\pgsql\bin\psql.exe"
DATABASE = "english_practice"
ANSWERS = {question.id: question.answer for question in build_demo_questions()}


def psql(sql: str) -> None:
    print(f"\nPSQL> {sql}")
    subprocess.run(
        [
            PSQL,
            "-h",
            "127.0.0.1",
            "-p",
            "15432",
            "-U",
            "postgres",
            "-d",
            DATABASE,
            "-c",
            sql,
        ],
        check=True,
    )


def headers(student_id: str) -> dict[str, str]:
    return {"X-Student-Id": student_id}


def start(client: httpx.Client, student_id: str) -> dict:
    response = client.post(
        f"{BASE}/practice/start",
        headers=headers(student_id),
        json={"duration_minutes": 30},
    )
    response.raise_for_status()
    return response.json()


def answer_and_submit(
    client: httpx.Client,
    student_id: str,
    session: dict,
    *,
    target_id: str | None = None,
    target_answer: str | None = None,
) -> tuple[dict, str]:
    for item in session["items"]:
        answer = (
            target_answer
            if item["question_id"] == target_id
            else ANSWERS[item["question_id"]]
        )
        response = client.put(
            f"{BASE}/practice/{session['session_id']}/answer",
            headers=headers(student_id),
            json={
                "question_id": item["question_id"],
                "answer": answer,
                "client_revision": 0,
            },
        )
        response.raise_for_status()
    key = str(uuid.uuid4())
    response = client.post(
        f"{BASE}/practice/{session['session_id']}/submit",
        headers={**headers(student_id), "Idempotency-Key": key},
    )
    response.raise_for_status()
    return response.json(), key


def idempotency_evidence(client: httpx.Client) -> None:
    student_id = str(uuid.uuid4())
    session = start(client, student_id)
    first, key = answer_and_submit(client, student_id, session)
    second = client.post(
        f"{BASE}/practice/{session['session_id']}/submit",
        headers={**headers(student_id), "Idempotency-Key": key},
    )
    second.raise_for_status()
    assert first == second.json()
    print("\nIDEMPOTENCY")
    print(
        json.dumps(
            {
                "session_id": session["session_id"],
                "first_score": first["score"],
                "second_score": second.json()["score"],
                "responses_equal": first == second.json(),
            },
            ensure_ascii=False,
        )
    )
    psql(
        "SELECT id, status, submit_idempotency_key, "
        "(SELECT count(*) FROM practice_reports r WHERE r.session_id = s.id) AS report_rows "
        "FROM practice_sessions s "
        f"WHERE id = '{session['session_id']}';"
    )


def mastery_evidence(client: httpx.Client) -> None:
    student_id = str(uuid.uuid4())
    probe = start(client, student_id)
    target_id = probe["items"][0]["question_id"]

    wrong_session = start(client, student_id)
    answer_and_submit(
        client,
        student_id,
        wrong_session,
        target_id=target_id,
        target_answer="definitely-wrong",
    )

    correct_one = start(client, student_id)
    first_report, first_key = answer_and_submit(
        client,
        student_id,
        correct_one,
        target_id=target_id,
        target_answer=ANSWERS[target_id],
    )
    duplicate = client.post(
        f"{BASE}/practice/{correct_one['session_id']}/submit",
        headers={**headers(student_id), "Idempotency-Key": first_key},
    )
    duplicate.raise_for_status()
    assert duplicate.json() == first_report

    correct_two = start(client, student_id)
    answer_and_submit(
        client,
        student_id,
        correct_two,
        target_id=target_id,
        target_answer=ANSWERS[target_id],
    )

    print("\nMASTERY")
    print(
        json.dumps(
            {
                "student_id": student_id,
                "question_id": target_id,
                "same_session_duplicate_does_not_increment": True,
            },
            ensure_ascii=False,
        )
    )
    psql(
        "SELECT student_id, question_id, status, streak, "
        "(SELECT count(*) FROM error_tag_successes x WHERE x.tag_id = t.id) AS success_rows "
        "FROM error_tags t "
        f"WHERE student_id = '{student_id}' AND question_id = '{target_id}';"
    )


def main() -> None:
    with httpx.Client(timeout=20.0) as client:
        health = client.get(f"{BASE}/healthz")
        health.raise_for_status()
        idempotency_evidence(client)
        mastery_evidence(client)


if __name__ == "__main__":
    main()
