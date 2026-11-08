from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.app.m2_repository import M2Repository


def valid_reading() -> dict:
    text = (
        "Students read a short book about healthy food and daily exercise. "
        "The teacher asks them to explain one idea with a clear example."
    )
    return {
        "type": "reading",
        "passage_group_id": f"M2-TEST-READING-{uuid.uuid4().hex[:8]}",
        "topic": "运动与健康",
        "book_source": "选必二 U3",
        "difficulty": 3,
        "passage": text,
        "questions": [
            {
                "stem": f"What is the main idea of sentence {index}?",
                "options": ["A clear example.", "A new school.", "A long trip.", "A price list."],
                "answer": "A clear example.",
                "explanation": "The text names a clear example. The other choices are absent. This tests detail reading.",
                "knowledge_points": [f"reading_detail_{index}"],
                "grammar_tags": [tag],
                "book_source": "选必二 U3",
                "difficulty": 3,
            }
            for index, tag in enumerate(
                [
                    "tense_system",
                    "noun_clauses",
                    "passive_voice_tenses",
                    "word_formation",
                ],
                start=1,
            )
        ],
    }


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres@127.0.0.1:15432/english_practice",
    )


def test_repository_keeps_new_bank_in_generating_until_pause_and_never_appends_to_ready(
    caplog,
) -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        with connection.transaction(force_rollback=True):
            repo = M2Repository(connection)
            bank = repo.create_bank(
                name=f"M2 test {uuid.uuid4()}",
                target_size=300,
                difficulty_profile="standard",
            )
            assert bank["status"] == "draft"

            job = repo.create_generation_job(
                bank["id"],
                target_passages=47,
                batch_size=10,
                approved_by="pytest",
                reason="M2 repository test",
            )
            assert job["status"] == "queued"
            assert repo.get_bank(bank["id"])["status"] == "generating"

            question_ids = repo.insert_passage(
                bank_id=bank["id"],
                job_id=job["id"],
                batch_id="M2-TEST-PILOT",
                record=valid_reading(),
            )
            assert len(question_ids) == 4
            assert repo.question_count(bank["id"]) == 4
            assert repo.get_bank(bank["id"])["status"] == "generating"

            repo.set_job_status(job["id"], "paused_for_owner")
            assert repo.get_job(job["id"])["status"] == "paused_for_owner"
            assert repo.get_bank(bank["id"])["status"] == "generating"

            repo.set_bank_status(
                bank["id"],
                "ready",
                coverage_snapshot={
                    "question_counts": {
                        "cloze": 0,
                        "grammar_fill": 0,
                        "reading": 4,
                        "gap_fill": 0,
                    },
                    "generated_at": "2026-11-07T00:00:00+00:00",
                },
            )
            with pytest.raises(psycopg.errors.RaiseException, match="BANK_APPEND_FORBIDDEN"):
                repo.insert_passage(
                    bank_id=bank["id"],
                    job_id=job["id"],
                    batch_id="M2-FORBIDDEN-APPEND",
                    record=valid_reading(),
                )


def test_activation_moves_previous_active_to_ready_and_can_return_target_to_ready() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        with connection.transaction(force_rollback=True):
            repo = M2Repository(connection)
            previous = repo.get_active_bank()
            bank = repo.create_bank(
                name=f"M2 activate test {uuid.uuid4()}",
                target_size=300,
                difficulty_profile="standard",
            )
            repo.set_bank_status(
                bank["id"],
                "ready",
                coverage_snapshot={
                    "question_counts": {
                        "cloze": 0,
                        "grammar_fill": 0,
                        "reading": 0,
                        "gap_fill": 0,
                    },
                    "generated_at": "2026-11-07T00:00:00+00:00",
                },
            )
            repo.activate_bank(bank["id"], actor="pytest")

            assert repo.get_active_bank()["id"] == bank["id"]
            assert repo.get_bank(previous["id"])["status"] == "ready"

            repo.set_bank_status(bank["id"], "ready")
            assert repo.get_active_bank() is None
            assert repo.get_bank(bank["id"])["status"] == "ready"


def test_generating_bank_can_start_a_replacement_job_after_previous_job_fails() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        with connection.transaction(force_rollback=True):
            repo = M2Repository(connection)
            bank = repo.create_bank(
                name=f"M2 retry test {uuid.uuid4()}",
                target_size=300,
                difficulty_profile="standard",
            )
            first = repo.create_generation_job(
                bank["id"],
                target_passages=47,
                batch_size=10,
                approved_by="pytest",
                reason="first attempt",
            )
            repo.set_job_status(first["id"], "failed")

            second = repo.create_generation_job(
                bank["id"],
                target_passages=47,
                batch_size=10,
                approved_by="pytest",
                reason="replacement after failure",
            )

            assert second["status"] == "queued"
            assert second["id"] != first["id"]
            assert repo.get_bank(bank["id"])["generation_job_id"] == second["id"]


def test_replace_passage_questions_updates_the_fixed_passage_and_all_questions() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        with connection.transaction(force_rollback=True):
            repo = M2Repository(connection)
            bank = repo.create_bank(
                name=f"M2 replace test {uuid.uuid4()}",
                target_size=300,
                difficulty_profile="standard",
            )
            job = repo.create_generation_job(
                bank["id"],
                target_passages=47,
                batch_size=10,
                approved_by="pytest",
                reason="replace passage test",
            )
            original = valid_reading()
            repo.insert_passage(
                bank_id=bank["id"],
                job_id=job["id"],
                batch_id="M2-TEST-ORIGINAL",
                record=original,
            )
            replacement = valid_reading()
            replacement["passage_group_id"] = original["passage_group_id"]
            replacement["passage"] = (
                "Students now read a new short book about rest and recovery. "
                "The teacher asks them to compare two examples."
            )
            replacement["questions"][0]["stem"] = "Why do students read the book?"

            repo.replace_passage_questions(
                bank_id=bank["id"],
                batch_id="M2-TEST-REPLACEMENT",
                record=replacement,
            )

            passage = connection.execute(
                """
                SELECT content, word_count
                FROM passages
                WHERE bank_id=%s AND passage_group_id=%s
                """,
                (bank["id"], original["passage_group_id"]),
            ).fetchone()
            question = connection.execute(
                """
                SELECT stem, batch_id
                FROM questions
                WHERE bank_id=%s AND id=%s
                """,
                (
                    bank["id"],
                    f"{original['passage_group_id']}-Q01",
                ),
            ).fetchone()

            assert passage["content"] == replacement["passage"]
            assert passage["word_count"] == 19
            assert question["stem"] == "Why do students read the book?"
            assert question["batch_id"] == "M2-TEST-REPLACEMENT"
